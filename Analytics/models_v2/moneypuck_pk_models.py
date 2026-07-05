"""MoneyPuck-backed PK Decision Lab models."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from models.model_utils import add_timestamp, export_json
from models_v2.common import records, top_records
from moneypuck.features import (
    PK_SHOTS_AGAINST_WHERE,
    PK_SHOTS_FOR_WHERE,
    add_movement_bucket,
    per60,
    pct_rank,
    rate,
    summarize_shots,
)


logger = logging.getLogger(__name__)


class PuckMovementGeometryModel:
    """Classify how pre-shot puck movement breaks a PK."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = pd.DataFrame()

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
        """
        logger.info("Fetching MoneyPuck PK shots for movement geometry...")
        self.data = add_movement_bucket(self.db.query_to_df(query))
        logger.info("Movement geometry rows: %s", len(self.data))
        return self.data

    def run(self):
        self.fetch_data()
        bucket_rows = []
        for bucket, group in self.data.groupby("movement_bucket"):
            row = {"movement_bucket": bucket}
            row.update(summarize_shots(group))
            bucket_rows.append(row)
        bucket_summary = pd.DataFrame(bucket_rows).sort_values(["avg_xg", "shots"], ascending=[False, False])

        team_rows = []
        for keys, group in self.data.groupby(["defending_team_code", "movement_bucket"]):
            team, bucket = keys
            if len(group) < 50:
                continue
            row = {"team": team, "movement_bucket": bucket}
            row.update(summarize_shots(group))
            team_rows.append(row)
        team_summary = pd.DataFrame(team_rows)

        results = add_timestamp(
            {
                "model": "MoneyPuck PK Puck Movement Geometry",
                "bucket_summary": records(bucket_summary),
                "team_vulnerabilities": {
                    bucket: top_records(team_summary[team_summary["movement_bucket"] == bucket], "avg_xg", count=8)
                    for bucket in sorted(team_summary["movement_bucket"].unique()) if not team_summary.empty
                },
                "sample": {
                    "pk_shots_against": int(len(self.data)),
                    "minimum_team_bucket_shots": 50,
                },
                "caveats": [
                    "Movement buckets are derived from MoneyPuck last-event and shot coordinates.",
                    "This measures pre-shot geometry, not player tracking or exact team structure.",
                    "North-south and diagonal buckets are useful diagnostics but have smaller samples than reset/rebound buckets.",
                ],
            }
        )
        results["output_file"] = export_json(results, "model_v2_puck_movement_geometry.json")
        return results


class BlockedShotAftershockModel:
    """Measure danger after a PK block fails to end pressure."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = pd.DataFrame()
        self.baseline = pd.DataFrame()

    def fetch_data(self):
        query = f"""
        SELECT
            season,
            game_id,
            defending_team_code,
            shooting_team_code,
            x_goal,
            goal,
            shot_generated_rebound,
            shot_play_continued_in_zone,
            shot_play_continued_outside_zone,
            shot_goalie_froze,
            time_since_last_event,
            distance_from_last_event,
            speed_from_last_event,
            last_event_category
        FROM mp_shots
        WHERE {PK_SHOTS_AGAINST_WHERE}
          AND x_goal IS NOT NULL
        """
        all_pk = self.db.query_to_df(query)
        self.baseline = all_pk
        self.data = all_pk[all_pk["last_event_category"] == "BLOCK"].copy()
        logger.info("Blocked-shot aftershock rows: %s", len(self.data))
        return self.data

    def run(self):
        self.fetch_data()
        league_avg = float(self.baseline["x_goal"].astype(float).mean()) if not self.baseline.empty else None

        rows = []
        for team, group in self.data.groupby("defending_team_code"):
            if len(group) < 75:
                continue
            xg = group["x_goal"].astype(float)
            rows.append(
                {
                    "team": team,
                    "after_block_shots": int(len(group)),
                    "avg_xg_after_block": float(xg.mean()),
                    "xg_after_block": float(xg.sum()),
                    "goals_after_block": int(group["goal"].astype(bool).sum()),
                    "high_danger_after_block_rate": rate((xg >= 0.10).sum(), len(group)),
                    "continued_in_zone_rate": rate(group["shot_play_continued_in_zone"].astype(bool).sum(), len(group)),
                    "rebound_generated_rate": rate(group["shot_generated_rebound"].astype(bool).sum(), len(group)),
                    "avg_xg_vs_pk_baseline": float(xg.mean() - league_avg) if league_avg is not None else None,
                }
            )
        summary = pd.DataFrame(rows)

        results = add_timestamp(
            {
                "model": "MoneyPuck PK Blocked-Shot Aftershock",
                "league": {
                    "pk_shots_against": int(len(self.baseline)),
                    "after_block_shots": int(len(self.data)),
                    "league_avg_pk_shot_xg": league_avg,
                    "league_avg_xg_after_block": float(self.data["x_goal"].astype(float).mean()) if not self.data.empty else None,
                },
                "teams": records(summary.sort_values("avg_xg_after_block", ascending=False)) if not summary.empty else [],
                "highest_aftershock_teams": top_records(summary, "avg_xg_after_block", count=8),
                "sample": {"minimum_team_after_block_shots": 75},
                "caveats": [
                    "A BLOCK last event means the next recorded shot followed a blocked attempt; it does not identify the blocker.",
                    "The model measures failed pressure relief after blocks, not individual shot-blocking value.",
                ],
            }
        )
        results["output_file"] = export_json(results, "model_v2_blocked_shot_aftershock.json")
        return results


