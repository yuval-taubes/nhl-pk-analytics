#!/usr/bin/env python3
"""Validate MoneyPuck v2 imports and derived PK counts."""

from __future__ import annotations

import json
import logging

import pandas as pd

from db import DatabaseConnection
from moneypuck.features import PK_SHOTS_AGAINST_WHERE, PK_SHOTS_FOR_WHERE


logger = logging.getLogger(__name__)


VALIDATED_TABLES = [
    "mp_shots",
    "mp_team_games",
    "mp_skaters_season",
    "mp_goalies_season",
    "mp_teams_season",
]


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
    for table in VALIDATED_TABLES:
        stats = db.query_to_df(
            f"""
            SELECT
                COUNT(*) AS rows,
                MIN(season) AS first_season,
                MAX(season) AS latest_season
            FROM {table}
            """
        ).iloc[0]
        count = int(stats["rows"])
        report["tables"][table] = {
            "rows": count,
            "first_season": int(stats["first_season"]) if not pd.isna(stats["first_season"]) else None,
            "latest_season": int(stats["latest_season"]) if not pd.isna(stats["latest_season"]) else None,
        }
        if count == 0:
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
