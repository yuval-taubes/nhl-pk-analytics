"""Model 2: PK rush commitment risk-reward."""

import logging

import numpy as np
import pandas as pd

from db import DatabaseConnection
from models.model_utils import add_timestamp, bootstrap_ci_by_game, export_json

logger = logging.getLogger(__name__)


class PkRushCommitmentModel:
    """Decision-boundary table for PK offensive-zone rush commitment."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None
        self.results = None

    def fetch_data(self):
        query = """
        WITH pk_possessions AS (
            SELECT
                p.*,
                g.season,
                g.home_team_id,
                g.away_team_id,
                se.period,
                se.period_time_seconds AS start_time,
                ee.period_time_seconds AS end_time,
                CASE
                    WHEN split_part(p.strength, 'v', 1)::int < split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int < split_part(p.strength, 'v', 1)::int THEN g.home_team_id
                END AS pk_team_id,
                CASE
                    WHEN split_part(p.strength, 'v', 1)::int > split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int > split_part(p.strength, 'v', 1)::int THEN g.home_team_id
                END AS pp_team_id,
                CASE
                    WHEN p.team_id = g.home_team_id THEN g.home_score - g.away_score
                    ELSE g.away_score - g.home_score
                END AS score_diff
            FROM possessions p
            JOIN games g ON p.game_id = g.game_id
            JOIN events se ON p.start_event_id = se.event_id
            JOIN events ee ON p.end_event_id = ee.event_id
            WHERE p.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
              AND p.start_zone = 'OZ'
              AND p.team_id = CASE
                    WHEN split_part(p.strength, 'v', 1)::int < split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int < split_part(p.strength, 'v', 1)::int THEN g.home_team_id
              END
        ),
        commitment AS (
            SELECT
                p.possession_id,
                MAX(player_counts.pk_player_count) AS pk_players_seen_in_oz
            FROM pk_possessions p
            JOIN events e
              ON e.game_id = p.game_id
             AND e.event_idx BETWEEN (
                    SELECT event_idx FROM events WHERE event_id = p.start_event_id
                 ) AND (
                    SELECT event_idx FROM events WHERE event_id = p.end_event_id
                 )
            LEFT JOIN LATERAL (
                SELECT COUNT(DISTINCT ep.player_id) AS pk_player_count
                FROM event_players ep
                WHERE ep.event_id = e.event_id
                  AND ep.team_id = p.pk_team_id
                  AND (
                      (p.pk_team_id = p.home_team_id AND e.x_norm >= 125)
                      OR (p.pk_team_id = p.away_team_id AND e.x_norm <= 75)
                  )
            ) player_counts ON TRUE
            GROUP BY p.possession_id
        ),
        next_pp AS (
            SELECT DISTINCT ON (p.possession_id)
                p.possession_id,
                np.possession_id AS counter_possession_id,
                np.xg_sum AS counter_xg
            FROM pk_possessions p
            JOIN events pe ON p.end_event_id = pe.event_id
            JOIN possessions np ON np.game_id = p.game_id
            JOIN events ns ON np.start_event_id = ns.event_id
            WHERE np.team_id = p.pp_team_id
              AND np.possession_id <> p.possession_id
              AND ns.period = pe.period
              AND ns.period_time_seconds > pe.period_time_seconds
              AND ns.period_time_seconds <= pe.period_time_seconds + 30
              AND p.end_type <> 'GOAL'
            ORDER BY p.possession_id, ns.period_time_seconds
        )
        SELECT
            p.possession_id,
            p.game_id,
            p.season,
            p.team_id AS pk_team_id,
            p.strength,
            p.period,
            p.start_time,
            p.duration_seconds,
            p.shot_count,
            p.goal_count,
            COALESCE(p.xg_sum, 0) AS pk_xg,
            COALESCE(n.counter_xg, 0) AS counter_xg_against,
            COALESCE(c.pk_players_seen_in_oz, 1) AS pk_players_seen_in_oz,
            CASE
                WHEN COALESCE(c.pk_players_seen_in_oz, 1) <= 1 THEN 0
                WHEN COALESCE(c.pk_players_seen_in_oz, 1) = 2 THEN 1
                ELSE 2
            END AS commitment_level,
            CASE
                WHEN p.score_diff <= -2 THEN 'trailing_2_plus'
                WHEN p.score_diff = -1 THEN 'trailing_1'
                WHEN p.score_diff = 0 THEN 'tied'
                ELSE 'leading'
            END AS score_state,
            CASE
                WHEN p.period >= 3 AND p.start_time >= 900 THEN 'late_third'
                WHEN p.period = 3 THEN 'third'
                ELSE 'early_game'
            END AS game_phase
        FROM pk_possessions p
        LEFT JOIN commitment c ON c.possession_id = p.possession_id
        LEFT JOIN next_pp n ON n.possession_id = p.possession_id
        """
        logger.info("Fetching PK rush commitment data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 2 sample: %s PK OZ possessions", len(self.data))
        return self.data

    @staticmethod
    def _summarize_group(df):
        if df.empty:
            return {}
        return {
            "n": int(len(df)),
            "avg_pk_xg_benefit": float(df["pk_xg"].mean()),
            "avg_counter_xg_risk": float(df["counter_xg_against"].mean()),
            "net_xg": float(df["pk_xg"].mean() - df["counter_xg_against"].mean()),
            "counterattack_rate": float((df["counter_xg_against"] > 0).mean()),
            "avg_duration_seconds": float(df["duration_seconds"].astype(float).mean()),
        }

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 2: PK Rush Commitment Risk-Reward")
        logger.info("=" * 60)
        data = self.fetch_data()

        level_rows = []
        for level, group in data.groupby("commitment_level"):
            row = {"commitment_level": int(level), **self._summarize_group(group)}
            ci = bootstrap_ci_by_game(
                group,
                "game_id",
                lambda x: x["pk_xg"].astype(float).mean() - x["counter_xg_against"].astype(float).mean(),
                n_bootstrap=500,
            )
            row["net_xg_ci"] = ci
            level_rows.append(row)

        strata = []
        for keys, group in data.groupby(["score_state", "game_phase", "commitment_level"]):
            score_state, game_phase, level = keys
            strata.append(
                {
                    "score_state": score_state,
                    "game_phase": game_phase,
                    "commitment_level": int(level),
                    **self._summarize_group(group),
                }
            )

        levels = sorted(level_rows, key=lambda x: x["commitment_level"])
        marginal = []
        for prev, curr in zip(levels, levels[1:]):
            marginal.append(
                {
                    "from_level": prev["commitment_level"],
                    "to_level": curr["commitment_level"],
                    "marginal_pk_xg": curr["avg_pk_xg_benefit"] - prev["avg_pk_xg_benefit"],
                    "marginal_counter_xg": curr["avg_counter_xg_risk"] - prev["avg_counter_xg_risk"],
                    "marginal_net": curr["net_xg"] - prev["net_xg"],
                }
            )

        self.results = add_timestamp(
            {
                "model": "PK Rush Commitment Risk-Reward",
                "summary_by_commitment_level": level_rows,
                "marginal_curve": marginal,
                "stratified_summary": strata,
                "sample": {"n_possessions": int(len(data))},
                "caveats": [
                    "Commitment uses on-ice player linkage at event locations, not tracking-data player coordinates",
                    "The x_norm threshold is a blue-line approximation in normalized coordinates",
                    "Counterattack tracking only catches the immediate next opponent possession within 30 seconds",
                    "Goalie-pulled situations are not separately excluded",
                    "This is descriptive decision-boundary analysis, not a causal estimate",
                ],
            }
        )
        self.results["output_file"] = export_json(self.results, "model2_pk_rush_commitment.json")
        logger.info("Model 2 output: %s", self.results["output_file"])
        return self.results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        PkRushCommitmentModel(db).run()
    finally:
        db.close()
