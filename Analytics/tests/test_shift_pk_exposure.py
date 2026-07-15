"""Regression tests for shift-covered PK exposure helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "Analytics"))

from diagnostics.shift_pk_exposure import NON_GOAL_SHOT_EVENTS, SHOT_ATTEMPT_EVENTS, shift_age_bucket


class ShiftPkExposureTests(unittest.TestCase):
    def test_shift_age_bucket_boundaries(self):
        self.assertEqual(shift_age_bucket(None), "unknown")
        self.assertEqual(shift_age_bucket(0), "00-29")
        self.assertEqual(shift_age_bucket(29.9), "00-29")
        self.assertEqual(shift_age_bucket(30), "30-44")
        self.assertEqual(shift_age_bucket(44.9), "30-44")
        self.assertEqual(shift_age_bucket(45), "45-59")
        self.assertEqual(shift_age_bucket(59.9), "45-59")
        self.assertEqual(shift_age_bucket(60), "60+")

    def test_goal_events_are_not_shift_age_bucket_inputs(self):
        self.assertNotIn("goal", NON_GOAL_SHOT_EVENTS)
        self.assertIn("goal", SHOT_ATTEMPT_EVENTS)


if __name__ == "__main__":
    unittest.main()
