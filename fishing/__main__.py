import argparse
import ctypes
import json
from pathlib import Path
import time

import cv2
import mss
import numpy as np

from .controller import Controller
from .vision import Detector
from .overlay import draw_overlay

ROOT = Path(__file__).resolve().parent.parent
USER32 = ctypes.windll.user32


def key_down(key):
    return bool(USER32.GetAsyncKeyState(key) & 0x8000)


def click(region, point):
    x = region["left"] + round(point[0]*region["width"])
    y = region["top"] + round(point[1]*region["height"])
    USER32.SetCursorPos(x, y)
    USER32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(.012)
    USER32.mouse_event(0x0004, 0, 0, 0, 0)


def calibrate(sct):
    desktop = sct.monitors[0]
    shot = np.asarray(sct.grab(desktop))[:, :, :3].copy()
    scale = min(1, 1500/shot.shape[1], 900/shot.shape[0])
    small = cv2.resize(shot, None, fx=scale, fy=scale)
    title = "Select GAME only: exclude ads, title bar, toolbar and bottom black X strip. ENTER confirms"
    x, y, w, h = cv2.selectROI(title, small, showCrosshair=True)
    cv2.destroyAllWindows()
    if w < 100 or h < 100:
        raise SystemExit("Calibration cancelled; nothing clicked.")
    region = dict(left=desktop["left"]+round(x/scale), top=desktop["top"]+round(y/scale),
                  width=round(w/scale), height=round(h/scale))
    ratio = region["width"]/region["height"]
    if not .55 < ratio < .68:
        raise SystemExit("Expected portrait game area, approximately 500 x 820. Please calibrate again.")
    (ROOT/"config.json").write_text(json.dumps(region, indent=2))
    return region


