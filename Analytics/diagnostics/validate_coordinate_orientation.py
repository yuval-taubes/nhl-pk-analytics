"""Compare shot-side nearest-net xG convention to home-perspective rink teams.

The xG model currently uses the nearest net to the shot location. That is a
reasonable modeling convention only if normalized shots mostly land near the
shooting team's offensive end. This diagnostic checks that assumption without
reusing the xG feature code.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db import DatabaseConnection


REPORT_PATH = os.path.join("reports", "latest_coordinate_orientation.md")


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
            WITH shot_context AS (
                SELECT
                    e.period,
                    e.strength,
                    CASE WHEN e.event_team_id = g.home_team_id THEN 'home' ELSE 'away' END AS shooting_side,
                    CASE
                        WHEN e.event_team_id = g.home_team_id THEN 189
                        WHEN e.event_team_id = g.away_team_id THEN 11
                    END AS home_perspective_target_net,
                    CASE
                        WHEN ABS(s.x_norm - 11) <= ABS(s.x_norm - 189) THEN 11
                        ELSE 189
                    END AS nearest_net
                FROM shots s
                JOIN events e ON s.event_id = e.event_id
                JOIN games g ON e.game_id = g.game_id
                WHERE s.x_norm IS NOT NULL
                  AND e.event_team_id IS NOT NULL
            )
            SELECT
                shooting_side,
                home_perspective_target_net,
                nearest_net,
                COUNT(*) AS shots
            FROM shot_context
            GROUP BY shooting_side, home_perspective_target_net, nearest_net
            ORDER BY shooting_side, shots DESC
            """
        )

        mismatch = db.query_to_df(
            """
            WITH shot_context AS (
                SELECT
                    CASE
                        WHEN e.event_team_id = g.home_team_id THEN 189
                        WHEN e.event_team_id = g.away_team_id THEN 11
                    END AS home_perspective_target_net,
                    CASE
                        WHEN ABS(s.x_norm - 11) <= ABS(s.x_norm - 189) THEN 11
                        ELSE 189
                    END AS nearest_net
                FROM shots s
                JOIN events e ON s.event_id = e.event_id
                JOIN games g ON e.game_id = g.game_id
                WHERE s.x_norm IS NOT NULL
                  AND e.event_team_id IS NOT NULL
            )
            SELECT
                COUNT(*) AS total_shots,
                COUNT(*) FILTER (WHERE home_perspective_target_net <> nearest_net) AS mismatched_shots
            FROM shot_context
            """
        )
    finally:
        db.close()

    total_shots = int(mismatch.loc[0, "total_shots"])
    mismatched_shots = int(mismatch.loc[0, "mismatched_shots"])
    mismatch_rate = mismatched_shots / total_shots if total_shots else 0
    status = "PASS" if mismatch_rate <= 0.05 else "REVIEW"

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    report = [
        "# Coordinate Orientation Validation",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Status: **{status}**",
        "",
        "Convention checked: home-team shots should usually be nearest the x=189 net; away-team shots should usually be nearest the x=11 net.",
        "",
        f"Total shots checked: `{total_shots}`",
        f"Nearest-net mismatches: `{mismatched_shots}`",
        f"Mismatch rate: `{mismatch_rate:.2%}`",
        "",
        "## Summary",
        "",
        _markdown_table(
            summary.to_dict("records"),
            ["shooting_side", "home_perspective_target_net", "nearest_net", "shots"],
        ),
        "",
        "## Model Implication",
        "",
        "The xG model may use nearest-net distance only if this report stays low-mismatch. "
        "If the mismatch rate is high, coordinate orientation must be fixed or the model must use a different target-net rule.",
        "",
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"{status}: wrote {REPORT_PATH}")
    if status == "REVIEW":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
