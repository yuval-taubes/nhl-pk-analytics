"""Model 3: Intentional clearance for offensive-zone faceoff."""

import logging

from db import DatabaseConnection
from models.model_utils import add_timestamp, bootstrap_ci_by_game, export_json

logger = logging.getLogger(__name__)


class IntentionalClearanceFaceoffModel:
    """Expected-value comparison of keeping play alive versus OZ whistle/faceoff."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None

    def fetch_data(self):
        query = """
        WITH pk_context AS (
            SELECT
                e.*,
                g.home_team_id,
                g.away_team_id,
                LEAD(e.event_type) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS next_event_type,
                LEAD(e.zone) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS next_zone,
                LEAD(e.event_team_id) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS next_team_id,
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
            WHERE e.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
        ),
        oz_pk_events AS (
            SELECT *
            FROM pk_context
            WHERE event_team_id = pk_team_id
              AND zone = 'OZ'
        ),
        path_a AS (
            SELECT
                e.event_id,
                e.game_id,
                'maintain_play' AS path,
                COALESCE(SUM(CASE WHEN se.event_team_id = e.pk_team_id THEN s.xg ELSE 0 END), 0) AS pk_xg_20,
                COALESCE(SUM(CASE WHEN se.event_team_id = e.pp_team_id THEN s.xg ELSE 0 END), 0) AS pp_xg_20
            FROM oz_pk_events e
            LEFT JOIN events se
              ON se.game_id = e.game_id
             AND se.period = e.period
             AND se.period_time_seconds BETWEEN e.period_time_seconds AND e.period_time_seconds + 20
            LEFT JOIN shots s ON s.event_id = se.event_id
            WHERE NOT (
                e.event_type ILIKE '%stoppage%'
                OR e.event_type IN ('puck-out-of-play', 'puck-in-crowd', 'puck-in-netting')
                OR (e.next_event_type = 'faceoff' AND e.next_zone = 'OZ')
            )
            GROUP BY e.event_id, e.game_id
        ),
        path_b AS (
            SELECT
                e.event_id,
                e.game_id,
                'out_of_play' AS path,
                COALESCE(SUM(CASE WHEN se.event_team_id = e.pk_team_id THEN s.xg ELSE 0 END), 0) AS pk_xg_20,
                COALESCE(SUM(CASE WHEN se.event_team_id = e.pp_team_id THEN s.xg ELSE 0 END), 0) AS pp_xg_20
            FROM oz_pk_events e
            LEFT JOIN events se
              ON se.game_id = e.game_id
             AND se.period = e.period
             AND se.period_time_seconds BETWEEN e.period_time_seconds AND e.period_time_seconds + 20
            LEFT JOIN shots s ON s.event_id = se.event_id
            WHERE (
                e.event_type ILIKE '%stoppage%'
                OR e.event_type IN ('puck-out-of-play', 'puck-in-crowd', 'puck-in-netting')
                OR (e.next_event_type = 'faceoff' AND e.next_zone = 'OZ')
            )
            GROUP BY e.event_id, e.game_id
        )
        SELECT * FROM path_a
        UNION ALL
        SELECT * FROM path_b
        """
        logger.info("Fetching intentional-clearance proxy data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 3 sample: %s PK OZ situations", len(self.data))
        return self.data

    def _faceoff_ev(self):
        query = """
        WITH f AS (
            SELECT
                e.event_id,
                e.game_id,
                e.period,
                e.period_time_seconds,
                e.event_team_id,
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
              AND e.zone = 'OZ'
              AND e.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
        )
        SELECT
            COUNT(*) AS n_faceoffs,
            AVG(CASE WHEN event_team_id = pk_team_id THEN 1.0 ELSE 0.0 END) AS pk_win_prob,
            AVG(CASE WHEN event_team_id = pk_team_id THEN x.pk_xg_20 END) AS avg_xg_after_win,
            AVG(CASE WHEN event_team_id <> pk_team_id THEN x.pp_xg_20 END) AS avg_xga_after_loss
        FROM f
        LEFT JOIN LATERAL (
            SELECT
                COALESCE(SUM(CASE WHEN se.event_team_id = f.pk_team_id THEN s.xg ELSE 0 END), 0) AS pk_xg_20,
                COALESCE(SUM(CASE WHEN se.event_team_id = f.pp_team_id THEN s.xg ELSE 0 END), 0) AS pp_xg_20
            FROM events se
            LEFT JOIN shots s ON s.event_id = se.event_id
            WHERE se.game_id = f.game_id
              AND se.period = f.period
              AND se.period_time_seconds BETWEEN f.period_time_seconds AND f.period_time_seconds + 20
        ) x ON TRUE
        """
        df = self.db.query_to_df(query)
        if df.empty:
            return {}
        row = df.to_dict("records")[0]
        p_win = float(row["pk_win_prob"] or 0)
        win_xg = float(row["avg_xg_after_win"] or 0)
        loss_xga = float(row["avg_xga_after_loss"] or 0)
        return {
            "n_faceoffs": int(row["n_faceoffs"] or 0),
            "pk_oz_faceoff_win_probability": p_win,
            "avg_xg_after_pk_win": win_xg,
            "avg_xga_after_pk_loss": loss_xga,
            "ev_out_of_play": p_win * win_xg - (1 - p_win) * loss_xga,
        }

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 3: Intentional Clearance for OZ Faceoff")
        logger.info("=" * 60)
        data = self.fetch_data()

        rows = []
        for path, group in data.groupby("path"):
            net = group["pk_xg_20"].astype(float) - group["pp_xg_20"].astype(float)
            ci = bootstrap_ci_by_game(
                group,
                "game_id",
                lambda x: (x["pk_xg_20"].astype(float) - x["pp_xg_20"].astype(float)).mean(),
                n_bootstrap=200,
            )
            rows.append(
                {
                    "path": path,
                    "n": int(len(group)),
                    "avg_pk_xg_20": float(group["pk_xg_20"].astype(float).mean()),
                    "avg_pp_xg_20": float(group["pp_xg_20"].astype(float).mean()),
                    "avg_net_xg_20": float(net.mean()),
                    "net_xg_ci": ci,
                }
            )

        faceoff_ev = self._faceoff_ev()
        results = add_timestamp(
            {
                "model": "Intentional Clearance for OZ Faceoff",
                "path_summary": rows,
                "oz_faceoff_ev": faceoff_ev,
                "sample": {"n_situations": int(len(data))},
                "caveats": [
                    "Intentional out-of-play is inferred from stoppage/next-faceoff context and is not explicitly tagged",
                    "Rare-event samples may be too small for significance",
                    "Path A is a broad keep-play-alive comparison, not a randomized tactical choice",
                    "This is descriptive EV comparison, not a causal claim",
                ],
            }
        )
        results["output_file"] = export_json(results, "model3_clearance_faceoff.json")
        logger.info("Model 3 output: %s", results["output_file"])
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        IntentionalClearanceFaceoffModel(db).run()
    finally:
        db.close()