def main():
    parser = argparse.ArgumentParser(description="BlueStacks fishing watcher. F8 starts/pauses; F9 or ESC exits.")
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--max-casts", type=int, default=10)
    parser.add_argument("--latency-ms", type=float, default=35)
    parser.add_argument("--timeout", type=float, default=45, help="Pause after this many seconds without an action")
    parser.add_argument("--preview-fps", type=int, default=10, help="Preview refresh rate; does not limit control FPS")
    parser.add_argument("--control-fps", type=int, default=60, help="Maximum capture/control iterations per second")
    parser.add_argument("--no-preview", action="store_true", help="Disable preview for less rendering overhead; hotkeys still work")
    parser.add_argument("--verbose", action="store_true", help="Print routine detections and clicks (off by default)")
    args = parser.parse_args()
    if args.max_casts < 1 or not 0 <= args.latency_ms <= 250 or args.timeout < 5:
        parser.error("Use max-casts >= 1, latency-ms 0..250, timeout >= 5")
    if not 1 <= args.preview_fps <= 60 or not 10 <= args.control_fps <= 120:
        parser.error("Use preview-fps 1..60 and control-fps 10..120")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:
        USER32.SetProcessDPIAware()
    detector = Detector(ROOT/"assets")
    # Small regions do not benefit from large OpenCV thread pools.
    cv2.setNumThreads(1)
    controller = Controller(args.latency_ms/1000, args.max_casts)
    active = False
    was_f8 = False
    was_f7 = False
    recent_action = None
    recent_action_at = -100.
    last_frame = time.monotonic()
    fps = 60.
    last_preview = -100.
    last_progress = time.monotonic()
    unknown_since = None
    stable_state = "unknown"
    stable_count = 0
    with mss.MSS() as sct:
        path = ROOT/"config.json"
        region = calibrate(sct) if args.calibrate or not path.exists() else json.loads(path.read_text())
        print("WATCH ONLY. Keep the game unobscured; move the preview beside it.", flush=True)
        print("F8: enable/pause clicking. F9 or ESC: quit. F7: save diagnostic image. Close preview: quit.", flush=True)
        title = "Fishing preview - F8 run/pause - F9 stop"
        if not args.no_preview:
            cv2.namedWindow(title, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(title, 400, 656)
        # Place preview beside the game, not over its capture region.
        if not args.no_preview:
            cv2.moveWindow(title, region["left"]+region["width"]+50, region["top"])
        try:
            while True:
                started = time.monotonic()
                fps = .9*fps + .1/max(.001, started-last_frame)
                last_frame = started
                if key_down(0x78) or key_down(0x1B):
                    break
                f8 = key_down(0x77)
                if f8 and not was_f8:
                    active = not active and not controller.finished
                    last_progress = started
                    controller.previous = None
                    controller.velocity = 0.0
                    unknown_since = None
                    print("RUNNING" if active else "PAUSED", flush=True)
                was_f8 = f8
                capture_started = time.monotonic()
                raw = np.asarray(sct.grab(region))
                capture_done = time.monotonic()
                # Midpoint is a closer frame timestamp than the start of the loop.
                frame_time = (capture_started+capture_done)/2
                obs, preview = detector.detect(raw)
                detection_done = time.monotonic()
                detector.debug.update(capture_ms=(capture_done-capture_started)*1000,
                                      detect_ms=(detection_done-capture_done)*1000)
                if args.verbose and obs.state != stable_state:
                    print(f"Detected {obs.state}: phase={controller.phase}, active={active}, "
                          f"casts={controller.casts}/{args.max_casts}, ready={detector.debug.get('ready_score', 0):.2f}, "
                          f"bite={detector.debug.get('bite_score', 0):.2f}, "
                          f"panel={bool(detector.debug.get('panel_box'))}", flush=True)
                stable_count = stable_count+1 if obs.state == stable_state else 1
                stable_state = obs.state
                if obs.state == "unknown":
                    unknown_since = started if unknown_since is None else unknown_since
                else:
                    unknown_since = None
                # Waiting for a bite naturally has no recognized UI for a while.
                lost = unknown_since is not None and started-unknown_since > (30 if controller.phase == "waiting" else 5)
                if active and (lost or started-last_progress > args.timeout):
                    active = False
                    print("PAUSED: screen not recognized or progress timeout. Inspect game; F8 resumes.", flush=True)
                # Bite prompts are time-critical; do not wait for three matching frames.
                if active and (obs.state in ("skill", "bite") or stable_count >= 3):
                    action = controller.step(obs, frame_time, time.monotonic()-frame_time)
                    if action:
                        click(region, action.point)
                        last_progress = time.monotonic()
                        recent_action = action
                        recent_action_at = last_progress
                        if args.verbose:
                            print(f"{action.kind}: cast {controller.casts}/{args.max_casts}", flush=True)
                    if controller.finished:
                        active = False
                        print("Cast limit reached. Restart to run another batch.", flush=True)
                f7 = key_down(0x76)
                # Keep visualization work off most capture/control iterations.
                render = (not args.no_preview and started-last_preview >= 1/args.preview_fps) or (f7 and not was_f7)
                if render:
                    preview = draw_overlay(preview, obs, detector.debug, active, controller.casts,
                                       args.max_casts, controller.phase, fps, controller.velocity,
                                       controller.latency + detection_done-frame_time, recent_action if started-recent_action_at < .5 else None,
                                       controller.decision if active else 'paused', controller.skill_clicks)
                    if not args.no_preview:
                        cv2.imshow(title, preview)
                    last_preview = started
                if f7 and not was_f7:
                    directory = ROOT/'captures'
                    directory.mkdir(exist_ok=True)
                    stamp = time.strftime('%Y%m%d-%H%M%S')
                    cv2.imwrite(str(directory/f'{stamp}-raw.png'), cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR))
                    cv2.imwrite(str(directory/f'{stamp}-overlay.png'), preview)
                    (directory/f'{stamp}.json').write_text(json.dumps(dict(
                        state=obs.state, phase=controller.phase, region=region,
                        debug=detector.debug, fps=fps, marker=obs.marker, target=obs.target,
                        decision=controller.decision, armed=controller.armed,
                        skill_clicks=controller.skill_clicks, velocity=controller.velocity,
                        active=active, casts=controller.casts, max_casts=args.max_casts,
                        finished=controller.finished), indent=2))
                    print(f"Diagnostics saved in {directory}", flush=True)
                was_f7 = f7
                if not args.no_preview and (cv2.pollKey() == 27 or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1):
                    break
                time.sleep(max(0, 1/args.control_fps-(time.monotonic()-started)))
        finally:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
