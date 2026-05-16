"""Model 10: PK defenseman shot-block profile.

Net-front prevention while on ice is unsupported without shift/player position
data. This model ranks defensemen on directly tagged blocked-shot events.
"""

import logging

import pandas as pd

from db import DatabaseConnection
from models.model_utils import add_timestamp, export_json
from models.player_scouting_utils import export_scouting, metric_ci

logger = logging.getLogger(__name__)
MODEL_NAME = "model10_defense_shot_blocks"


class NetFrontDefenseModel:
    """Participant-based defenseman shot-block profile on the PK."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None

    def fetch_data(self):
        query = """
        SELECT
            pl.player_id,
            pl.full_name,
            pl.position,
            g.season,
            e.game_id,
            e.event_id,
            s.shot_id,
            COALESCE(s.xg, 0) AS blocked_xg,
            SQRT(
                POWER(s.x_norm - CASE WHEN ABS(s.x_norm - 11) <= ABS(s.x_norm - 189) THEN 11 ELSE 189 END, 2)
                + POWER(s.y_norm - 42.5, 2)
            ) AS shot_distance
        FROM events e
        JOIN games g ON e.game_id = g.game_id
        JOIN shots s ON s.event_id = e.event_id
        JOIN event_players ep ON ep.event_id = e.event_id
        JOIN players pl ON pl.player_id = ep.player_id
        WHERE e.event_type = 'blocked-shot'
          AND e.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
          AND ep.team_id = CASE
                WHEN split_part(e.strength, 'v', 1)::int < split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                WHEN split_part(e.strength, 'v', 2)::int < split_part(e.strength, 'v', 1)::int THEN g.home_team_id
          END
          AND pl.position IN ('D', 'LD', 'RD')
        """
        logger.info("Fetching Model 10 PK defenseman blocked-shot data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 10 rows: %s", len(self.data))
        return self.data

    def summarize(self):
        rows = []
        for keys, group in self.data.groupby(["player_id", "full_name", "position"]):
            player_id, name, position = keys
            total = len(group)
            if total < 75:
                continue
            high_danger = ((group["blocked_xg"].astype(float) > 0.10) | (group["shot_distance"].astype(float) < 30)).astype(int)
            rows.append(
                {
                    "player_id": player_id,
                    "full_name": name,
                    "position": position,
                    "season": "ALL",
                    "blocked_shots": total,
                    "avg_blocked_xg": float(group["blocked_xg"].astype(float).mean()),
                    "high_danger_block_rate": float(high_danger.mean()),
                    "avg_block_distance": float(group["shot_distance"].astype(float).mean()),
                    "avg_blocked_xg_ci": metric_ci(group, lambda x: x["blocked_xg"].astype(float).mean()),
                    "high_danger_block_rate_ci": metric_ci(group.assign(high_danger=high_danger), lambda x: x["high_danger"].astype(float).mean()),
                }
            )
        return pd.DataFrame(rows)

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 10: PK Defenseman Shot Blocks")
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
                    ("avg_blocked_xg", True, "blocked_shots"),
                    ("high_danger_block_rate", True, "blocked_shots"),
                    ("avg_block_distance", False, "blocked_shots"),
                ],
            )
        results = add_timestamp(
            {
                "model": "PK Defenseman Shot Blocks",
                "players": summary.to_dict("records") if not summary.empty else [],
                "sample": {"raw_block_rows": int(len(self.data)), "eligible_players": int(len(summary)), "minimum_blocked_shots": 75},
                "caveats": [
                    "Original net-front prevention model is unsupported without on-ice shift/player position data",
                    "This ranks only directly tagged blocked shots by PK defensemen",
                    "High-danger blocks use xG > 0.10 or shot distance < 30 feet",
                    "This is descriptive, not causal attribution",
                ],
            }
        )
        results["scouting_rows_exported"] = len(scouting_rows)
        results["output_file"] = export_json(results, "model10_defense_shot_blocks.json")
        logger.info("Model 10 output: %s", results["output_file"])
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        NetFrontDefenseModel(db).run()
    finally:
        db.close()
