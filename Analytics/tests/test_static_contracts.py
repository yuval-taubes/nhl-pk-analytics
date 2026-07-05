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

    def test_moneypuck_v2_uses_season_scoped_shot_key(self):
        schema = self.read("Analytics/moneypuck/schema.sql")
        importer = self.read("Analytics/moneypuck/import_moneypuck.py")
        self.assertIn("PRIMARY KEY (season, game_id, shot_id)", schema)
        self.assertIn("shot_id", importer)
        self.assertIn("strength_state", importer)

    def test_moneypuck_v2_models_credit_source_and_keep_old_runner_separate(self):
        runner = self.read("Analytics/run_models_v2.py")
        models = self.read("Analytics/models_v2/moneypuck_pk_models.py")
        self.assertIn("https://www.moneypuck.com/data.htm", runner)
        self.assertIn("models_v2_run_", runner)
        self.assertIn("Blocked-Shot Aftershock", models)
        self.assertIn("Puck Movement Geometry", models)

    def test_moneypuck_v2_scouting_has_talent_and_similarity_layer(self):
        runner = self.read("Analytics/run_models_v2.py")
        api = self.read("NhlPkApi/Program.cs")
        frontend = self.read("Frontend/src/data/dashboard.ts")
        self.assertIn("BayesianPkPlayerEvaluationModel", runner)
        self.assertIn("trustedPkImpact", api)
        self.assertIn("playerSimilarityGroups", api)
        self.assertIn("PkTalentRow", frontend)
        self.assertIn("PlayerSimilarityGroup", frontend)

    def test_moneypuck_source_discovery_is_separate_from_db_import(self):
        config = self.read("Analytics/moneypuck/config.py")
        importer = self.read("Analytics/moneypuck/import_moneypuck.py")
        self.assertIn("MONEYPUCK_FILE_GROUPS", config)
        self.assertIn("describe_moneypuck_sources", config)
        self.assertIn("validate_moneypuck_freshness", config)
        self.assertIn("--describe-sources", importer)
        self.assertIn("from config import DB_CONFIG", importer)
        self.assertLess(importer.index("describe_moneypuck_sources()"), importer.index("from config import DB_CONFIG"))
        self.assertIn("ON CONFLICT ({\", \".join(conflict_keys)})", importer)
        self.assertIn("DO UPDATE SET", importer)

    def test_special_teams_matchup_model_is_split_from_core_models(self):
        runner = self.read("Analytics/run_models_v2.py")
        api = self.read("NhlPkApi/Program.cs")
        frontend = self.read("Frontend/src/data/dashboard.ts")
        special = self.read("Analytics/models_v2/special_teams_matchups.py")
        core = self.read("Analytics/models_v2/moneypuck_pk_models.py")
        self.assertIn("from models_v2.special_teams_matchups import SpecialTeamsMatchupModel", runner)
        self.assertIn("matchupCards", api)
        self.assertIn("leaguePkDangerHeatmap", api)
        self.assertIn("teamShotMaps", api)
        self.assertIn("export type MatchupCard", frontend)
        self.assertIn("leaguePkDangerHeatmap?: HeatmapBin[]", frontend)
        self.assertIn("teamShotMaps?: TeamShotMapBin[]", frontend)
        self.assertIn("class SpecialTeamsMatchupModel", special)
        self.assertNotIn("class SpecialTeamsMatchupModel", core)
        self.assertIn('set_index(["season", "attack_type"])', special)
        self.assertIn('team_totals = self.data.groupby(["season", team_col])', special)
        self.assertIn('"team_shot_maps": records(self._team_shot_maps())', special)

    def test_player_tagging_is_backend_owned_and_auditable(self):
        runner = self.read("Analytics/run_models_v2.py")
        api = self.read("NhlPkApi/Program.cs")
        frontend = self.read("Frontend/src/data/dashboard.ts")
        tags = self.read("Analytics/models_v2/player_tags.py")
        self.assertIn("from models_v2.player_tags import PlayerTaggingModel", runner)
        self.assertIn("playerTagProfiles", api)
        self.assertIn("playerTagDictionary", api)
        self.assertIn("export type PlayerTag", frontend)
        self.assertIn("tag_id", tags)
        self.assertIn("sample_size_note", tags)
        self.assertIn("caveat", tags)
        self.assertIn("source_lineage", tags)
        self.assertNotIn("rebound_cleanup", tags)

    def test_api_uses_filename_timestamp_for_latest_run_selection(self):
        api = self.read("NhlPkApi/Program.cs")
        self.assertIn("RunTimestamp(file) ?? file.LastWriteTimeUtc", api)
        self.assertIn("DateTime.TryParseExact", api)
        self.assertIn('"yyyyMMdd_HHmmss"', api)


if __name__ == "__main__":
    unittest.main()
