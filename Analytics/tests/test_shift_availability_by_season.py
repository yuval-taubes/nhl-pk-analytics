from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "Analytics"))

from diagnostics.scan_shift_availability_by_season import evenly_spaced_indices, summarize


class ShiftAvailabilityBySeasonTests(unittest.TestCase):
    def test_evenly_spaced_indices_include_both_ends(self):
        self.assertEqual(evenly_spaced_indices(10, 3), [0, 4, 9])

    def test_summary_keeps_seasons_separate(self):
        rows = [
            {"season": "20222023", "status": "covered"},
            {"season": "20222023", "status": "missing"},
            {"season": "20232024", "status": "error"},
        ]
        result = summarize(rows)
        self.assertEqual(result[0]["coverage_rate"], "50.0%")
        self.assertEqual(result[1]["errors"], 1)


if __name__ == "__main__":
    unittest.main()
