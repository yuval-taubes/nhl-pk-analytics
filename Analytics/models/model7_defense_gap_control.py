"""Model 7: PK defenseman gap control."""

import logging

import pandas as pd

from db import DatabaseConnection
from models.model_utils import add_timestamp, export_json
from models.player_scouting_utils import export_scouting, metric_ci, safe_div

logger = logging.getLogger(__name__)

MODEL_NAME = "model7_defense_gap_control"


class DefenseGapControlModel:
    """Event-linked defenseman rankings on opponent entries against the PK."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None

    def fetch_data(self):
        query = """
        WITH pp_entries AS (
            SELECT
                p.possession_id,
                p.game_id,
                g.season,
                p.team_id AS pp_team_id,
                p.entry_type,
                p.entry_x,
                COALESCE(p.xg_sum, 0) AS xga_entry,
                p.end_type,
                se.event_idx AS start_idx,
                ee.event_idx AS end_idx,
                se.period_time_seconds AS start_time,
                ee.period_time_seconds AS end_time,
                CASE
                    WHEN split_part(p.strength, 'v', 1)::int < split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int < split_part(p.strength, 'v', 1)::int THEN g.home_team_id
                END AS pk_team_id
            FROM possessions p
            JOIN games g ON p.game_id = g.game_id
            JOIN events se ON p.start_event_id = se.event_id
            JOIN events ee ON p.end_event_id = ee.event_id
            WHERE p.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
              AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
              AND p.team_id = CASE
                    WHEN split_part(p.strength, 'v', 1)::int > split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int > split_part(p.strength, 'v', 1)::int THEN g.home_team_id
              END
        )
        SELECT DISTINCT ON (pl.player_id, pe.possession_id)
            pl.player_id,
            pl.full_name,
            pl.position,
            pe.season,
            pe.game_id,
            pe.possession_id,
            pe.entry_type,
            pe.entry_x,
            CASE WHEN pe.end_type = 'CLEAR' AND (pe.end_time - pe.start_time) <= 3 THEN 1 ELSE 0 END AS denied_within_3s,
            pe.xga_entry,
            CASE WHEN pe.entry_x < 100 THEN 'left' ELSE 'right' END AS entry_side
        FROM pp_entries pe
        JOIN events e ON e.game_id = pe.game_id AND e.event_idx BETWEEN pe.start_idx AND pe.end_idx
        JOIN event_players ep ON ep.event_id = e.event_id AND ep.team_id = pe.pk_team_id
        JOIN players pl ON pl.player_id = ep.player_id
        WHERE pl.position IN ('D', 'LD', 'RD')
        ORDER BY pl.player_id, pe.possession_id, e.event_idx
        """
        logger.info("Fetching Model 7 defense-entry data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 7 rows: %s", len(self.data))
        return self.data

    def summarize(self):
        rows = []
        for keys, group in self.data.groupby(["player_id", "full_name", "position", "season"]):
            player_id, name, position, season = keys
            total = len(group)
            if total < 50:
                continue
            controlled = (group["entry_type"] == "CONTROLLED").sum()
            rows.append(
                {
                    "player_id": player_id,
                    "full_name": name,
                    "position": position,
                    "season": season,
                    "entries_faced": total,
                    "denial_rate": float(group["denied_within_3s"].astype(float).mean()),
                    "controlled_entry_rate": safe_div(controlled, total),
                    "avg_xga_per_entry": float(group["xga_entry"].astype(float).mean()),
                    "left_entries": int((group["entry_side"] == "left").sum()),
                    "right_entries": int((group["entry_side"] == "right").sum()),
                    "denial_rate_ci": metric_ci(group, lambda x: x["denied_within_3s"].astype(float).mean()),
                    "controlled_entry_rate_ci": metric_ci(group, lambda x: (x["entry_type"] == "CONTROLLED").mean()),
                    "avg_xga_per_entry_ci": metric_ci(group, lambda x: x["xga_entry"].astype(float).mean()),
                }
            )
        return pd.DataFrame(rows)

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 7: PK Defenseman Gap Control")
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
                    ("denial_rate", True, "entries_faced"),
                    ("controlled_entry_rate", False, "entries_faced"),
                    ("avg_xga_per_entry", False, "entries_faced"),
                ],
            )
        results = add_timestamp(
            {
                "model": "PK Defenseman Gap Control",
                "players": summary.to_dict("records") if not summary.empty else [],
                "sample": {"raw_player_entry_rows": int(len(self.data)), "eligible_players": int(len(summary)), "minimum_entries_faced": 50},
                "caveats": [
                    "event_players is event-linked context, not full tracking/on-ice shifts",
                    "Denial is approximated as CLEAR within 3 seconds of entry",
                    "Entry side uses entry_x split at center ice",
                    "This is descriptive scouting, not causal attribution",
                ],
            }
        )
        results["scouting_rows_exported"] = len(scouting_rows)
        results["output_file"] = export_json(results, "model7_defense_gap_control.json")
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
