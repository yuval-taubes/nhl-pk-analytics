"""Lightweight source-contract tests that run without a database.

The DB-backed diagnostics cover the real data. These tests make sure the most
important guardrails added for portfolio readiness do not accidentally disappear.
"""

from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[2]


class StaticContractTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_xg_backfill_uses_scoped_possession_update(self):
        source = self.read("Analytics/models/xg_model.py")
        self.assertIn("SET xg_sum = agg.xg_sum", source)
        self.assertIn("WHERE p.possession_id = agg.possession_id", source)
        self.assertIn("Set {zeroed} shotless possessions to zero xG", source)

    def test_xg_training_exports_fixed_bin_calibration(self):
        source = self.read("Analytics/models/xg_model.py")
        self.assertIn("'calibration_bins': calibration_bins", source)
        self.assertIn("'predicted_goals_test': predicted_total", source)
        self.assertIn("'actual_goals_test': actual_total", source)

    def test_entry_attempt_windows_are_capped(self):
        source = self.read("Analytics/models/model1_entry_attempts.py")
        self.assertIn("prev_candidate_time", source)
        self.assertIn("next_candidate_event_idx", source)
        self.assertIn("shot_event.event_idx < c.next_candidate_event_idx", source)

    def test_api_missing_numbers_do_not_render_as_zero(self):
        source = self.read("NhlPkApi/Program.cs")
        self.assertIn("static double? NumberValue", source)
        self.assertIn('return "N/A";', source)

    def test_golden_game_fixture_shape(self):
        fixture = json.loads(
            self.read("Analytics/diagnostics/golden_games/2022020154.json")
        )
        self.assertEqual(fixture["summary"]["game_id"], 2022020154)
        self.assertGreater(fixture["summary"]["events"], 250)
        self.assertGreater(fixture["summary"]["shots"], 40)
        self.assertGreater(fixture["summary"]["special_teams_possessions"], 0)


if __name__ == "__main__":
    unittest.main()
