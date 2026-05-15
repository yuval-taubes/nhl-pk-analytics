"""Model 9: PK center faceoff value."""

import logging

import pandas as pd

from db import DatabaseConnection
from models.model_utils import add_timestamp, export_json
from models.player_scouting_utils import export_scouting, metric_ci, safe_div

logger = logging.getLogger(__name__)

MODEL_NAME = "model9_center_faceoff_value"


class CenterFaceoffValueModel:
    """Event-linked center rankings on DZ PK faceoffs."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None

    def fetch_data(self):
        query = """
        WITH faceoffs AS (
            SELECT
                e.event_id,
                e.game_id,
                e.period,
                e.period_time_seconds,
                e.event_team_id AS winner_team_id,
                e.y_norm,
                g.season,
                CASE
                    WHEN split_part(e.strength, 'v', 1)::int < split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(e.strength, 'v', 2)::int < split_part(e.strength, 'v', 1)::int THEN g.home_team_id
                END AS pk_team_id,
                CASE
                    WHEN split_part(e.strength, 'v', 1)::int > split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(e.strength, 'v', 2)::int > split_part(e.strength, 'v', 1)::int THEN g.home_team_id
                END AS pp_team_id
            FROM events e
            JOIN games g ON e.game_id = g.game_id
            WHERE e.event_type = 'faceoff'
              AND e.zone = 'DZ'
              AND e.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
        ),
        xga AS (
            SELECT
                f.event_id,
                COALESCE(SUM(s.xg), 0) AS xga_20
            FROM faceoffs f
            LEFT JOIN events se ON se.game_id = f.game_id
              AND se.period = f.period
              AND se.event_team_id = f.pp_team_id
              AND se.period_time_seconds BETWEEN f.period_time_seconds AND f.period_time_seconds + 20
            LEFT JOIN shots s ON s.event_id = se.event_id
            GROUP BY f.event_id
        )
        SELECT DISTINCT ON (f.event_id, pl.player_id)
            pl.player_id,
            pl.full_name,
            pl.position,
            f.season,
            f.game_id,
            f.event_id,
            f.y_norm,
            CASE WHEN f.y_norm < 37 THEN 'left' WHEN f.y_norm > 48 THEN 'right' ELSE 'center_unknown' END AS circle_side,
            CASE WHEN f.winner_team_id = f.pk_team_id THEN 1 ELSE 0 END AS win,
            x.xga_20
        FROM faceoffs f
        JOIN event_players ep ON ep.event_id = f.event_id AND ep.team_id = f.pk_team_id
        JOIN players pl ON pl.player_id = ep.player_id
        LEFT JOIN xga x ON x.event_id = f.event_id
        WHERE pl.position IN ('C', 'F')
        ORDER BY f.event_id, pl.player_id
        """
        logger.info("Fetching Model 9 center faceoff data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 9 rows: %s", len(self.data))
        return self.data

    def summarize(self):
        if self.data.empty:
            return pd.DataFrame()
        global_win = self.data[self.data["win"] == 1]["xga_20"].astype(float).mean()
        global_loss = self.data[self.data["win"] == 0]["xga_20"].astype(float).mean()
        avg_xga_differential = float((global_loss or 0) - (global_win or 0))

        rows = []
        for keys, group in self.data.groupby(["player_id", "full_name", "position", "season"]):
            player_id, name, position, season = keys
            total = len(group)
            if total < 50:
                continue
            win_rate = float(group["win"].astype(float).mean())
            left = group[group["circle_side"] == "left"]
            right = group[group["circle_side"] == "right"]
            rows.append(
                {
                    "player_id": player_id,
                    "full_name": name,
                    "position": position,
                    "season": season,
                    "faceoffs": total,
                    "win_rate": win_rate,
                    "win_rate_left": float(left["win"].astype(float).mean()) if not left.empty else None,
                    "win_rate_right": float(right["win"].astype(float).mean()) if not right.empty else None,
                    "faceoff_value_added": float((win_rate - 0.45) * avg_xga_differential * (total / 60)),
                    "win_rate_ci": metric_ci(group, lambda x: x["win"].astype(float).mean()),
                }
            )
        return pd.DataFrame(rows)

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 9: PK Center Faceoff Value")
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
                    ("win_rate", True, "faceoffs"),
                    ("faceoff_value_added", True, "faceoffs"),
                ],
            )
        results = add_timestamp(
            {
                "model": "PK Center Faceoff Value",
                "players": summary.to_dict("records") if not summary.empty else [],
                "sample": {"raw_player_faceoff_rows": int(len(self.data)), "eligible_players": int(len(summary)), "minimum_faceoffs": 50},
                "caveats": [
                    "Faceoff participant is inferred from event_players and may include non-centers tagged on the event",
                    "Faceoff winner is inferred from event_team_id",
                    "Handedness data is unavailable",
                    "faceoff_value_added uses faceoff count scaling, not TOI",
                    "This is descriptive scouting, not causal attribution",
                ],
            }
        )
        results["scouting_rows_exported"] = len(scouting_rows)
        results["output_file"] = export_json(results, "model9_center_faceoff_value.json")
        logger.info("Model 9 output: %s", results["output_file"])
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        CenterFaceoffValueModel(db).run()
    finally:
        db.close()
