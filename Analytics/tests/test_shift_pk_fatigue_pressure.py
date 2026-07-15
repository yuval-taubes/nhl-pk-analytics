from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "Analytics"))

from diagnostics.shift_pk_fatigue_pressure import trust_label, wilson_interval


class ShiftPkFatiguePressureTests(unittest.TestCase):
    def test_trust_label_boundary(self):
        self.assertEqual(trust_label(99), "small_sample")
        self.assertEqual(trust_label(100), "descriptive")

    def test_wilson_interval_contains_observed_rate(self):
        low, high = wilson_interval(25, 100)
        self.assertLess(low, 25)
        self.assertGreater(high, 25)

    def test_wilson_interval_handles_empty_sample(self):
        self.assertEqual(wilson_interval(0, 0), (None, None))


if __name__ == "__main__":
    unittest.main()
