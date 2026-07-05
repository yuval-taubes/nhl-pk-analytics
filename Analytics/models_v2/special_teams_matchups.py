"""PP attack, PK leak, matchup, and heat-map profiles from MoneyPuck shots."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from models.model_utils import add_timestamp, export_json
from models_v2.common import records
from moneypuck.features import PK_SHOTS_AGAINST_WHERE, add_movement_bucket, rate, summarize_shots


logger = logging.getLogger(__name__)


class SpecialTeamsMatchupModel:
    """Build PP attack and PK leak profiles from MoneyPuck shot geometry."""

    ATTACK_LABELS = {
        "rebound": "net_front_rebound",
        "east_west": "east_west_seam",
        "north_south_downhill": "downhill",
        "diagonal": "diagonal_seam",
        "small_area": "bumper_slot",
        "point_reset_backtrack": "point_reset",
        "slow_reset": "reset",
        "unknown": "unknown",
    }

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = pd.DataFrame()
        self.league_profile = pd.DataFrame()

    def fetch_data(self):
        query = f"""
        SELECT
            season,
            game_id,
            defending_team_code,
            shooting_team_code,
            x_goal,
            goal,
            shot_goalie_froze,
            shot_generated_rebound,
            shot_play_continued_in_zone,
            shot_play_continued_outside_zone,
            shot_rebound,
            shot_rush,
            shot_angle_rebound_royal_road,
            shot_angle_plus_rebound_speed,
            x_cord_adjusted,
            y_cord_adjusted,
            last_event_x_cord_adjusted,
            last_event_y_cord_adjusted,
            time_since_last_event,
            last_event_category
        FROM mp_shots
        WHERE {PK_SHOTS_AGAINST_WHERE}
          AND x_goal IS NOT NULL
          AND shooting_team_code IS NOT NULL
          AND defending_team_code IS NOT NULL
        """
        logger.info("Fetching MoneyPuck PK shots for special-teams matchup model...")
        self.data = add_movement_bucket(self.db.query_to_df(query))
        self.data["attack_type"] = self.data["movement_bucket"].map(self.ATTACK_LABELS).fillna("unknown")
        logger.info("Special-teams matchup rows: %s", len(self.data))
        return self.data

    def run(self):
        self.fetch_data()
        self.league_profile = self._league_profile()
        pp_profiles = self._team_profiles("shooting_team_code", "pp_attack")
        pk_profiles = self._team_profiles("defending_team_code", "pk_leak")

        results = add_timestamp(
            {
                "model": "MoneyPuck Special Teams Matchup Profiles",
                "league_attack_types": records(self.league_profile),
                "pp_attack_profiles": records(pp_profiles),
                "pk_leak_profiles": records(pk_profiles),
                "matchup_cards": records(self._matchups(pp_profiles, pk_profiles)),
                "league_pk_danger_heatmap": records(self._heatmap_bins(self.data)),
                "team_shot_maps": records(self._team_shot_maps()),
                "sample": {
                    "pk_shots_against": int(len(self.data)),
                    "heatmap_minimum_bin_shots": 25,
                    "team_shot_map_minimum_bin_shots": 8,
                    "minimum_team_type_shots": 40,
                    "minimum_matchup_component_shots": 40,
                },
                "caveats": [
                    "Attack and leak profiles are inferred from shot and last-event geometry, not tracking data or manually tagged formations.",
                    "The matchup score compares style fit: a PP creation tendency against a PK allowed-danger tendency.",
                    "Heat-map coordinates use adjusted MoneyPuck shot locations and are aggregated before export.",
                ],
            }
        )
        results["sample"]["heatmap_bins"] = len(results["league_pk_danger_heatmap"])
        results["sample"]["team_shot_map_bins"] = len(results["team_shot_maps"])
        results["output_file"] = export_json(results, "model_v2_special_teams_matchups.json")
        return results

    def _league_profile(self):
        rows = []
        if self.data.empty:
            return pd.DataFrame()

        season_totals = self.data.groupby("season").agg(
            season_xg=("x_goal", "sum"),
            season_shots=("x_goal", "size"),
        )
        for keys, group in self.data.groupby(["season", "attack_type"]):
            season, attack_type = keys
            season_total = season_totals.loc[season]
            row = {"season": int(season), "attack_type": attack_type}
            row.update(summarize_shots(group))
            row["xg_share"] = rate(row["xg"], float(season_total["season_xg"]))
            row["shot_share"] = rate(row["shots"], int(season_total["season_shots"]))
            rows.append(row)
        return pd.DataFrame(rows).sort_values(["season", "xg"], ascending=[False, False])

    def _team_profiles(self, team_col, profile_type):
        if self.league_profile.empty:
            return pd.DataFrame()

        league_lookup = self.league_profile.set_index(["season", "attack_type"])
        team_totals = self.data.groupby(["season", team_col]).agg(team_xg=("x_goal", "sum"))
        rows = []
        for keys, group in self.data.groupby(["season", team_col, "attack_type"]):
            season, team, attack_type = keys
            if len(group) < 40:
                continue

            team_xg = float(team_totals.loc[(season, team), "team_xg"])
            summary = summarize_shots(group)
            league_row = league_lookup.loc[(season, attack_type)]
            xg_share = rate(summary["xg"], team_xg)
            league_share = self._number_or_none(league_row["xg_share"])
            league_avg = self._number_or_none(league_row["avg_xg"])

            rows.append(
                {
                    "season": int(season),
                    "team": team,
                    "profile_type": profile_type,
                    "attack_type": attack_type,
                    **summary,
                    "xg_share": xg_share,
                    "xg_share_index": rate(xg_share, league_share) if league_share else None,
                    "avg_xg_index": rate(summary["avg_xg"], league_avg) if league_avg else None,
                }
            )

        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        frame["style_score"] = frame["xg_share_index"].fillna(0) * frame["avg_xg_index"].fillna(0)
        return frame.sort_values(["season", "style_score"], ascending=[False, False])

    def _matchups(self, pp_profiles, pk_profiles):
        if pp_profiles.empty or pk_profiles.empty:
            return pd.DataFrame()

        latest_season = int(min(pp_profiles["season"].max(), pk_profiles["season"].max()))
        pp = pp_profiles[pp_profiles["season"] == latest_season]
        pk = pk_profiles[pk_profiles["season"] == latest_season]
        rows = []

        for attack_type in sorted(set(pp["attack_type"]) & set(pk["attack_type"])):
            pp_type = pp[pp["attack_type"] == attack_type]
            pk_type = pk[pk["attack_type"] == attack_type]
            for _, pp_row in pp_type.iterrows():
                for _, pk_row in pk_type.iterrows():
                    if pp_row["team"] == pk_row["team"]:
                        continue
                    pp_style_index = self._number_or_zero(pp_row.get("xg_share_index"))
                    pk_leak_index = self._number_or_zero(pk_row.get("xg_share_index"))
                    score = pp_style_index * pk_leak_index * np.log1p(float(pp_row["shots"]) + float(pk_row["shots"]))
                    if score <= 0:
                        continue
                    rows.append(
                        {
                            "season": latest_season,
                            "pp_team": pp_row["team"],
                            "pk_team": pk_row["team"],
                            "attack_type": attack_type,
                            "matchup_score": float(score),
                            "pp_style_index": pp_style_index,
                            "pk_leak_index": pk_leak_index,
                            "pp_avg_xg": float(pp_row["avg_xg"]),
                            "pk_allowed_avg_xg": float(pk_row["avg_xg"]),
                            "pp_shots": int(pp_row["shots"]),
                            "pk_shots_allowed": int(pk_row["shots"]),
                            "note": self._matchup_note(pp_row["team"], pk_row["team"], attack_type),
                        }
                    )

        frame = pd.DataFrame(rows)
        return frame.sort_values("matchup_score", ascending=False).head(80) if not frame.empty else frame

    def _heatmap_bins(self, df):
        frame = df.dropna(subset=["x_cord_adjusted", "y_cord_adjusted", "x_goal"]).copy()
        if frame.empty:
            return pd.DataFrame()

        frame["rink_x"] = frame["x_cord_adjusted"].astype(float).abs().clip(0, 100)
        frame["rink_y"] = frame["y_cord_adjusted"].astype(float).clip(-42.5, 42.5)
        frame["x_bin"] = pd.cut(frame["rink_x"], bins=np.linspace(0, 100, 21), labels=False, include_lowest=True)
        frame["y_bin"] = pd.cut(frame["rink_y"], bins=np.linspace(-42.5, 42.5, 18), labels=False, include_lowest=True)

        rows = []
        for keys, group in frame.groupby(["x_bin", "y_bin"], dropna=True):
            x_bin, y_bin = keys
            if len(group) < 25:
                continue
            xg = group["x_goal"].astype(float)
            rows.append(
                {
                    "x_bin": int(x_bin),
                    "y_bin": int(y_bin),
                    "shots": int(len(group)),
                    "xg": float(xg.sum()),
                    "avg_xg": float(xg.mean()),
                    "goal_rate": rate(group["goal"].astype(bool).sum(), len(group)),
                    "rebound_rate": rate(group["shot_generated_rebound"].astype(bool).sum(), len(group)),
                }
            )
        return pd.DataFrame(rows).sort_values("xg", ascending=False) if rows else pd.DataFrame()

    def _team_shot_maps(self):
        """Compact team-season PP/PK shot maps for the frontend animation tool."""
        if self.data.empty:
            return pd.DataFrame()

        pp_maps = self._team_shot_map_rows("shooting_team_code", "pp_attack")
        pk_maps = self._team_shot_map_rows("defending_team_code", "pk_leak")
        frame = pd.concat([pp_maps, pk_maps], ignore_index=True)
        if frame.empty:
            return frame

        frame["map_score"] = frame["xg_share"].fillna(0) * frame["avg_xg"].fillna(0) * np.log1p(frame["shots"].fillna(0))
        return frame.sort_values(["season", "profile_type", "team", "map_score"], ascending=[False, True, True, False])

    def _team_shot_map_rows(self, team_col, profile_type):
        frame = self.data.dropna(subset=["x_cord_adjusted", "y_cord_adjusted", "x_goal", team_col]).copy()
        if frame.empty:
            return pd.DataFrame()

        frame["rink_x"] = frame["x_cord_adjusted"].astype(float).abs().clip(0, 100)
        frame["rink_y"] = frame["y_cord_adjusted"].astype(float).clip(-42.5, 42.5)
        frame["x_bin"] = pd.cut(frame["rink_x"], bins=np.linspace(0, 100, 17), labels=False, include_lowest=True)
        frame["y_bin"] = pd.cut(frame["rink_y"], bins=np.linspace(-42.5, 42.5, 13), labels=False, include_lowest=True)

        team_totals = frame.groupby(["season", team_col]).agg(team_xg=("x_goal", "sum"), team_shots=("x_goal", "size"))
        rows = []
        for keys, group in frame.groupby(["season", team_col, "attack_type", "x_bin", "y_bin"], dropna=True):
            season, team, attack_type, x_bin, y_bin = keys
            if len(group) < 8:
                continue

            total = team_totals.loc[(season, team)]
            xg = group["x_goal"].astype(float)
            rows.append(
                {
                    "season": int(season),
                    "team": team,
                    "profile_type": profile_type,
                    "attack_type": attack_type,
                    "x_bin": int(x_bin),
                    "y_bin": int(y_bin),
                    "rink_x": float(group["rink_x"].mean()),
                    "rink_y": float(group["rink_y"].mean()),
                    "shots": int(len(group)),
                    "xg": float(xg.sum()),
                    "avg_xg": float(xg.mean()),
                    "xg_share": rate(float(xg.sum()), float(total["team_xg"])),
                    "shot_share": rate(int(len(group)), int(total["team_shots"])),
                    "goal_rate": rate(group["goal"].astype(bool).sum(), len(group)),
                    "rebound_rate": rate(group["shot_generated_rebound"].astype(bool).sum(), len(group)),
                    "royal_road_rate": rate(group["shot_angle_rebound_royal_road"].astype(bool).sum(), len(group)),
                }
            )

        return pd.DataFrame(rows)

    def _matchup_note(self, pp_team, pk_team, attack_type):
        labels = {
            "east_west_seam": "look for lateral seams before the shot",
            "downhill": "push downhill into the slot or crease",
            "diagonal_seam": "change both lane and depth before release",
            "net_front_rebound": "crash second chances around the crease",
            "bumper_slot": "use quick slot touches instead of slow resets",
            "point_reset": "test point-to-slot recovery",
            "reset": "force the PK to reset and defend another layer",
        }
        action = labels.get(attack_type, "attack the matching weak area")
        return f"{pp_team} creates this look and {pk_team} allows it: {action}."

    def _number_or_zero(self, value):
        number = self._number_or_none(value)
        return 0.0 if number is None else number

    def _number_or_none(self, value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return None if pd.isna(number) else number
