"""Model 10: Net-front defenseman performance."""

import logging

import pandas as pd

from db import DatabaseConnection
from models.model_utils import add_timestamp, export_json
from models.player_scouting_utils import export_scouting, metric_ci

logger = logging.getLogger(__name__)

MODEL_NAME = "model10_net_front_defense"


class NetFrontDefenseModel:
    """Event-linked defenseman rankings on high-danger/net-front shots against."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None

    def fetch_data(self):
        query = """
        WITH shot_context AS (
            SELECT
                s.shot_id,
                s.event_id,
                s.x_norm,
                s.y_norm,
                s.xg,
                e.game_id,
                e.event_idx,
                e.event_team_id AS pp_team_id,
                g.season,
                CASE
                    WHEN split_part(e.strength, 'v', 1)::int < split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(e.strength, 'v', 2)::int < split_part(e.strength, 'v', 1)::int THEN g.home_team_id
                END AS pk_team_id,
                LAG(e.event_type) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_event_type,
                LAG(e.event_team_id) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_event_team_id
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
        SELECT DISTINCT ON (sc.shot_id, pl.player_id)
            pl.player_id,
            pl.full_name,
            pl.position,
            sc.season,
            sc.game_id,
            sc.shot_id,
            sc.xg,
            SQRT(
                POWER(sc.x_norm - CASE WHEN ABS(sc.x_norm - 11) <= ABS(sc.x_norm - 189) THEN 11 ELSE 189 END, 2)
                + POWER(sc.y_norm - 42.5, 2)
            ) AS distance_to_net,
            CASE
                WHEN sc.prev_event_type IN ('shot-on-goal', 'missed-shot', 'blocked-shot')
                 AND sc.prev_event_team_id = sc.pp_team_id THEN 1 ELSE 0
            END AS is_rebound
        FROM shot_context sc
        JOIN event_players ep ON ep.event_id = sc.event_id AND ep.team_id = sc.pk_team_id
        JOIN players pl ON pl.player_id = ep.player_id
        WHERE pl.position IN ('D', 'LD', 'RD')
        ORDER BY sc.shot_id, pl.player_id
        """
        logger.info("Fetching Model 10 net-front defense data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 10 rows: %s", len(self.data))
        return self.data

    def summarize(self):
        rows = []
        for keys, group in self.data.groupby(["player_id", "full_name", "position"]):
            player_id, name, position = keys
            total = len(group)
            if total < 100:
                continue
            high_danger = ((group["xg"].astype(float) > 0.15) | (group["distance_to_net"].astype(float) < 20)).astype(int)
            rows.append(
                {
                    "player_id": player_id,
                    "full_name": name,
                    "position": position,
                    "season": "ALL",
                    "shots_faced": total,
                    "high_danger_shots_per_shot": float(high_danger.mean()),
                    "rebound_shots_per_shot": float(group["is_rebound"].astype(float).mean()),
                    "avg_xga_per_shot": float(group["xg"].astype(float).mean()),
                    "high_danger_shots_per_shot_ci": metric_ci(group.assign(high_danger=high_danger), lambda x: x["high_danger"].astype(float).mean()),
                    "rebound_shots_per_shot_ci": metric_ci(group, lambda x: x["is_rebound"].astype(float).mean()),
                    "avg_xga_per_shot_ci": metric_ci(group, lambda x: x["xg"].astype(float).mean()),
                }
            )
        return pd.DataFrame(rows)

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 10: Net-Front Defenseman Performance")
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
                    ("high_danger_shots_per_shot", False, "shots_faced"),
                    ("rebound_shots_per_shot", False, "shots_faced"),
                    ("avg_xga_per_shot", False, "shots_faced"),
                ],
            )
        results = add_timestamp(
            {
                "model": "Net-Front Defenseman Performance",
                "players": summary.to_dict("records") if not summary.empty else [],
                "sample": {"raw_player_shot_rows": int(len(self.data)), "eligible_players": int(len(summary)), "minimum_shots_faced": 100},
                "caveats": [
                    "event_players is event-linked context, not verified full on-ice shifts",
                    "High danger is xG > 0.15 or inferred distance < 20 feet",
                    "Rebounds are inferred from immediately previous shot event by same PP team",
                    "This is descriptive scouting, not causal attribution",
                ],
            }
        )
        results["scouting_rows_exported"] = len(scouting_rows)
        results["output_file"] = export_json(results, "model10_net_front_defense.json")
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
