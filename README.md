# BlueStacks fishing automation

Windows + Python 3.11 or newer. Uses local screen capture, OpenCV and mouse clicks. The game must stay visible and unobscured. Supports the Polish fishing event in portrait mode.

## Start

```powershell
.\setup.ps1
.\run.ps1 -Calibrate -MaxCasts 1
```

If PowerShell blocks local scripts, invoke `powershell -ExecutionPolicy Bypass -File .\setup.ps1` and likewise for `run.ps1`; this changes policy only for that process.

Select the **game viewport only**: from below the BlueStacks title bar to just above the bottom black strip containing the X. Exclude advertisements and the right emulator toolbar. Press Enter. This saves `config.json`. Keep the same window size and position afterward; recalibrate whenever either changes.

The app starts in **watch-only mode**. Put its preview beside the game so it cannot obstruct capture. Check that it identifies `ready`, `bite`, `skill`, and `reward` appropriately.

The preview includes diagnostic overlays:

- Green/purple mesh over the button when its corresponding state is detected; the crosshair is the configured click destination, not a detected button boundary.
- A faint rectangle shows where the bite prompt is searched for; pink mesh marks a recognized panel or text match.
- Orange mesh shows the skill target, green outlines its safe interior, and white marks the float. While running, cyan marks the predicted float position.
- A yellow crosshair flashes for half a second at an actual click; reward dismissal has its own crosshair.
- The header shows state, controller phase, FPS, bite match score and whether the purple prompt panel was detected. Unknown states still show the inactive button position in gray.
- During skill checks, the header shows the number of skill clicks sent and why the controller is waiting. This counts input sent, not successful checks; manually completed checks do not increase it.

The detector joins yellow fragments hidden behind the float and tracks occluded target edges across frames. The preview updates at most 10 times per second by default, while capture and click decisions run at up to 60 iterations per second. Preview drawing shares the loop but runs less often. The displayed FPS refers to that control loop, not game rendering. `-PreviewFps 5` reduces display work further; `-ControlFps 90` raises the loop cap but cannot overcome capture or processing limits.

Bite recognition uses multiple text scales and a separate purple-panel-plus-purple-button check. Recognized bites trigger without waiting for three frames.

- **F8** enables or pauses clicking (global hotkey).
- **F9 / Escape** exits (global hotkeys); closing the preview also exits.
- **F7** saves the raw frame, annotated preview and detection details under `captures/` for troubleshooting.
- Default limit: 10 casts. Start with one; then ` .\run.ps1 -MaxCasts 10`.
- Unknown screens and stalled progress pause automation; inspect the game before resuming.
- Purple, gold, blue, and red reward panels are recognized and dismissed at the usual green/purple button position. The controller waits for the ready screen and a 1.2-second cooldown before casting again.
- Instant catches can skip skill checks entirely. The script looks for the “Odbierz teraz” text on a green rectangular button before checking any gameplay state, regardless of fish, title, or backdrop. It clicks that button and waits for the normal ready screen.
- After dismissal, a dedicated collecting phase ignores lingering skill-bar frames until ready returns. A stable ready screen also resynchronizes a controller left in playing after a missed/manual dismissal. Cast limits and manual pause still apply.

Do not move/use the mouse over other apps during a run: clicks use the desktop pointer. Keep BlueStacks in front and disable screensavers. Do not minimize or resize it mid-run.

## Timing and limitations

Routine detection and click printing is disabled by default. Startup, pause, completion, and diagnostic-save messages remain visible. Use `-DebugLog` (or Python `--verbose`) when troubleshooting to restore the detailed console output.

The controller estimates the float's velocity and predicts where it will be when a click lands. `-LatencyMs 35` is an initial estimate, not a measured property of your PC. Tune in small increments after observing single-cast trials. It aims inside the yellow/orange band; it does not yet distinguish an inner perfect-score band. A latch prevents repeated clicks during one target crossing.

For less rendering overhead, run ` .\run.ps1 -NoPreview`. This skips the preview window entirely; F8 still starts/pauses, F9/Escape exits, and F7 still saves a diagnostic image with overlays. Calibration still displays its selection window when needed. Without a preview, use the terminal messages to follow actions. Normal mode keeps the visual overlay.

Prediction includes the measured age of the captured frame as well as the configured click latency. More control FPS gives fresher positions and improves speed estimates; prediction cannot replace observations during sudden reversals or resets. F7 diagnostics include capture and detection milliseconds to identify the actual bottleneck. Live FPS depends on desktop capture and emulator load, not just the loop cap.

No OCR, network requests, or game memory access is used. Visual templates are stored in `assets/`. Different themes, languages, UI layouts, or result dialogs may need updated detection. The cast limit counts casts initiated by this process; it does not persist across restarts.

Static screenshot checks and controller tests do not prove live timing. Calibrate and validate a full single-cast run before leaving a batch running.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
