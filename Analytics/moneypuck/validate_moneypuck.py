#!/usr/bin/env python3
"""Validate MoneyPuck v2 imports and derived PK counts."""

from __future__ import annotations

import json
import logging

from db import DatabaseConnection
from moneypuck.features import PK_SHOTS_AGAINST_WHERE, PK_SHOTS_FOR_WHERE


logger = logging.getLogger(__name__)


EXPECTED_LOCAL_ROWS = {
    "mp_shots": 786244,
    "mp_team_games": 232170,
    "mp_skaters_season": 76655,
    "mp_goalies_season": 8020,
    "mp_teams_season": 2610,
}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        report = validate(db)
        print(json.dumps(report, indent=2))
        return report
    finally:
        db.close()


def validate(db):
    report = {"tables": {}, "derived": {}, "status": "ok"}
    for table, expected in EXPECTED_LOCAL_ROWS.items():
        count = int(db.query_to_df(f"SELECT COUNT(*) AS n FROM {table}")["n"].iloc[0])
        report["tables"][table] = {"rows": count, "expected_local_rows": expected, "matches_expected": count == expected}
        if count != expected:
            report["status"] = "warning"

    dupes = db.query_to_df(
        """
        SELECT COUNT(*) AS n
        FROM (
            SELECT season, game_id, shot_id, COUNT(*)
            FROM mp_shots
            GROUP BY season, game_id, shot_id
            HAVING COUNT(*) > 1
        ) d
        """
    )
    report["derived"]["duplicate_shot_keys"] = int(dupes["n"].iloc[0])

    pk_against = db.query_to_df(f"SELECT COUNT(*) AS n FROM mp_shots WHERE {PK_SHOTS_AGAINST_WHERE}")
    pk_for = db.query_to_df(f"SELECT COUNT(*) AS n FROM mp_shots WHERE {PK_SHOTS_FOR_WHERE}")
    report["derived"]["pk_shots_against"] = int(pk_against["n"].iloc[0])
    report["derived"]["pk_shots_for"] = int(pk_for["n"].iloc[0])

    strength = db.query_to_df(
        """
        SELECT strength_state, COUNT(*)::int AS shots
        FROM mp_shots
        GROUP BY strength_state
        ORDER BY shots DESC
        LIMIT 12
        """
    )
    report["derived"]["top_strength_states"] = strength.to_dict("records")
    return report


if __name__ == "__main__":
    main()
