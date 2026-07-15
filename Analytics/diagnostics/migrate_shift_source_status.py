"""Apply shift-source schema changes and conservatively backfill audit status.

Games with stored shift rows are known to have had source data. Games without
rows are marked not_checked because old ingestion did not distinguish an empty
source response from a request failure.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "NhlPkIngest" / "schema.sql"
SHIFTCHART_ENDPOINT = "https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={gameId}"


def main():
    parser = argparse.ArgumentParser(description="Apply or audit shift-source status schema.")
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Run summary queries in a read-only transaction without applying schema or status changes.",
    )
    args = parser.parse_args()

    from db import DatabaseConnection

    db = DatabaseConnection()
    db.connect()
    try:
        with db.conn.cursor() as cursor:
            if args.audit_only:
                cursor.execute("SET TRANSACTION READ ONLY")
            else:
                cursor.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
                cursor.execute(
                    """
                    INSERT INTO game_shift_source_status
                        (game_id, source_status, checked_at, row_count, endpoint_url)
                    SELECT
                        g.game_id,
                        CASE WHEN COUNT(gs.shift_id) > 0 THEN 'available' ELSE 'not_checked' END,
                        NOW(),
                        COUNT(gs.shift_id)::int,
                        REPLACE(%s, '{gameId}', g.game_id::text)
                    FROM games g
                    LEFT JOIN game_shifts gs ON gs.game_id = g.game_id
                    GROUP BY g.game_id
                    ON CONFLICT (game_id) DO NOTHING
                    """,
                    (SHIFTCHART_ENDPOINT,),
                )
            cursor.execute(
                """
                SELECT source_status, COUNT(*)::int AS games, SUM(row_count)::int AS rows
                FROM game_shift_source_status
                GROUP BY source_status
                ORDER BY source_status
                """
            )
            summary = cursor.fetchall()
            cursor.execute(
                """
                SELECT COUNT(*)::int, COUNT(DISTINCT game_id)::int, COUNT(DISTINCT player_id)::int
                FROM pk_shift_player_event_features
                WHERE is_penalty_killing
                """
            )
            feature_summary = cursor.fetchone()
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()

    for status, games, rows in summary:
        print(f"{status}: games={games}, rows={rows}")
    print(
        "pk_shift_player_event_features: "
        f"rows={feature_summary[0]}, games={feature_summary[1]}, players={feature_summary[2]}"
    )


if __name__ == "__main__":
    main()