class GoalieControlAboveExpectedModel:
    """Profile PK goalie control outcomes beyond goals saved above expected."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = pd.DataFrame()

    def fetch_data(self):
        query = f"""
        SELECT
            season,
            game_id,
            goalie_id_for_shot,
            goalie_name_for_shot,
            x_goal,
            goal,
            x_froze,
            shot_goalie_froze,
            x_rebound,
            shot_generated_rebound,
            x_play_continued_outside_zone,
            shot_play_continued_outside_zone,
            x_play_continued_in_zone,
            shot_play_continued_in_zone
        FROM mp_shots
        WHERE {PK_SHOTS_AGAINST_WHERE}
          AND goalie_id_for_shot IS NOT NULL
          AND x_goal IS NOT NULL
        """
        self.data = self.db.query_to_df(query)
        logger.info("Goalie control rows: %s", len(self.data))
        return self.data

    def run(self):
        self.fetch_data()
        rows = []
        for keys, group in self.data.groupby(["season", "goalie_id_for_shot", "goalie_name_for_shot"]):
            season, goalie_id, name = keys
            if len(group) < 150:
                continue
            xg = group["x_goal"].astype(float)
            goals = group["goal"].astype(bool).sum()
            freeze_oe = group["shot_goalie_froze"].astype(bool).sum() - group["x_froze"].astype(float).sum()
            rebound_oe = group["shot_generated_rebound"].astype(bool).sum() - group["x_rebound"].astype(float).sum()
            out_oe = group["shot_play_continued_outside_zone"].astype(bool).sum() - group["x_play_continued_outside_zone"].astype(float).sum()
            in_oe = group["shot_play_continued_in_zone"].astype(bool).sum() - group["x_play_continued_in_zone"].astype(float).sum()
            scale = 100 / len(group)
            gsax = xg.sum() - goals
            gsax_per100 = gsax * scale
            freeze_oe_per100 = freeze_oe * scale
            rebound_oe_per100 = rebound_oe * scale
            out_oe_per100 = out_oe * scale
            in_oe_per100 = in_oe * scale
            rows.append(
                {
                    "goalie_id": int(goalie_id),
                    "goalie": name,
                    "season": int(season),
                    "pk_shots_faced": int(len(group)),
                    "gsax": float(gsax),
                    "gsax_per100": float(gsax_per100),
                    "goals_allowed": int(goals),
                    "freeze_above_expected": float(freeze_oe),
                    "freeze_above_expected_per100": float(freeze_oe_per100),
                    "rebounds_allowed_above_expected": float(rebound_oe),
                    "rebounds_allowed_above_expected_per100": float(rebound_oe_per100),
                    "play_outside_zone_above_expected": float(out_oe),
                    "play_outside_zone_above_expected_per100": float(out_oe_per100),
                    "play_continued_in_zone_above_expected": float(in_oe),
                    "play_continued_in_zone_above_expected_per100": float(in_oe_per100),
                    "control_score": float(gsax_per100 + (freeze_oe_per100 * 0.20) - (rebound_oe_per100 * 0.45) + (out_oe_per100 * 0.15) - (in_oe_per100 * 0.15)),
                }
            )
        summary = pd.DataFrame(rows)
        if not summary.empty:
            summary["control_percentile"] = pct_rank(summary["control_score"], higher_is_better=True)

        results = add_timestamp(
            {
                "model": "MoneyPuck PK Goalie Control Above Expected",
                "goalies": records(summary.sort_values("control_score", ascending=False)) if not summary.empty else [],
                "best_control_goalies": top_records(summary, "control_score", count=10),
                "rebound_leak_watch": top_records(summary, "rebounds_allowed_above_expected_per100", count=10),
                "seasons": sorted([int(season) for season in summary["season"].dropna().unique()], reverse=True) if not summary.empty else [],
                "sample": {"pk_shots": int(len(self.data)), "minimum_goalie_pk_shots": 150},
                "caveats": [
                    "Control outcomes compare actual freezes/rebounds/continuations to MoneyPuck expected outcome probabilities.",
                    "Rebound watch is normalized per 100 PK shots so heavy workload does not dominate the list.",
                    "Rebounds allowed above expected is bad; freezes and play outside zone above expected are generally good.",
                    "Team defensive clearance can influence goalie control outcomes.",
                ],
            }
        )
        results["output_file"] = export_json(results, "model_v2_goalie_control_above_expected.json")
        return results


class PkFatigueTimingModel:
    """Measure PK danger by fatigue and penalty-clock phase."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = pd.DataFrame()

    def fetch_data(self):
        query = f"""
        SELECT
            season,
            game_id,
            defending_team_code,
            x_goal,
            goal,
            shot_angle_rebound_royal_road,
            shot_generated_rebound,
            defending_team_average_time_on_ice,
            defending_team_max_time_on_ice,
            defending_team_average_time_on_ice_since_faceoff,
            defending_team_max_time_on_ice_since_faceoff,
            CASE WHEN is_home_shot THEN away_penalty1_time_left ELSE home_penalty1_time_left END AS defending_penalty_time_left,
            CASE WHEN is_home_shot THEN away_penalty1_length ELSE home_penalty1_length END AS defending_penalty_length
        FROM mp_shots
        WHERE {PK_SHOTS_AGAINST_WHERE}
          AND x_goal IS NOT NULL
        """
        self.data = self.db.query_to_df(query)
        logger.info("PK fatigue/timing rows: %s", len(self.data))
        return self.data

    def summarize_bucket(self, frame, column, bins, labels):
        data = frame.copy()
        data["bucket"] = pd.cut(data[column].astype(float), bins=bins, labels=labels, right=False)
        rows = []
        for bucket, group in data.dropna(subset=["bucket"]).groupby("bucket", observed=True):
            xg = group["x_goal"].astype(float)
            rows.append(
                {
                    "bucket": str(bucket),
                    "shots": int(len(group)),
                    "avg_xg": float(xg.mean()),
                    "goal_rate": rate(group["goal"].astype(bool).sum(), len(group)),
                    "royal_road_rate": rate(group["shot_angle_rebound_royal_road"].astype(bool).sum(), len(group)),
                    "rebound_generated_rate": rate(group["shot_generated_rebound"].astype(bool).sum(), len(group)),
                }
            )
        return rows

    def run(self):
        self.fetch_data()
        data = self.data.copy()
        valid_penalty = data[
            (data["defending_penalty_time_left"].astype(float) > 0)
            & (data["defending_penalty_length"].astype(float) > 0)
        ].copy()
        valid_penalty["penalty_elapsed"] = (
            valid_penalty["defending_penalty_length"].astype(float)
            - valid_penalty["defending_penalty_time_left"].astype(float)
        ).clip(lower=0)

        avg_toi = self.summarize_bucket(data, "defending_team_average_time_on_ice", [0, 20, 35, 50, 65, 9999], ["0-20", "20-35", "35-50", "50-65", "65+"])
        max_toi = self.summarize_bucket(data, "defending_team_max_time_on_ice", [0, 30, 45, 60, 75, 9999], ["0-30", "30-45", "45-60", "60-75", "75+"])
        penalty_elapsed = self.summarize_bucket(valid_penalty, "penalty_elapsed", [0, 20, 45, 75, 120, 9999], ["0-20", "20-45", "45-75", "75-120", "120+"])
        penalty_left = self.summarize_bucket(valid_penalty, "defending_penalty_time_left", [0, 20, 45, 75, 120, 9999], ["0-20", "20-45", "45-75", "75-120", "120+"])

        team_rows = []
        for team, group in data.groupby("defending_team_code"):
            tired = group[group["defending_team_average_time_on_ice"].astype(float) >= 50]
            fresh = group[group["defending_team_average_time_on_ice"].astype(float) < 35]
            if len(tired) < 100 or len(fresh) < 100:
                continue
            team_rows.append(
                {
                    "team": team,
                    "fresh_shots": int(len(fresh)),
                    "tired_shots": int(len(tired)),
                    "fresh_avg_xg": float(fresh["x_goal"].astype(float).mean()),
                    "tired_avg_xg": float(tired["x_goal"].astype(float).mean()),
                    "fatigue_cliff": float(tired["x_goal"].astype(float).mean() - fresh["x_goal"].astype(float).mean()),
                }
            )
        team_summary = pd.DataFrame(team_rows)

        results = add_timestamp(
            {
                "model": "MoneyPuck PK Fatigue And Penalty Timing",
                "defending_average_toi": avg_toi,
                "defending_max_toi": max_toi,
                "penalty_elapsed": penalty_elapsed,
                "penalty_time_left": penalty_left,
                "team_fatigue_cliffs": top_records(team_summary, "fatigue_cliff", count=10),
                "sample": {
                    "pk_shots_against": int(len(data)),
                    "valid_penalty_clock_shots": int(len(valid_penalty)),
                    "team_cliff_minimum_fresh_and_tired_shots": 100,
                },
                "caveats": [
                    "Penalty-clock analysis excludes shots without a valid defending-team penalty clock.",
                    "TOI fields describe skater fatigue context for the defending team, not exact goalie shift length.",
                ],
            }
        )
        results["output_file"] = export_json(results, "model_v2_pk_fatigue_timing.json")
        return results


