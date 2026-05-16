"""Model 4: PK entry defense outcomes.

The requested aggressive/passive forecheck structure requires player
positioning. This supported version evaluates entry outcomes against the PK
using possession data and opponent PP entry tendencies.
"""

import logging

from db import DatabaseConnection
from models.model_utils import add_timestamp, bootstrap_ci_by_game, export_json

logger = logging.getLogger(__name__)


class PkForecheckStructureModel:
    """Descriptive PP entry outcomes against PK."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None

    def fetch_data(self):
        query = """
        WITH pp_entries AS (
            SELECT
                p.possession_id,
                p.game_id,
                p.team_id AS pp_team_id,
                p.entry_type,
                p.end_type,
                p.duration_seconds,
                COALESCE(p.xg_sum, 0) AS xga_entry,
                p.shot_count,
                p.goal_count,
                p.strength,
                g.season,
                CASE
                    WHEN split_part(p.strength, 'v', 1)::int < split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int < split_part(p.strength, 'v', 1)::int THEN g.home_team_id
                END AS pk_team_id
            FROM possessions p
            JOIN games g ON p.game_id = g.game_id
            WHERE p.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
              AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
              AND p.team_id = CASE
                    WHEN split_part(p.strength, 'v', 1)::int > split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int > split_part(p.strength, 'v', 1)::int THEN g.home_team_id
              END
        ),
        tendency AS (
            SELECT
                pp_team_id,
                AVG(CASE WHEN entry_type = 'CONTROLLED' THEN 1.0 ELSE 0.0 END) AS controlled_entry_tendency
            FROM pp_entries
            WHERE strength = '5v4'
            GROUP BY pp_team_id
        )
        SELECT
            e.*,
            COALESCE(t.controlled_entry_tendency, 0) AS controlled_entry_tendency,
            CASE WHEN COALESCE(t.controlled_entry_tendency, 0) >= 0.5 THEN 'carry_in_heavy' ELSE 'dump_in_heavy' END AS opponent_tendency
        FROM pp_entries e
        LEFT JOIN tendency t ON t.pp_team_id = e.pp_team_id
        """
        logger.info("Fetching PK entry defense outcome data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 4 sample: %s PP entries", len(self.data))
        return self.data

    @staticmethod
    def _summary(group):
        seconds = group["duration_seconds"].astype(float).clip(lower=1).sum()
        return {
            "n_entries": int(len(group)),
            "controlled_entry_rate": float((group["entry_type"] == "CONTROLLED").mean()),
            "dump_in_rate": float((group["entry_type"] == "DUMP_IN").mean()),
            "clear_rate": float((group["end_type"] == "CLEAR").mean()),
            "shot_rate": float((group["shot_count"].astype(float) > 0).mean()),
            "goal_rate": float((group["goal_count"].astype(float) > 0).mean()),
            "avg_xga_per_entry": float(group["xga_entry"].astype(float).mean()),
            "xga_per_60_observed_duration": float(group["xga_entry"].astype(float).sum() / seconds * 60) if seconds > 0 else None,
        }

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 4: PK Entry Defense Outcomes")
        logger.info("=" * 60)
        data = self.fetch_data()

        by_entry = []
        for entry_type, group in data.groupby("entry_type"):
            row = {"entry_type": entry_type, **self._summary(group)}
            row["avg_xga_ci"] = bootstrap_ci_by_game(group, "game_id", lambda x: x["xga_entry"].astype(float).mean(), n_bootstrap=200)
            by_entry.append(row)

        by_tendency = []
        for keys, group in data.groupby(["opponent_tendency", "entry_type"]):
            tendency, entry_type = keys
            by_tendency.append({"opponent_tendency": tendency, "entry_type": entry_type, **self._summary(group)})

        results = add_timestamp(
            {
                "model": "PK Entry Defense Outcomes",
                "summary_by_entry_type": by_entry,
                "summary_by_opponent_tendency": by_tendency,
                "sample": {"n_entries": int(len(data))},
                "caveats": [
                    "Original forechecker-count structure requires tracking/player coordinates and is not estimated",
                    "Opponent tendency is estimated from observed PP possession entry types",
                    "xGA/60 uses observed possession duration, not true time-on-ice",
                    "This is descriptive, not causal",
                ],
            }
        )
        results["output_file"] = export_json(results, "model4_pk_entry_defense_outcomes.json")
        logger.info("Model 4 output: %s", results["output_file"])
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        PkForecheckStructureModel(db).run()
    finally:
        db.close()
