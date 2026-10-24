from pathlib import Path
import unittest

import cv2
import numpy as np

from fishing.vision import Detector
from fishing.overlay import draw_overlay


class VisionTests(unittest.TestCase):
    def test_red_reward_screenshot(self):
        frame = cv2.imread(str(Path(__file__).parent/'fixtures/reward-red.png'))
        self.assertEqual(self.detector.detect(frame)[0].state, 'reward')

    def test_red_scene_without_dim_backdrop_is_not_reward(self):
        frame = np.full((820, 500, 3), (40, 60, 240), np.uint8)
        self.assertNotEqual(self.detector.detect(frame)[0].state, 'reward')

    def test_packed_capture_matches_bgr_for_all_saved_screens(self):
        for path in (Path(__file__).parent/'fixtures').glob('*.png'):
            with self.subTest(screen=path.name):
                raw = cv2.imread(str(path))
                a = Detector(Path(__file__).resolve().parents[1]/'assets')
                b = Detector(Path(__file__).resolve().parents[1]/'assets')
                expected, frame = a.detect(raw)
                actual, packed_frame = b.detect(cv2.cvtColor(raw, cv2.COLOR_BGR2BGRA))
                self.assertEqual(expected, actual)
                np.testing.assert_array_equal(frame, packed_frame)

    def test_missed_live_collect_diagnostics(self):
        for name in ('reward-collect-blue.png', 'reward-collect-purple.png'):
            with self.subTest(name=name):
                frame = cv2.imread(str(Path(__file__).parent/'fixtures'/name))
                obs, _ = self.detector.detect(frame)
                self.assertEqual(obs.state, 'reward')
                self.assertIsNotNone(obs.dismiss_point)

    def test_unlabelled_green_rectangle_is_not_collect(self):
        frame = np.zeros((820, 500, 3), np.uint8)
        cv2.rectangle(frame, (135, 750), (365, 810), (40, 210, 100), -1)
        self.assertNotEqual(self.detector.detect(frame)[0].state, 'reward')

    def test_collect_text_overrides_skill_detection_for_both_fish(self):
        from unittest.mock import patch
        for name in ('reward-instant.png', 'reward-instant-red.png'):
            frame = cv2.imread(str(Path(__file__).parent/'fixtures'/name))
            # Neither the title nor the fish/background should be required.
            frame[:700] = (220, 180, 100)
            with self.subTest(name=name), patch.object(self.detector, 'detect_skill', side_effect=AssertionError('Collect must win')):
                obs, _ = self.detector.detect(frame)
                self.assertEqual(obs.state, 'reward')
                self.assertIsNotNone(obs.dismiss_point)

    def test_instant_reward_has_collect_button_destination(self):
        frame = cv2.imread(str(Path(__file__).parent/'fixtures/reward-instant.png'))
        obs, _ = self.detector.detect(frame)
        self.assertEqual(obs.state, 'reward')
        self.assertIsNotNone(obs.dismiss_point)
        self.assertTrue(.45 < obs.dismiss_point[0] < .55)
        self.assertTrue(.92 < obs.dismiss_point[1] < .98)

    def test_blue_reward_screenshot(self):
        frame = cv2.imread(str(Path(__file__).parent/'fixtures/reward-blue.png'))
        self.assertEqual(self.detector.detect(frame)[0].state, 'reward')

    def test_blue_scene_without_dim_backdrop_is_not_reward(self):
        frame = np.full((820, 500, 3), (240, 140, 50), np.uint8)
        self.assertNotEqual(self.detector.detect(frame)[0].state, 'reward')

    def test_gold_reward_screenshot(self):
        frame = cv2.imread(str(Path(__file__).parent/'fixtures/reward-gold.png'))
        self.assertEqual(self.detector.detect(frame)[0].state, 'reward')

    def test_gold_scene_without_dim_backdrop_is_not_reward(self):
        frame = np.full((820, 500, 3), (30, 180, 250), np.uint8)
        self.assertNotEqual(self.detector.detect(frame)[0].state, 'reward')

    def setUp(self):
        self.detector = Detector(Path(__file__).resolve().parents[1]/'assets')

    def test_bite_at_different_text_scales(self):
        for scale in (.9, 1., 1.1):
            with self.subTest(scale=scale):
                frame = np.full((820, 500, 3), (220, 180, 100), np.uint8)
                text = cv2.resize(self.detector.templates['bite'], None, fx=scale, fy=scale)
                h, w = text.shape[:2]
                frame[540:540+h, 130:130+w] = text
                obs, _ = self.detector.detect(frame)
                self.assertEqual(obs.state, 'bite')

    def test_panel_fallback_requires_button(self):
        frame = np.full((820, 500, 3), (220, 180, 100), np.uint8)
        cv2.rectangle(frame, (115, 530), (385, 610), (210, 50, 150), -1)
        self.assertNotEqual(self.detector.detect(frame)[0].state, 'bite')
        cv2.circle(frame, (250, 730), 65, (210, 50, 150), -1)
        self.assertEqual(self.detector.detect(frame)[0].state, 'bite')

    def test_button_alone_is_not_bite(self):
        frame = np.full((820, 500, 3), (220, 180, 100), np.uint8)
        cv2.circle(frame, (250, 730), 65, (210, 50, 150), -1)
        self.assertNotEqual(self.detector.detect(frame)[0].state, 'bite')

    def test_overlay_does_not_modify_capture(self):
        frame = np.full((820, 500, 3), 30, np.uint8)
        obs, _ = self.detector.detect(frame)
        result = draw_overlay(frame, obs, self.detector.debug, False, 0, 1, 'ready', 60)
        self.assertTrue(np.all(frame == 30))
        self.assertFalse(np.array_equal(frame, result))

    def test_real_marker_inside_target_can_trigger_click(self):
        from fishing.controller import Controller
        frame = cv2.imread(str(Path(__file__).parent/'fixtures/marker-inside.png'))
        obs, _ = self.detector.detect(frame)
        self.assertEqual(obs.state, 'skill')
        self.assertAlmostEqual(obs.target[0], 213, delta=2)
        self.assertAlmostEqual(obs.target[1], 319, delta=2)
        self.assertEqual(Controller().step(obs, 1).kind, 'skill')

    def test_real_target_edges_stay_stable_under_marker(self):
        fixtures = Path(__file__).parent/'fixtures'
        observed = []
        for name in ('marker-outside.png', 'marker-inside.png', 'marker-edge.png'):
            obs, _ = self.detector.detect(cv2.imread(str(fixtures/name)))
            self.assertEqual(obs.state, 'skill')
            observed.append(obs.target)
        self.assertEqual(observed[0], observed[1])
        self.assertEqual(observed[0], observed[2])

    def test_changed_target_is_not_kept_from_previous_check(self):
        cols = np.zeros(245, bool)
        cols[80:190] = True
        self.detector.track_target(cols, 150)
        cols[:] = False
        cols[20:70] = True
        self.assertEqual(self.detector.track_target(cols, 350), (150., 200.))