class ShortHandedTwoWayValueModel:
    """Find PK skaters who create offense without defensive leakage."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = pd.DataFrame()

    def fetch_data(self):
        query = """
        SELECT
            player_id,
            name,
            position,
            team,
            season,
            ice_time,
            games_played,
            i_f_x_goals,
            i_f_goals,
            i_f_shot_attempts,
            on_ice_f_x_goals,
            on_ice_a_x_goals,
            on_ice_f_shot_attempts,
            on_ice_a_shot_attempts,
            shots_blocked_by_player,
            penalties,
            penalties_drawn
        FROM mp_skaters_season
        WHERE situation = '4on5'
          AND ice_time IS NOT NULL
          AND ice_time > 0
        """
        self.data = self.db.query_to_df(query)
        logger.info("Short-handed two-way rows: %s", len(self.data))
        return self.data

    def run(self):
        self.fetch_data()
        rows = []
        for keys, group in self.data.groupby(["season", "player_id", "name", "position"]):
            season, player_id, name, position = keys
            ice_time = group["ice_time"].astype(float).sum()
            if ice_time < 600:
                continue
            on_f = group["on_ice_f_x_goals"].astype(float).sum()
            on_a = group["on_ice_a_x_goals"].astype(float).sum()
            indiv = group["i_f_x_goals"].astype(float).sum()
            rows.append(
                {
                    "player_id": int(player_id),
                    "name": name,
                    "position": position,
                    "season": int(season),
                    "teams": ", ".join(sorted(group["team"].dropna().unique())),
                    "ice_time": float(ice_time),
                    "individual_sh_xg_per60": per60(indiv, ice_time),
                    "on_ice_sh_xg_for_per60": per60(on_f, ice_time),
                    "on_ice_xga_per60": per60(on_a, ice_time),
                    "two_way_net_xg_per60": per60(on_f - on_a, ice_time),
                    "shot_attempt_share": rate(group["on_ice_f_shot_attempts"].astype(float).sum(), group["on_ice_f_shot_attempts"].astype(float).sum() + group["on_ice_a_shot_attempts"].astype(float).sum()),
                    "blocks_per60": per60(group["shots_blocked_by_player"].astype(float).sum(), ice_time),
                    "penalty_draw_minus_take_per60": per60(group["penalties_drawn"].astype(float).sum() - group["penalties"].astype(float).sum(), ice_time),
                }
            )
        summary = pd.DataFrame(rows)
        if not summary.empty:
            summary["offense_percentile"] = pct_rank(summary["on_ice_sh_xg_for_per60"], True)
            summary["defense_percentile"] = pct_rank(summary["on_ice_xga_per60"], False)
            summary["two_way_percentile"] = pct_rank(summary["two_way_net_xg_per60"], True)

        results = add_timestamp(
            {
                "model": "MoneyPuck Short-Handed Offense Without Defensive Leakage",
                "players": records(summary.sort_values("two_way_net_xg_per60", ascending=False)) if not summary.empty else [],
                "two_way_leaders": top_records(summary, "two_way_net_xg_per60", count=12),
                "offense_without_leakage": top_records(
                    summary[(summary["offense_percentile"] >= 75) & (summary["defense_percentile"] >= 50)] if not summary.empty else summary,
                    "two_way_net_xg_per60",
                    count=12,
                ),
                "seasons": sorted([int(season) for season in summary["season"].dropna().unique()], reverse=True) if not summary.empty else [],
                "sample": {"skater_season_rows": int(len(self.data)), "minimum_4on5_ice_time_seconds": 600},
                "caveats": [
                    "This uses season-level MoneyPuck 4on5 skater aggregates, not shot-by-shot on-ice player IDs.",
                    "V2 scouting leaderboards are season-specific so retired players do not appear in current-season views.",
                ],
            }
        )
        results["output_file"] = export_json(results, "model_v2_short_handed_two_way_value.json")
        return results


class BayesianPkPlayerEvaluationModel:
    """Empirical-Bayes PK skater evaluation and similarity from MoneyPuck aggregates."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = pd.DataFrame()

    def fetch_data(self):
        query = """
        SELECT
            player_id,
            name,
            position,
            team,
            season,
            ice_time,
            games_played,
            i_f_x_goals,
            i_f_goals,
            i_f_shot_attempts,
            on_ice_f_x_goals,
            on_ice_a_x_goals,
            on_ice_f_shot_attempts,
            on_ice_a_shot_attempts,
            shots_blocked_by_player,
            penalties,
            penalties_drawn
        FROM mp_skaters_season
        WHERE situation = '4on5'
          AND ice_time IS NOT NULL
          AND ice_time > 0
        """
        self.data = self.db.query_to_df(query)
        logger.info("Bayesian PK player evaluation rows: %s", len(self.data))
        return self.data

    @staticmethod
    def trust_label(ice_time, uncertainty):
        if ice_time >= 3600 and uncertainty <= 0.75:
            return "Strong signal"
        if ice_time >= 1200 and uncertainty <= 1.05:
            return "Useful signal"
        return "Too noisy"

    def player_seasons(self):
        rows = []
        for keys, group in self.data.groupby(["season", "player_id", "name", "position"]):
            season, player_id, name, position = keys
            ice_time = group["ice_time"].astype(float).sum()
            if ice_time < 300:
                continue
            on_f = group["on_ice_f_x_goals"].astype(float).sum()
            on_a = group["on_ice_a_x_goals"].astype(float).sum()
            attempts_for = group["on_ice_f_shot_attempts"].astype(float).sum()
            attempts_against = group["on_ice_a_shot_attempts"].astype(float).sum()
            indiv_xg = group["i_f_x_goals"].astype(float).sum()
            rows.append(
                {
                    "player_id": int(player_id),
                    "name": name,
                    "position": position,
                    "season": int(season),
                    "teams": ", ".join(sorted(group["team"].dropna().unique())),
                    "ice_time": float(ice_time),
                    "games_played": int(group["games_played"].astype(float).max()),
                    "on_ice_sh_xg_for_per60": per60(on_f, ice_time),
                    "on_ice_xga_per60": per60(on_a, ice_time),
                    "two_way_net_xg_per60": per60(on_f - on_a, ice_time),
                    "individual_sh_xg_per60": per60(indiv_xg, ice_time),
                    "shot_attempt_share": rate(attempts_for, attempts_for + attempts_against),
                    "blocks_per60": per60(group["shots_blocked_by_player"].astype(float).sum(), ice_time),
                    "penalty_draw_minus_take_per60": per60(group["penalties_drawn"].astype(float).sum() - group["penalties"].astype(float).sum(), ice_time),
                }
            )
        return pd.DataFrame(rows)

    def add_empirical_bayes(self, summary):
        if summary.empty:
            return summary
        output = []
        for season, season_df in summary.groupby("season"):
            league = season_df.copy()
            league_mean = float(league["two_way_net_xg_per60"].mean())
            league_sd = float(league["two_way_net_xg_per60"].std(ddof=0) or 0.75)
            prior_seconds = 1800.0
            for _, row in league.iterrows():
                ice_time = float(row["ice_time"])
                weight = ice_time / (ice_time + prior_seconds)
                raw = float(row["two_way_net_xg_per60"])
                estimate = league_mean + weight * (raw - league_mean)
                uncertainty = max(0.18, league_sd * (1 - weight + 0.18))
                lower = estimate - (1.64 * uncertainty)
                upper = estimate + (1.64 * uncertainty)
                out = row.to_dict()
                out.update(
                    {
                        "season": int(season),
                        "raw_pk_impact_per60": raw,
                        "true_talent_pk_impact_per60": float(estimate),
                        "impact_uncertainty": float(uncertainty),
                        "impact_lower_90": float(lower),
                        "impact_upper_90": float(upper),
                        "sample_weight": float(weight),
                        "trust_label": self.trust_label(ice_time, uncertainty),
                    }
                )
                output.append(out)
        enriched = pd.DataFrame(output)
        enriched["true_talent_percentile"] = enriched.groupby("season")["true_talent_pk_impact_per60"].rank(pct=True)
        enriched["uncertainty_percentile"] = enriched.groupby("season")["impact_uncertainty"].rank(pct=True, ascending=False)
        return enriched

    def build_similarity(self, summary):
        if summary.empty:
            return []
        features = [
            "ice_time",
            "on_ice_sh_xg_for_per60",
            "on_ice_xga_per60",
            "individual_sh_xg_per60",
            "shot_attempt_share",
            "blocks_per60",
            "penalty_draw_minus_take_per60",
            "true_talent_pk_impact_per60",
        ]
        rows = []
        for season, season_df in summary.groupby("season"):
            pool = season_df[season_df["ice_time"] >= 600].copy()
            if len(pool) < 8:
                continue
            matrix = pool[features].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            std = matrix.std(ddof=0).replace(0, 1)
            z = (matrix - matrix.mean()) / std
            top_pool = pool.sort_values("true_talent_pk_impact_per60", ascending=False).head(12)
            for idx, player in top_pool.iterrows():
                distances = ((z - z.loc[idx]) ** 2).sum(axis=1).pow(0.5)
                candidate_idxs = distances.sort_values().index.tolist()
                matches = []
                for candidate_idx in candidate_idxs:
                    if candidate_idx == idx:
                        continue
                    candidate = pool.loc[candidate_idx]
                    matches.append(
                        {
                            "player_id": int(candidate["player_id"]),
                            "name": candidate["name"],
                            "position": candidate["position"],
                            "teams": candidate["teams"],
                            "similarity_score": float(max(0, 100 - (distances.loc[candidate_idx] * 18))),
                            "true_talent_pk_impact_per60": float(candidate["true_talent_pk_impact_per60"]),
                            "trust_label": candidate["trust_label"],
                        }
                    )
                    if len(matches) == 4:
                        break
                rows.append(
                    {
                        "season": int(season),
                        "player_id": int(player["player_id"]),
                        "name": player["name"],
                        "position": player["position"],
                        "teams": player["teams"],
                        "true_talent_pk_impact_per60": float(player["true_talent_pk_impact_per60"]),
                        "trust_label": player["trust_label"],
                        "matches": matches,
                    }
                )
        return rows

    def run(self):
        self.fetch_data()
        summary = self.add_empirical_bayes(self.player_seasons())
        trusted = summary[(summary["ice_time"] >= 600) & (summary["trust_label"] != "Too noisy")] if not summary.empty else summary
        upside = summary[(summary["ice_time"] >= 300) & (summary["trust_label"] == "Too noisy")] if not summary.empty else summary

        results = add_timestamp(
            {
                "model": "MoneyPuck Empirical-Bayes PK Player Evaluation",
                "players": records(summary.sort_values(["season", "true_talent_pk_impact_per60"], ascending=[False, False])) if not summary.empty else [],
                "trusted_pk_impact": records(trusted.sort_values(["season", "true_talent_pk_impact_per60"], ascending=[False, False])) if not trusted.empty else [],
                "high_upside_noisy": records(upside.sort_values(["season", "true_talent_pk_impact_per60"], ascending=[False, False])) if not upside.empty else [],
                "similarity_groups": self.build_similarity(summary),
                "seasons": sorted([int(season) for season in summary["season"].dropna().unique()], reverse=True) if not summary.empty else [],
                "sample": {
                    "skater_season_rows": int(len(self.data)),
                    "minimum_seconds_for_estimate": 300,
                    "prior_seconds": 1800,
                    "trusted_minimum_seconds": 600,
                },
                "caveats": [
                    "This is empirical Bayes shrinkage, not a full MCMC model.",
                    "Higher true-talent impact is better because PK skaters usually give up more xG than they create.",
                    "Uncertainty bands are approximate and should be read as confidence context, not exact odds.",
                    "Similarity is role/outcome similarity from season aggregates, not stylistic tracking data.",
                ],
            }
        )
        results["output_file"] = export_json(results, "model_v2_bayesian_pk_player_evaluation.json")
        return results


