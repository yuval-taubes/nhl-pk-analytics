"""Validate special-teams manpower conventions used by analytics models.

The NHL feed exposes `home_skaters` and `away_skaters`, while this project also
stores a compact `strength` string. Local ingestion currently stores that string
as `away_skaters v home_skaters`. This diagnostic makes that convention explicit
and fails loudly if the string stops matching the numeric skater columns.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db import DatabaseConnection


SPECIAL_TEAMS_STATES = ("4v5", "5v4", "3v5", "5v3", "3v4", "4v3")
REPORT_PATH = os.path.join("reports", "latest_manpower_context.md")


def _markdown_table(rows, columns):
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def main():
    db = DatabaseConnection()
    db.connect()
    try:
        summary = db.query_to_df(
            """
            SELECT strength, home_skaters, away_skaters, COUNT(*) AS events
            FROM events
            WHERE strength = ANY(%s)
            GROUP BY strength, home_skaters, away_skaters
            ORDER BY events DESC
            """,
            (list(SPECIAL_TEAMS_STATES),),
        )

        mismatch = db.query_to_df(
            """
            SELECT COUNT(*) AS mismatched_events
            FROM events
            WHERE strength = ANY(%s)
              AND (
                split_part(strength, 'v', 1)::int <> away_skaters
                OR split_part(strength, 'v', 2)::int <> home_skaters
              )
            """,
            (list(SPECIAL_TEAMS_STATES),),
        )

        missing = db.query_to_df(
            """
            SELECT COUNT(*) AS missing_skaters
            FROM events
            WHERE strength = ANY(%s)
              AND (home_skaters IS NULL OR away_skaters IS NULL)
            """,
            (list(SPECIAL_TEAMS_STATES),),
        )
    finally:
        db.close()

    mismatch_count = int(mismatch.loc[0, "mismatched_events"])
    missing_count = int(missing.loc[0, "missing_skaters"])
    status = "PASS" if mismatch_count == 0 and missing_count == 0 else "FAIL"

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    report = [
        "# Manpower Context Validation",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Status: **{status}**",
        "",
        "Convention checked: `strength` is stored as `away_skaters v home_skaters`.",
        "",
        f"Mismatched special-teams events: `{mismatch_count}`",
        f"Special-teams events with missing skater counts: `{missing_count}`",
        "",
        "## Special-Teams Strength Summary",
        "",
        _markdown_table(
            summary.to_dict("records"),
            ["strength", "home_skaters", "away_skaters", "events"],
        ),
        "",
        "## Model Implication",
        "",
        "PP team inference from `strength` is valid only under the away-v-home convention above. "
        "Future models should prefer a shared context view/helper over repeating string parsing.",
        "",
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"{status}: wrote {REPORT_PATH}")
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
