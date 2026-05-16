"""Regression check for one canonical ingested NHL game.

This script is intentionally database-backed. It should be run after ingestion
or possession-tracking changes to verify that core derived counts did not drift
unexpectedly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db import DatabaseConnection


DEFAULT_EXPECTED = Path("diagnostics") / "golden_games" / "2022020154.json"
SPECIAL_TEAMS = ("4v5", "5v4", "3v5", "5v3", "3v4", "4v3")


def _records(df):
    return json.loads(df.to_json(orient="records"))


def fetch_golden_game(db, game_id):
    summary = db.query_to_df(
        """
        SELECT
            g.game_id,
            g.season,
            g.game_date::text AS game_date,
            ht.abbreviation AS home_team,
            at.abbreviation AS away_team,
            COUNT(DISTINCT e.event_id)::int AS events,
            COUNT(DISTINCT s.shot_id)::int AS shots,
            COUNT(DISTINCT s.shot_id) FILTER (WHERE s.is_goal)::int AS goals,
            COUNT(DISTINCT p.possession_id)::int AS possessions,
            COUNT(DISTINCT p.possession_id) FILTER (WHERE p.strength = ANY(%s))::int AS special_teams_possessions,
            COUNT(DISTINCT s.shot_id) FILTER (WHERE s.possession_id IS NOT NULL)::int AS linked_shots,
            COUNT(DISTINCT s.shot_id) FILTER (WHERE s.xg IS NOT NULL)::int AS shots_with_xg
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        LEFT JOIN events e ON e.game_id = g.game_id
        LEFT JOIN shots s ON s.event_id = e.event_id
        LEFT JOIN possessions p ON p.game_id = g.game_id
        WHERE g.game_id = %s
        GROUP BY g.game_id, g.season, g.game_date, ht.abbreviation, at.abbreviation
        """,
        (list(SPECIAL_TEAMS), game_id),
    )

    if summary.empty:
        raise ValueError(f"Game {game_id} was not found in the database")

    strength_counts = db.query_to_df(
        """
        SELECT strength, COUNT(*)::int AS events
        FROM events
        WHERE game_id = %s
        GROUP BY strength
        ORDER BY strength
        """,
        (game_id,),
    )

    possession_counts = db.query_to_df(
        """
        SELECT
            strength,
            entry_type,
            COUNT(*)::int AS possessions,
            COALESCE(SUM(shot_count), 0)::int AS shots,
            COALESCE(SUM(goal_count), 0)::int AS goals
        FROM possessions
        WHERE game_id = %s
        GROUP BY strength, entry_type
        ORDER BY strength, entry_type
        """,
        (game_id,),
    )

    return {
        "summary": summary.to_dict("records")[0],
        "strength_counts": _records(strength_counts),
        "possession_counts": _records(possession_counts),
    }


def compare(expected, actual):
    mismatches = []

    def walk(path, left, right):
        if isinstance(left, dict):
            for key in sorted(left):
                if key not in right:
                    mismatches.append(f"{path}.{key}: missing from actual")
                else:
                    walk(f"{path}.{key}", left[key], right[key])
            for key in sorted(set(right) - set(left)):
                mismatches.append(f"{path}.{key}: unexpected actual value {right[key]!r}")
            return

        if isinstance(left, list):
            if len(left) != len(right):
                mismatches.append(f"{path}: expected {len(left)} rows, got {len(right)}")
                return
            for index, (left_item, right_item) in enumerate(zip(left, right)):
                walk(f"{path}[{index}]", left_item, right_item)
            return

        if left != right:
            mismatches.append(f"{path}: expected {left!r}, got {right!r}")

    walk("golden_game", expected, actual)
    return mismatches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", default=str(DEFAULT_EXPECTED))
    parser.add_argument("--write", action="store_true", help="Write current DB counts as the expected fixture")
    args = parser.parse_args()

    expected_path = Path(args.expected)
    game_id = int(expected_path.stem)

    db = DatabaseConnection()
    db.connect()
    try:
        actual = fetch_golden_game(db, game_id)
    finally:
        db.close()

    if args.write:
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {expected_path}")
        return

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    mismatches = compare(expected, actual)
    if mismatches:
        print("GOLDEN GAME REGRESSION FAILED")
        for mismatch in mismatches:
            print(f"- {mismatch}")
        raise SystemExit(1)

    print(f"PASS: game {game_id} matches {expected_path}")


if __name__ == "__main__":
    main()
