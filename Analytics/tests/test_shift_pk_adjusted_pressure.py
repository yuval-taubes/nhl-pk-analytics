from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "Analytics"))

from diagnostics.shift_pk_adjusted_pressure import shift_age_bucket


class ShiftPkAdjustedPressureTests(unittest.TestCase):
    def test_shift_age_bucket_boundaries(self):
        self.assertEqual(shift_age_bucket(0), "00-29")
        self.assertEqual(shift_age_bucket(30), "30-44")
        self.assertEqual(shift_age_bucket(45), "45-59")
        self.assertEqual(shift_age_bucket(60), "60+")


if __name__ == "__main__":
    unittest.main()
