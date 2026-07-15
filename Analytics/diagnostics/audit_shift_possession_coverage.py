"""Audit whether reconstructed possessions can condition shift-age PK models."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from diagnostics.shift_pk_exposure import markdown_table


REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORT_PATH = REPORT_DIR / "latest_shift_possession_coverage.md"
DETAIL_CSV = REPORT_DIR / "latest_shift_possession_coverage_by_game.csv"


def coverage_status(coverage_rate, ambiguous_rate):
    if coverage_rate >= 0.8 and ambiguous_rate <= 0.01:
        return "SUITABLE"
    if coverage_rate >= 0.5 and ambiguous_rate <= 0.03:
        return "PARTIAL"
    return "INSUFFICIENT"


def load_summary(db):
    return db.query_to_df(
        """
        WITH covered_games AS (
            SELECT game_id FROM game_shift_source_status WHERE source_status = 'available'
        ), pp_possessions AS (
            SELECT
                p.*,
                se.event_idx AS start_event_idx,
                ee.event_idx AS end_event_idx
            FROM possessions p
            JOIN games g ON g.game_id = p.game_id
            JOIN events se ON se.event_id = p.start_event_id
            JOIN events ee ON ee.event_id = p.end_event_id
            JOIN covered_games cg ON cg.game_id = p.game_id
            WHERE (
                p.strength IN ('5v4', '5v3', '4v3') AND p.team_id = g.away_team_id
            ) OR (
                p.strength IN ('4v5', '3v5', '3v4') AND p.team_id = g.home_team_id
            )
        ), pk_team_events AS (
            SELECT DISTINCT game_id, event_id, team_id
            FROM pk_shift_player_event_features
            WHERE is_penalty_killing
              AND event_type <> 'goal'
        ), event_matches AS (
            SELECT
                pke.game_id,
                pke.event_id,
                pke.team_id,
                COUNT(pp.possession_id)::int AS possession_matches
            FROM pk_team_events pke
            JOIN events e ON e.event_id = pke.event_id
            LEFT JOIN games g ON g.game_id = pke.game_id
            LEFT JOIN pp_possessions pp
              ON pp.game_id = pke.game_id
             AND pp.team_id = CASE WHEN pke.team_id = g.home_team_id THEN g.away_team_id ELSE g.home_team_id END
             AND e.event_idx BETWEEN pp.start_event_idx AND pp.end_event_idx
            GROUP BY pke.game_id, pke.event_id, pke.team_id
        )
        SELECT
            (SELECT COUNT(*) FROM covered_games)::int AS covered_games,
            (SELECT COUNT(DISTINCT game_id) FROM pp_possessions)::int AS games_with_pp_possessions,
            (SELECT COUNT(*) FROM pp_possessions)::int AS pp_possessions,
            (SELECT COUNT(*) FROM pp_possessions WHERE end_event_idx < start_event_idx)::int AS reversed_possessions,
            (SELECT COUNT(*) FROM pk_team_events)::int AS pk_team_events,
            COUNT(*) FILTER (WHERE possession_matches > 0)::int AS matched_pk_team_events,
            COUNT(*) FILTER (WHERE possession_matches > 1)::int AS ambiguous_pk_team_events,
            ROUND(AVG(possession_matches)::numeric, 3)::float AS avg_matches_per_event
        FROM event_matches
        """
    )


def load_by_game(db):
    return db.query_to_df(
        """
        WITH pp_possessions AS (
            SELECT p.*, se.event_idx AS start_event_idx, ee.event_idx AS end_event_idx
            FROM possessions p
            JOIN games g ON g.game_id = p.game_id
            JOIN events se ON se.event_id = p.start_event_id
            JOIN events ee ON ee.event_id = p.end_event_id
            JOIN game_shift_source_status gsss ON gsss.game_id = p.game_id AND gsss.source_status = 'available'
            WHERE (p.strength IN ('5v4', '5v3', '4v3') AND p.team_id = g.away_team_id)
               OR (p.strength IN ('4v5', '3v5', '3v4') AND p.team_id = g.home_team_id)
        ), pk_team_events AS (
            SELECT DISTINCT game_id, event_id, team_id
            FROM pk_shift_player_event_features
            WHERE is_penalty_killing AND event_type <> 'goal'
        ), matches AS (
            SELECT pke.game_id, pke.event_id, COUNT(pp.possession_id)::int AS possession_matches
            FROM pk_team_events pke
            JOIN events e ON e.event_id = pke.event_id
            JOIN games g ON g.game_id = pke.game_id
            LEFT JOIN pp_possessions pp
              ON pp.game_id = pke.game_id
             AND pp.team_id = CASE WHEN pke.team_id = g.home_team_id THEN g.away_team_id ELSE g.home_team_id END
             AND e.event_idx BETWEEN pp.start_event_idx AND pp.end_event_idx
            GROUP BY pke.game_id, pke.event_id
        )
        SELECT
            m.game_id,
            COUNT(*)::int AS pk_team_events,
            COUNT(*) FILTER (WHERE possession_matches > 0)::int AS matched_events,
            COUNT(*) FILTER (WHERE possession_matches > 1)::int AS ambiguous_events,
            ROUND((100.0 * COUNT(*) FILTER (WHERE possession_matches > 0) / COUNT(*))::numeric, 2)::float AS coverage_pct
        FROM matches m
        GROUP BY m.game_id
        ORDER BY coverage_pct, m.game_id
        """
    )


def load_possession_shape(db):
    return db.query_to_df(
        """
        SELECT
            COALESCE(p.entry_type, 'UNKNOWN') AS entry_type,
            COALESCE(p.end_type, 'UNKNOWN') AS end_type,
            COUNT(*)::int AS possessions,
            ROUND(AVG(p.duration_seconds)::numeric, 1)::float AS avg_duration_seconds,
            SUM(p.shot_count)::int AS shots
        FROM possessions p
        JOIN games g ON g.game_id = p.game_id
        JOIN game_shift_source_status gsss ON gsss.game_id = p.game_id AND gsss.source_status = 'available'
        WHERE (p.strength IN ('5v4', '5v3', '4v3') AND p.team_id = g.away_team_id)
           OR (p.strength IN ('4v5', '3v5', '3v4') AND p.team_id = g.home_team_id)
        GROUP BY entry_type, end_type
        ORDER BY possessions DESC
        """
    )


def write_report(summary, by_game, shape):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    by_game.to_csv(DETAIL_CSV, index=False)
    row = summary.iloc[0].to_dict()
    total = int(row["pk_team_events"] or 0)
    matched = int(row["matched_pk_team_events"] or 0)
    ambiguous = int(row["ambiguous_pk_team_events"] or 0)
    coverage_rate = matched / total if total else 0
    ambiguous_rate = ambiguous / total if total else 0
    status = coverage_status(coverage_rate, ambiguous_rate)
    report = [
        "# Shift / Possession Coverage Audit",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Status: **{status}**",
        f"Shift-covered games: `{int(row['covered_games'])}`",
        f"Games with reconstructed PP possessions: `{int(row['games_with_pp_possessions'])}`",
        f"Reconstructed PP possessions: `{int(row['pp_possessions'])}`",
        f"Reversed possession boundaries: `{int(row['reversed_possessions'])}`",
        f"PK team-events: `{total}`",
        f"Events inside a reconstructed PP possession: `{matched}`",
        f"Coverage rate: `{coverage_rate:.2%}`",
        f"Events matching multiple possessions: `{ambiguous}`",
        f"Ambiguous rate: `{ambiguous_rate:.2%}`",
        "",
        "## Lowest-Coverage Games",
        "",
        markdown_table(by_game.head(20).to_dict("records"), list(by_game.columns)),
        "",
        "## Possession Shapes",
        "",
        markdown_table(shape.head(25).to_dict("records"), list(shape.columns)),
        "",
        "## Interpretation",
        "",
        "The existing possession table contains selected offensive-zone sequences that begin with detected entries, OZ faceoffs, or turnovers and pass a meaningful-activity filter. "
        "It is not a complete puck-control timeline. `SUITABLE` requires at least 80% event coverage with at most 1% ambiguous overlap; `PARTIAL` requires at least 50% coverage with at most 3% overlap.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    return status


def main():
    from db import DatabaseConnection

    db = DatabaseConnection()
    db.connect()
    try:
        summary = load_summary(db)
        by_game = load_by_game(db)
        shape = load_possession_shape(db)
    finally:
        db.close()
    status = write_report(summary, by_game, shape)
    print(f"{status}: wrote {REPORT_PATH}")
    print(f"Wrote {DETAIL_CSV}")


if __name__ == "__main__":
    main()
