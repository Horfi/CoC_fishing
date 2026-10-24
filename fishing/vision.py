from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Observation:
    state: str = "unknown"
    marker: float | None = None
    target: tuple[float, float] | None = None
    score: float = 0.0
    dismiss_point: tuple[float, float] | None = None


class Detector:
    """All coordinates use a viewport normalized to 500 x 820 pixels."""

    def __init__(self, assets: Path):
        self.templates = {}
        self.debug = {}
        self.last_target = None
        for name in ("bite", "marker", "ready", "collect-text"):
            img = cv2.imread(str(assets / f"{name}.png"))
            if img is None:
                raise FileNotFoundError(f"Missing template: {assets / name}")
            self.templates[name] = img
        self.bite_templates = [cv2.resize(self.templates['bite'], None, fx=s, fy=s)
                               for s in (.90, .95, 1., 1.05, 1.10)]
        self.marker_gray = cv2.cvtColor(self.templates['marker'], cv2.COLOR_BGR2GRAY)
        self.collect_templates = [cv2.cvtColor(cv2.resize(self.templates['collect-text'], None, fx=s, fy=s), cv2.COLOR_BGR2GRAY)
                                  for s in (.8, .9, 1., 1.1, 1.2)]
        self.collect_white = cv2.imread(str(assets/'collect-white.png'), cv2.IMREAD_GRAYSCALE)
        self.reward_title = cv2.imread(str(assets/'reward-title.png'))
        if self.collect_white is None or self.reward_title is None:
            raise FileNotFoundError('Missing collect-white.png or reward-title.png')

    def match(self, frame, name, rect):
        x, y, w, h = rect
        template = self.templates[name]
        scores = cv2.matchTemplate(frame[y:y+h, x:x+w], template, cv2.TM_CCOEFF_NORMED)
        _, score, _, pos = cv2.minMaxLoc(scores)
        return score, (x + pos[0] + template.shape[1]/2, y + pos[1] + template.shape[0]/2)

    def detect(self, raw):
        # MSS supplies packed BGRA. Let OpenCV drop alpha natively, rather
        # than passing a strided [:, :, :3] view that causes a slow copy.
        if raw.shape[2] == 4:
            raw = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
        frame = cv2.resize(raw, (500, 820))
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        self.debug = {}
        # Collect text takes priority over every gameplay state, independent
        # of the reward title, fish, background brightness, or current phase.
        green = cv2.inRange(hsv[400:820, 40:460], (30, 80, 100), (85, 255, 255))
        joined = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        contours, _ = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if not (130 <= w <= 340 and 25 <= h <= 110 and w/h > 2.2):
                continue
            left, top = max(0, 40+x-8), max(0, 400+y-8)
            right, bottom = min(500, 40+x+w+8), min(820, 400+y+h+8)
            roi = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
            # Normalize by the actual button bounds, including independent X/Y
            # scaling introduced by viewport calibration. Ignore green texture.
            button = cv2.resize(frame[400+y:400+y+h, 40+x:40+x+w], (230, 60))
            white = cv2.inRange(cv2.cvtColor(button, cv2.COLOR_BGR2HSV), (0, 0, 170), (179, 85, 255))
            white_score = cv2.minMaxLoc(cv2.matchTemplate(white, self.collect_white, cv2.TM_CCOEFF_NORMED))[1]
            self.debug['collect_white_score'] = white_score
            score = max((cv2.minMaxLoc(cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED))[1]
                         for template in self.collect_templates
                         if template.shape[0] <= roi.shape[0] and template.shape[1] <= roi.shape[1]), default=0.)
            self.debug['collect_score'] = max(score, self.debug.get('collect_score', 0.))
            fallback = False
            if score > .50 and white_score <= .72 and score <= .68:
                title_score = cv2.minMaxLoc(cv2.matchTemplate(frame[65:240, 60:440], self.reward_title, cv2.TM_CCOEFF_NORMED))[1]
                self.debug['reward_title_score'] = title_score
                fallback = title_score > .72
            if score > .68 or white_score > .72 or fallback:
                self.last_target = None
                point = ((40+x+w/2)/500, (400+y+h/2)/820)
                self.debug['collect_box'] = (40+x, 400+y, w, h)
                self.debug['reward_source'] = 'collect text' if not fallback else 'collect + reward title fallback'
                return Observation('reward', score=score, dismiss_point=point), frame
        # Gold/blue cards require broad side panels and a dimmed backdrop;
        # normal blue water or yellow UI must not trigger a dismissal.
        purple = cv2.inRange(hsv[220:600, 30:470], (125, 100, 90), (165, 255, 255))
        gold = cv2.inRange(hsv[220:600, 30:470], (15, 90, 140), (40, 255, 255))
        gold_fill = float(cv2.countNonZero(gold)/gold.size)
        blue = cv2.inRange(hsv[220:600, 30:470], (90, 110, 140), (120, 255, 255))
        blue_fill = float(cv2.countNonZero(blue)/blue.size)
        is_gold = False
        is_blue = False
        # The red card fades into orange at its bottom edge.
        panel_hsv = hsv[220:600, 30:470]
        red = cv2.bitwise_or(cv2.inRange(panel_hsv, (0, 100, 140), (22, 255, 255)),
                            cv2.inRange(panel_hsv, (170, 100, 140), (179, 255, 255)))
        red_fill = cv2.countNonZero(red)/red.size
        is_red = False
        if gold_fill > .48 or blue_fill > .48 or red_fill > .48:
            dim_top = float(np.median(hsv[45:180:4, 30:470:4, 2])) < 165
            dim_bottom = float(np.median(hsv[710:800:4, 30:470:4, 2])) < 150
            gold_sides = min(np.mean(gold[70:300, :45] > 0), np.mean(gold[70:300, -45:] > 0))
            is_gold = gold_sides > .65 and dim_top and dim_bottom
            blue_sides = min(np.mean(blue[70:300, :45] > 0), np.mean(blue[70:300, -45:] > 0))
            is_gold = is_gold and gold_fill > .48
            is_blue = blue_fill > .48 and blue_sides > .65 and dim_top and dim_bottom
            red_sides = min(np.mean(red[70:300, :45] > 0), np.mean(red[70:300, -45:] > 0))
            is_red = red_fill > .48 and red_sides > .65 and dim_top and dim_bottom
        self.debug.update(reward_gold_fill=gold_fill, reward_blue_fill=blue_fill, reward_red_fill=red_fill)
        if cv2.countNonZero(purple)/purple.size > .52 or is_gold or is_blue or is_red:
            self.last_target = None
            return Observation("reward"), frame
        # Skill checks are the time-critical path. Avoid five text searches here.
        skill = self.detect_skill(frame, hsv)
        if skill is not None:
            return skill, frame
        # Text alone is brittle when viewport calibration differs by a few pixels.
        # Search several scales, and independently recognize the purple prompt panel.
        best = (-1., (0, 0, 0, 0))
        for template in self.bite_templates:
            scores = cv2.matchTemplate(frame[485:635, 75:425], template, cv2.TM_CCOEFF_NORMED)
            _, score, _, pos = cv2.minMaxLoc(scores)
            if score > best[0]:
                best = (score, (75+pos[0], 485+pos[1], template.shape[1], template.shape[0]))
        score, rect = best
        self.debug.update(bite_score=score, bite_box=rect)
        panel_mask = cv2.inRange(hsv[485:635, 75:425], (115, 75, 90), (165, 255, 255))
        joined = cv2.morphologyEx(panel_mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        contours, _ = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        panel = None
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            fill = cv2.countNonZero(panel_mask[y:y+h, x:x+w])/(w*h)
            if 210 <= w <= 310 and 45 <= h <= 115 and fill > .40:
                panel = (75+x, 485+y, w, h)
                break
        button_purple = np.mean(cv2.inRange(hsv[675:775, 195:305], (120, 100, 100), (165, 255, 255)) > 0)
        self.debug.update(panel_box=panel, button_purple=float(button_purple))
        if score > .68 or (panel is not None and button_purple > .25):
            self.last_target = None
            return Observation("bite", score=score), frame
        score, _ = self.match(frame, "ready", (130, 640, 240, 170))
        self.debug['ready_score'] = score
        green = cv2.inRange(hsv[690:770, 195:305], (30, 100, 100), (85, 255, 255))
        if score > .68 and cv2.countNonZero(green)/green.size > .2:
            self.last_target = None
            return Observation("ready", score=score), frame
        return Observation(), frame

    def detect_skill(self, frame, hsv):
        # One-channel matching on a small region preserves the marker silhouette
        # while avoiding the cost of matching all three color channels.
        roi = cv2.cvtColor(frame[545:645, 105:405], cv2.COLOR_BGR2GRAY)
        scores = cv2.matchTemplate(roi, self.marker_gray, cv2.TM_CCOEFF_NORMED)
        _, score, _, found = cv2.minMaxLoc(scores)
        pos = (105+found[0]+self.marker_gray.shape[1]/2,
               545+found[1]+self.marker_gray.shape[0]/2)
        self.debug.update(marker_score=score, marker_candidate=pos)
        if score <= .65:
            return None
        yellow = cv2.inRange(hsv[587:607, 130:375], (18, 130, 160), (40, 255, 255))
        columns = np.count_nonzero(yellow, axis=0) >= 8
        target = self.track_target(columns, pos[0])
        if target is None:
            return None
        self.debug.update(target=target, marker=pos[0])
        return Observation("skill", pos[0], target, score)

    def track_target(self, columns, marker):
        """Keep the yellow interval intact when the float hides its pixels."""
        xs = np.arange(130, 375)
        visible = np.abs(xs-marker) > 22
        if self.last_target is not None:
            a, b = self.last_target
            expected = (xs >= a) & (xs < b)
            # Retain an old edge only if all changes are explained by occlusion.
            if np.count_nonzero((expected != columns) & visible) <= 4:
                self.debug['target_source'] = 'tracked through marker'
                return self.last_target
        edges = np.diff(np.r_[False, columns, False].astype(int))
        runs = [(int(a+130), int(b+130)) for a, b in
                zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)) if b-a >= 3]
        merged = []
        for a, b in runs:
            if merged and 0 <= a-merged[-1][1] <= 44 and merged[-1][1]-3 <= marker <= a+3:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        merged = [(a, b) for a, b in merged if b-a >= 10]
        if not merged:
            return None
        a, b = max(merged, key=lambda r: r[1]-r[0])
        self.last_target = (float(a), float(b))
        self.debug['target_source'] = 'visible / bridged marker gap'
        return self.last_target