class RushSetDefenseModel:
    """Guarded rush/set diagnostic from MoneyPuck shotRush."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = pd.DataFrame()

    def fetch_data(self):
        query = f"""
        SELECT
            season,
            game_id,
            defending_team_code,
            x_goal,
            goal,
            shot_rush
        FROM mp_shots
        WHERE {PK_SHOTS_AGAINST_WHERE}
          AND x_goal IS NOT NULL
        """
        self.data = self.db.query_to_df(query)
        logger.info("Rush/set rows: %s", len(self.data))
        return self.data

    def run(self):
        self.fetch_data()
        rows = []
        for label, group in self.data.groupby(self.data["shot_rush"].astype(bool).map({True: "rush", False: "set"})):
            xg = group["x_goal"].astype(float)
            rows.append(
                {
                    "shot_context": label,
                    "shots": int(len(group)),
                    "avg_xg": float(xg.mean()),
                    "xg": float(xg.sum()),
                    "goals": int(group["goal"].astype(bool).sum()),
                    "goal_rate": rate(group["goal"].astype(bool).sum(), len(group)),
                }
            )

        team_rows = []
        rush = self.data[self.data["shot_rush"].astype(bool)]
        for team, group in rush.groupby("defending_team_code"):
            if len(group) < 10:
                continue
            xg = group["x_goal"].astype(float)
            team_rows.append({"team": team, "rush_shots_against": int(len(group)), "avg_rush_xg": float(xg.mean()), "rush_xg": float(xg.sum())})
        team_summary = pd.DataFrame(team_rows)

        results = add_timestamp(
            {
                "model": "MoneyPuck PK Rush / Set Defense Diagnostic",
                "summary": rows,
                "rush_vulnerable_teams": top_records(team_summary, "avg_rush_xg", count=10),
                "sample": {
                    "pk_shots_against": int(len(self.data)),
                    "rush_flagged_shots": int(self.data["shot_rush"].astype(bool).sum()) if not self.data.empty else 0,
                    "minimum_team_rush_shots": 10,
                },
                "caveats": [
                    "The inspected MoneyPuck file has a sparse shotRush flag for PK shots, so this is a diagnostic subview.",
                    "Movement geometry and last-event speed should carry the transition story if rush samples are too thin.",
                ],
            }
        )
        results["output_file"] = export_json(results, "model_v2_rush_set_defense.json")
        return results
