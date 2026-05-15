"""Model 8: PK forward shot suppression."""

import logging

import pandas as pd

from db import DatabaseConnection
from models.model_utils import add_timestamp, export_json
from models.player_scouting_utils import export_scouting, metric_ci, safe_div

logger = logging.getLogger(__name__)

MODEL_NAME = "model8_forward_shot_suppression"


class ForwardShotSuppressionModel:
    """Event-linked forward rankings for shot quality faced on the PK."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None

    def fetch_data(self):
        query = """
        WITH pk_shots_against AS (
            SELECT
                s.shot_id,
                s.xg,
                s.is_goal,
                e.event_id,
                e.game_id,
                e.zone,
                g.season,
                e.event_team_id AS pp_team_id,
                CASE
                    WHEN split_part(e.strength, 'v', 1)::int < split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(e.strength, 'v', 2)::int < split_part(e.strength, 'v', 1)::int THEN g.home_team_id
                END AS pk_team_id
            FROM shots s
            JOIN events e ON s.event_id = e.event_id
            JOIN games g ON e.game_id = g.game_id
            WHERE e.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
              AND s.xg IS NOT NULL
              AND e.event_team_id = CASE
                    WHEN split_part(e.strength, 'v', 1)::int > split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(e.strength, 'v', 2)::int > split_part(e.strength, 'v', 1)::int THEN g.home_team_id
              END
        )
        SELECT DISTINCT ON (sh.shot_id, pl.player_id)
            pl.player_id,
            pl.full_name,
            pl.position,
            sh.season,
            sh.game_id,
            sh.shot_id,
            sh.zone,
            sh.xg,
            sh.is_goal,
            CASE WHEN sh.xg > 0.15 THEN 1 ELSE 0 END AS high_danger
        FROM pk_shots_against sh
        JOIN event_players ep ON ep.event_id = sh.event_id AND ep.team_id = sh.pk_team_id
        JOIN players pl ON pl.player_id = ep.player_id
        WHERE pl.position IN ('C', 'L', 'R', 'F', 'LW', 'RW')
        ORDER BY sh.shot_id, pl.player_id
        """
        logger.info("Fetching Model 8 forward-shot data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 8 rows: %s", len(self.data))
        return self.data

    def summarize(self):
        rows = []
        for keys, group in self.data.groupby(["player_id", "full_name", "position", "season"]):
            player_id, name, position, season = keys
            total = len(group)
            if total < 150:
                continue
            rows.append(
                {
                    "player_id": player_id,
                    "full_name": name,
                    "position": position,
                    "season": season,
                    "shots_faced": total,
                    "avg_xga_per_shot": float(group["xg"].astype(float).mean()),
                    "high_danger_rate": float(group["high_danger"].astype(float).mean()),
                    "goal_rate": float(group["is_goal"].astype(float).mean()),
                    "dz_event_rate": safe_div((group["zone"] == "DZ").sum(), total),
                    "avg_xga_per_shot_ci": metric_ci(group, lambda x: x["xg"].astype(float).mean()),
                    "high_danger_rate_ci": metric_ci(group, lambda x: x["high_danger"].astype(float).mean()),
                    "goal_rate_ci": metric_ci(group, lambda x: x["is_goal"].astype(float).mean()),
                }
            )
        return pd.DataFrame(rows)

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 8: PK Forward Shot Suppression")
        logger.info("=" * 60)
        self.fetch_data()
        summary = self.summarize()
        scouting_rows = []
        if not summary.empty:
            scouting_rows = export_scouting(
                self.db,
                MODEL_NAME,
                summary,
                "ALL",
                [
                    ("avg_xga_per_shot", False, "shots_faced"),
                    ("high_danger_rate", False, "shots_faced"),
                    ("goal_rate", False, "shots_faced"),
                ],
            )
        results = add_timestamp(
            {
                "model": "PK Forward Shot Suppression",
                "players": summary.to_dict("records") if not summary.empty else [],
                "sample": {"raw_player_shot_rows": int(len(self.data)), "eligible_players": int(len(summary)), "minimum_shots_faced": 150},
                "caveats": [
                    "Per-shot metrics only; no per-60 metrics are used because true TOI is unavailable",
                    "event_players is event-linked context, not verified full on-ice shifts",
                    "Zone-start adjustment is approximated with event zone mix",
                    "This is descriptive scouting, not causal attribution",
                ],
            }
        )
        results["scouting_rows_exported"] = len(scouting_rows)
        results["output_file"] = export_json(results, "model8_forward_shot_suppression.json")
        logger.info("Model 8 output: %s", results["output_file"])
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        ForwardShotSuppressionModel(db).run()
    finally:
        db.close()
