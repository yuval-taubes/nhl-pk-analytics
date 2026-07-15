from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "Analytics"))

from diagnostics.audit_shift_possession_coverage import coverage_status


class ShiftPossessionCoverageTests(unittest.TestCase):
    def test_coverage_status_gates(self):
        self.assertEqual(coverage_status(0.8, 0.01), "SUITABLE")
        self.assertEqual(coverage_status(0.6, 0.02), "PARTIAL")
        self.assertEqual(coverage_status(0.49, 0), "INSUFFICIENT")
        self.assertEqual(coverage_status(0.9, 0.04), "INSUFFICIENT")


if __name__ == "__main__":
    unittest.main()
