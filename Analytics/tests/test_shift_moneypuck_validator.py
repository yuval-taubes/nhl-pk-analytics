"""Regression tests for shift/MoneyPuck validator guardrails."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "Analytics"))

from diagnostics.validate_shift_and_moneypuck_alignment import shift_validation_status


class ShiftValidatorStatusTests(unittest.TestCase):
    def test_pass_uses_model_safe_mismatch_rate_not_all_event_noise(self):
        self.assertEqual(
            shift_validation_status(
                events=2854,
                manpower_rows=2854,
                model_safe_mismatch_rate=0.0082,
            ),
            "PASS",
        )

    def test_review_when_manpower_coverage_is_incomplete(self):
        self.assertEqual(
            shift_validation_status(
                events=2854,
                manpower_rows=2853,
                model_safe_mismatch_rate=0.0,
            ),
            "REVIEW",
        )

    def test_review_when_model_safe_mismatch_rate_exceeds_threshold(self):
        self.assertEqual(
            shift_validation_status(
                events=1000,
                manpower_rows=1000,
                model_safe_mismatch_rate=0.021,
            ),
            "REVIEW",
        )


if __name__ == "__main__":
    unittest.main()
