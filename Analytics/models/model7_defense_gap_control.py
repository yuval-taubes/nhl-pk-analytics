"""Model 7: PK defenseman disruption and shot blocking.

Blue-line gap control requires player positioning. This supported model ranks
defensemen by directly tagged PK disruption events.
"""

import logging

import pandas as pd

from db import DatabaseConnection
from models.model_utils import add_timestamp, export_json
from models.player_scouting_utils import export_scouting, metric_ci

logger = logging.getLogger(__name__)
MODEL_NAME = "model7_defense_disruption"


class DefenseGapControlModel:
    """Participant-based PK defenseman disruption profile."""

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
            e.event_type,
            COALESCE(s.xg, 0) AS shot_xg,
            CASE WHEN e.event_type = 'blocked-shot' THEN 1 ELSE 0 END AS blocked_shot,
            CASE WHEN e.event_type = 'takeaway' THEN 1 ELSE 0 END AS takeaway,
            CASE WHEN e.event_type = 'hit' THEN 1 ELSE 0 END AS hit,
            CASE WHEN e.event_type = 'giveaway' THEN 1 ELSE 0 END AS giveaway,
            CASE WHEN e.event_type = 'penalty' THEN 1 ELSE 0 END AS penalty
        FROM events e
        JOIN games g ON e.game_id = g.game_id
        JOIN event_players ep ON ep.event_id = e.event_id
        JOIN players pl ON pl.player_id = ep.player_id
        LEFT JOIN shots s ON s.event_id = e.event_id
        WHERE e.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
          AND ep.team_id = CASE
                WHEN split_part(e.strength, 'v', 1)::int < split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                WHEN split_part(e.strength, 'v', 2)::int < split_part(e.strength, 'v', 1)::int THEN g.home_team_id
          END
          AND pl.position IN ('D', 'LD', 'RD')
          AND e.event_type IN ('blocked-shot', 'takeaway', 'hit', 'giveaway', 'penalty')
        """
        logger.info("Fetching Model 7 PK defenseman events...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 7 rows: %s", len(self.data))
        return self.data

    def summarize(self):
        rows = []
        for keys, group in self.data.groupby(["player_id", "full_name", "position"]):
            player_id, name, position = keys
            total = len(group)
            if total < 50:
                continue
            rows.append(
                {
                    "player_id": player_id,
                    "full_name": name,
                    "position": position,
                    "season": "ALL",
                    "defensive_events": total,
                    "block_rate": float(group["blocked_shot"].mean()),
                    "takeaway_rate": float(group["takeaway"].mean()),
                    "disruption_rate": float((group["blocked_shot"] + group["takeaway"] + group["hit"]).clip(upper=1).mean()),
                    "negative_event_rate": float((group["giveaway"] + group["penalty"]).clip(upper=1).mean()),
                    "avg_blocked_shot_xg": float(group[group["blocked_shot"] == 1]["shot_xg"].astype(float).mean()) if (group["blocked_shot"] == 1).any() else 0,
                    "block_rate_ci": metric_ci(group, lambda x: x["blocked_shot"].mean()),
                    "disruption_rate_ci": metric_ci(group, lambda x: (x["blocked_shot"] + x["takeaway"] + x["hit"]).clip(upper=1).mean()),
                    "negative_event_rate_ci": metric_ci(group, lambda x: (x["giveaway"] + x["penalty"]).clip(upper=1).mean()),
                }
            )
        return pd.DataFrame(rows)

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 7: PK Defenseman Disruption Events")
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
                    ("block_rate", True, "defensive_events"),
                    ("disruption_rate", True, "defensive_events"),
                    ("negative_event_rate", False, "defensive_events"),
                ],
            )
        results = add_timestamp(
            {
                "model": "PK Defenseman Disruption Events",
                "players": summary.to_dict("records") if not summary.empty else [],
                "sample": {"raw_events": int(len(self.data)), "eligible_players": int(len(summary)), "minimum_events": 50},
                "caveats": [
                    "Original gap-control model requires player positioning and is not estimated",
                    "This ranks directly tagged PK defensive events only",
                    "No per-60 rates are reported because true TOI is unavailable",
                    "This is descriptive, not causal attribution",
                ],
            }
        )
        results["scouting_rows_exported"] = len(scouting_rows)
        results["output_file"] = export_json(results, "model7_defense_disruption.json")
        logger.info("Model 7 output: %s", results["output_file"])
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        DefenseGapControlModel(db).run()
    finally:
        db.close()
