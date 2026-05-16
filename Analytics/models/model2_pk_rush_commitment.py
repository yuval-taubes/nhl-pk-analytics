"""Model 2: PK offensive-zone foray risk-reward.

Original requested commitment levels require player coordinates/tracking data.
This supported version uses possession/event data to estimate the value and
counterattack risk of PK offensive-zone possessions.
"""

import logging

from db import DatabaseConnection
from models.model_utils import add_timestamp, bootstrap_ci_by_game, export_json

logger = logging.getLogger(__name__)


class PkRushCommitmentModel:
    """Risk-reward table for PK offensive-zone forays."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None

    def fetch_data(self):
        query = """
        WITH pk_oz AS (
            SELECT
                p.possession_id,
                p.game_id,
                g.season,
                p.team_id AS pk_team_id,
                p.entry_type,
                p.end_type,
                p.duration_seconds,
                p.shot_count,
                p.goal_count,
                COALESCE(p.xg_sum, 0) AS pk_xg,
                p.strength,
                se.period,
                se.period_time_seconds AS start_time,
                ee.period_time_seconds AS end_time,
                CASE
                    WHEN split_part(p.strength, 'v', 1)::int > split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int > split_part(p.strength, 'v', 1)::int THEN g.home_team_id
                END AS pp_team_id,
                CASE
                    WHEN p.team_id = g.home_team_id THEN g.home_score - g.away_score
                    ELSE g.away_score - g.home_score
                END AS pk_score_diff
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
        counter AS (
            SELECT DISTINCT ON (p.possession_id)
                p.possession_id,
                COALESCE(np.xg_sum, 0) AS counter_xg
            FROM pk_oz p
            JOIN events pe ON pe.game_id = p.game_id AND pe.period = p.period AND pe.period_time_seconds = p.end_time
            JOIN possessions np ON np.game_id = p.game_id AND np.team_id = p.pp_team_id
            JOIN events ns ON ns.event_id = np.start_event_id
            WHERE p.end_type <> 'GOAL'
              AND ns.period = p.period
              AND ns.period_time_seconds > p.end_time
              AND ns.period_time_seconds <= p.end_time + 30
            ORDER BY p.possession_id, ns.period_time_seconds
        )
        SELECT
            p.*,
            COALESCE(c.counter_xg, 0) AS counter_xg_against,
            CASE
                WHEN p.entry_type = 'CONTROLLED' THEN 'controlled_foray'
                WHEN p.entry_type = 'DUMP_IN' THEN 'dump_in_foray'
                WHEN p.entry_type = 'TURNOVER' THEN 'turnover_foray'
                WHEN p.entry_type = 'FACEOFF_START' THEN 'oz_faceoff_foray'
                ELSE 'other_foray'
            END AS foray_type,
            CASE
                WHEN p.pk_score_diff <= -2 THEN 'trailing_2_plus'
                WHEN p.pk_score_diff = -1 THEN 'trailing_1'
                WHEN p.pk_score_diff = 0 THEN 'tied'
                ELSE 'leading'
            END AS score_state,
            CASE
                WHEN p.period >= 3 AND p.start_time >= 900 THEN 'late_third'
                WHEN p.period = 3 THEN 'third'
                ELSE 'early_game'
            END AS game_phase
        FROM pk_oz p
        LEFT JOIN counter c ON c.possession_id = p.possession_id
        """
        logger.info("Fetching PK OZ foray data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 2 sample: %s PK OZ forays", len(self.data))
        return self.data

    @staticmethod
    def _summary(group):
        return {
            "n": int(len(group)),
            "avg_pk_xg_benefit": float(group["pk_xg"].astype(float).mean()),
            "avg_counter_xg_risk": float(group["counter_xg_against"].astype(float).mean()),
            "net_xg": float((group["pk_xg"].astype(float) - group["counter_xg_against"].astype(float)).mean()),
            "counterattack_rate": float((group["counter_xg_against"].astype(float) > 0).mean()),
            "shot_rate": float((group["shot_count"].astype(float) > 0).mean()),
        }

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 2: PK Offensive-Zone Foray Risk-Reward")
        logger.info("=" * 60)
        data = self.fetch_data()

        by_type = []
        for foray_type, group in data.groupby("foray_type"):
            row = {"foray_type": foray_type, **self._summary(group)}
            row["net_xg_ci"] = bootstrap_ci_by_game(
                group,
                "game_id",
                lambda x: (x["pk_xg"].astype(float) - x["counter_xg_against"].astype(float)).mean(),
                n_bootstrap=200,
            )
            by_type.append(row)

        strata = []
        for keys, group in data.groupby(["score_state", "game_phase", "foray_type"]):
            score_state, game_phase, foray_type = keys
            strata.append({"score_state": score_state, "game_phase": game_phase, "foray_type": foray_type, **self._summary(group)})

        results = add_timestamp(
            {
                "model": "PK Offensive-Zone Foray Risk-Reward",
                "summary_by_foray_type": by_type,
                "stratified_summary": strata,
                "sample": {"n_forays": int(len(data))},
                "caveats": [
                    "Original player-commitment levels require tracking/player coordinate data and are not estimated here",
                    "Counterattack risk only captures the next PP possession within 30 seconds",
                    "Goalie-pulled situations are not separately excluded",
                    "This is descriptive decision support, not causal inference",
                ],
            }
        )
        results["output_file"] = export_json(results, "model2_pk_foray_risk_reward.json")
        logger.info("Model 2 output: %s", results["output_file"])
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        PkRushCommitmentModel(db).run()
    finally:
        db.close()
