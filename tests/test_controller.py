import unittest

from fishing.controller import Controller
from fishing.vision import Observation


class ControllerTests(unittest.TestCase):
    def test_lingering_skill_frame_after_collect_does_not_block_next_cast(self):
        c = Controller(max_casts=2)
        c.step(Observation('ready'), 0)
        c.step(Observation('bite'), 1)
        c.step(Observation('reward'), 3)
        self.assertEqual(c.phase, 'collecting')
        self.assertIsNone(c.step(Observation('skill', 220, (180, 260)), 3.4))
        self.assertEqual(c.phase, 'collecting')
        self.assertEqual(c.step(Observation('ready'), 4.3).kind, 'cast')
        self.assertEqual(c.casts, 2)

    def test_stable_ready_recovers_from_playing_without_duplicate_cast(self):
        c = Controller(max_casts=3)
        c.phase = 'playing'
        self.assertIsNone(c.step(Observation('ready'), 5))
        self.assertEqual(c.step(Observation('ready'), 5.4).kind, 'cast')
        self.assertIsNone(c.step(Observation('ready'), 7))

    def test_instant_reward_skips_skills_and_returns_to_cast(self):
        c = Controller(max_casts=2)
        self.assertEqual(c.step(Observation('ready'), 0).kind, 'cast')
        self.assertEqual(c.step(Observation('bite'), 1).kind, 'hook')
        reward = Observation('reward', dismiss_point=(.5, .95))
        self.assertIsNone(c.step(reward, 1.1))
        action = c.step(reward, 2.3)
        self.assertEqual(action.kind, 'dismiss')
        self.assertEqual(action.point, (.5, .95))
        self.assertIsNone(c.step(Observation('ready'), 2.4))
        self.assertEqual(c.step(Observation('ready'), 3.6).kind, 'cast')
        self.assertEqual(c.skill_clicks, 0)

    def test_reward_dismisses_at_button_then_waits_before_cast(self):
        c = Controller(max_casts=2)
        c.phase = 'playing'
        action = c.step(Observation('reward'), 5)
        self.assertEqual(action.kind, 'dismiss')
        self.assertEqual(action.point, (.5, .89))
        self.assertIsNone(c.step(Observation('ready'), 5.2))
        self.assertEqual(c.step(Observation('ready'), 6.3).kind, 'cast')

    def test_fast_bite_after_cast(self):
        c = Controller()
        c.step(Observation('ready'), 0)
        self.assertEqual(c.step(Observation('bite'), .2).kind, 'hook')

    def test_cycle_and_limit(self):
        c = Controller(max_casts=1)
        self.assertEqual(c.step(Observation('ready'), 0).kind, 'cast')
        self.assertIsNone(c.step(Observation('ready'), 2))
        self.assertEqual(c.step(Observation('bite'), 3).kind, 'hook')
        self.assertIsNone(c.step(Observation('bite'), 4))
        self.assertEqual(c.step(Observation('reward'), 10).kind, 'dismiss')
        self.assertIsNone(c.step(Observation('ready'), 12))
        self.assertTrue(c.finished)

    def test_one_click_per_crossing(self):
        c = Controller(latency=0)
        target = (180., 260.)
        self.assertIsNone(c.step(Observation('skill', 150, target), 0))
        self.assertEqual(c.step(Observation('skill', 210, target), .1).kind, 'skill')
        self.assertIsNone(c.step(Observation('skill', 220, target), .7))
        self.assertIsNone(c.step(Observation('skill', 280, target), .8))
        self.assertEqual(c.step(Observation('skill', 230, target), .9).kind, 'skill')

    def test_unknown_does_not_click(self):
        c = Controller()
        for t in range(100):
            self.assertIsNone(c.step(Observation(), t))

    def test_prediction_avoids_late_click(self):
        c = Controller(latency=.1)
        c.step(Observation('skill', 170, (180, 220)), 0)
        self.assertIsNone(c.step(Observation('skill', 205, (180, 220)), .05))


if __name__ == '__main__':
    unittest.main()
