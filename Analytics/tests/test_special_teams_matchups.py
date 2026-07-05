"""Behavior tests for the MoneyPuck matchup profile model."""

from __future__ import annotations

import unittest

try:
    import pandas as pd
    from models_v2.special_teams_matchups import SpecialTeamsMatchupModel
except ModuleNotFoundError as exc:
    pd = None
    SpecialTeamsMatchupModel = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


def shot_row(season, shooting_team, defending_team, attack_type, x_goal):
    return {
        "season": season,
        "shooting_team_code": shooting_team,
        "defending_team_code": defending_team,
        "attack_type": attack_type,
        "x_goal": x_goal,
        "goal": False,
        "shot_goalie_froze": False,
        "shot_generated_rebound": False,
        "shot_play_continued_in_zone": False,
        "shot_play_continued_outside_zone": False,
        "shot_angle_rebound_royal_road": False,
        "x_cord_adjusted": 80.0,
        "y_cord_adjusted": 0.0,
    }


class SpecialTeamsMatchupTests(unittest.TestCase):
    def setUp(self):
        if IMPORT_ERROR is not None:
            self.skipTest(f"optional analytics dependency unavailable: {IMPORT_ERROR}")

    def test_league_profile_is_season_scoped(self):
        model = SpecialTeamsMatchupModel(None)
        rows = []
        rows.extend(shot_row(2024, "A", "X", "east_west_seam", 1.0) for _ in range(50))
        rows.extend(shot_row(2024, "B", "Y", "downhill", 1.0) for _ in range(50))
        rows.extend(shot_row(2025, "A", "X", "east_west_seam", 1.0) for _ in range(80))
        rows.extend(shot_row(2025, "B", "Y", "downhill", 1.0) for _ in range(20))
        model.data = pd.DataFrame(rows)

        profile = model._league_profile()
        east_2024 = profile[(profile["season"] == 2024) & (profile["attack_type"] == "east_west_seam")].iloc[0]
        east_2025 = profile[(profile["season"] == 2025) & (profile["attack_type"] == "east_west_seam")].iloc[0]

        self.assertAlmostEqual(east_2024["xg_share"], 0.5)
        self.assertAlmostEqual(east_2025["xg_share"], 0.8)

    def test_team_profiles_use_season_specific_baseline(self):
        model = SpecialTeamsMatchupModel(None)
        rows = []
        rows.extend(shot_row(2025, "A", "X", "east_west_seam", 1.0) for _ in range(80))
        rows.extend(shot_row(2025, "A", "X", "downhill", 1.0) for _ in range(20))
        rows.extend(shot_row(2025, "B", "Y", "east_west_seam", 1.0) for _ in range(20))
        rows.extend(shot_row(2025, "B", "Y", "downhill", 1.0) for _ in range(80))
        model.data = pd.DataFrame(rows)
        model.league_profile = model._league_profile()

        profiles = model._team_profiles("shooting_team_code", "pp_attack")
        team_a_east = profiles[(profiles["team"] == "A") & (profiles["attack_type"] == "east_west_seam")].iloc[0]

        self.assertAlmostEqual(team_a_east["xg_share"], 0.8)
        self.assertAlmostEqual(team_a_east["xg_share_index"], 1.6)


if __name__ == "__main__":
    unittest.main()
