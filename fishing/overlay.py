"""Diagnostic drawing on the preview only; never modifies the captured game."""
import cv2
import numpy as np

_Y, _X = np.indices((820, 500))
_HATCH = ((_X-_Y) % 14 == 0)


def mesh(image, mask, color):
    x, y, w, h = cv2.boundingRect(mask)
    if not w or not h:
        return
    roi = image[y:y+h, x:x+w]
    selected = mask[y:y+h, x:x+w] > 0
    tint = roi.copy()
    tint[selected] = color
    cv2.addWeighted(tint, .20, roi, .80, 0, dst=roi)
    roi[selected & _HATCH[y:y+h, x:x+w]] = color


def crosshair(image, point, color, radius=12):
    x, y = point
    cv2.circle(image, point, radius, color, 2)
    cv2.line(image, (x-radius-6, y), (x+radius+6, y), color, 2)
    cv2.line(image, (x, y-radius-6), (x, y+radius+6), color, 2)


def text(image, label, point, color=(255, 255, 255), size=.46):
    cv2.putText(image, label, point, cv2.FONT_HERSHEY_SIMPLEX, size, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(image, label, point, cv2.FONT_HERSHEY_SIMPLEX, size, color, 1, cv2.LINE_AA)


def draw_overlay(frame, obs, debug, active, casts, max_casts, phase, fps,
                 velocity=0., latency=.035, recent_action=None, decision='', skill_clicks=0):
    image = frame.copy()
    button = (250, round(.89*820))
    color = (70, 255, 70) if obs.state == 'ready' else (255, 80, 230)
    known_button = obs.state in ('ready', 'bite', 'skill')
    mask = np.zeros(image.shape[:2], np.uint8)
    if known_button:
        cv2.circle(mask, button, 62, 255, -1)
        mesh(image, mask, color)
    else:
        color = (150, 150, 150)
    cv2.circle(image, button, 62, color, 2)
    crosshair(image, button, color)
    label = {'ready': 'CAST click point', 'bite': 'PULL click point',
             'skill': 'SKILL click point'}.get(obs.state, 'Button position (inactive)')
    text(image, label, (145, 810), color)

    # Outline the search region even when the prompt is not recognized.
    cv2.rectangle(image, (75, 485), (425, 635), (180, 130, 180), 1)
    text(image, 'Bite prompt search', (78, 480), (220, 170, 220))
    box = debug.get('panel_box') or (debug.get('bite_box') if obs.state == 'bite' else None)
    if box:
        x, y, w, h = box
        mask[:] = 0
        mask[y:y+h, x:x+w] = 255
        mesh(image, mask, (255, 120, 200))
        cv2.rectangle(image, (x, y), (x+w, y+h), (255, 120, 200), 2)

    if obs.target:
        a, b = map(round, obs.target)
        mask[:] = 0
        mask[587:607, a:b] = 255
        mesh(image, mask, (0, 180, 255))
        cv2.rectangle(image, (a, 586), (b, 608), (0, 180, 255), 2)
        margin = round(min(10, (b-a)*.2))
        cv2.rectangle(image, (a+margin, 589), (b-margin, 605), (70, 255, 70), 1)
        x = round(obs.marker)
        cv2.line(image, (x, 552), (x, 630), (255, 255, 255), 2)
        text(image, 'marker', (max(0, min(440, x-20)), 548))
        if active:
            predicted = max(0, min(499, round(obs.marker+velocity*latency)))
            cv2.line(image, (predicted, 565), (predicted, 620), (255, 255, 0), 2)
        text(image, 'Orange: target / green: safe interior', (105, 652), (0, 210, 255), .40)
    if obs.state == 'reward':
        point = tuple(round(v*s) for v, s in zip(obs.dismiss_point, (500, 820))) if obs.dismiss_point else button
        crosshair(image, point, (0, 255, 255), 18)
        text(image, 'DISMISS click point', (155, point[1]-35), (0, 255, 255), .4)
    if recent_action:
        point = tuple(round(n*s) for n, s in zip(recent_action.point, (500, 820)))
        crosshair(image, point, (0, 255, 255), 28)
        text(image, 'CLICKED: '+recent_action.kind, (145, 675), (0, 255, 255))

    cv2.rectangle(image, (0, 0), (500, 92), (20, 20, 20), -1)
    text(image, f"{'RUN' if active else 'WATCH - no clicks'} | {obs.state} | {casts}/{max_casts}", (8, 20), size=.53)
    text(image, f"Phase: {phase} | {fps:.0f} FPS | F7 save diagnostics", (8, 43))
    if obs.state == 'skill':
        text(image, f'Skill clicks sent: {skill_clicks} | {decision}', (8, 64), size=.42)
        text(image, f"Target {obs.target[0]:.0f}..{obs.target[1]:.0f} | marker {obs.marker:.0f}", (8, 84), size=.43)
    else:
        text(image, f"Bite match: {debug.get('bite_score', 0):.2f} / 0.68 | panel: {'yes' if debug.get('panel_box') else 'no'}", (8, 64))
        text(image, 'Mesh = detected UI | crosshair = click destination', (8, 84), size=.43)
    return image
