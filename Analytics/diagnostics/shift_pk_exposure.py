"""Build first-pass PK exposure features from validated shift-covered games.

This diagnostic turns event-level shift/on-ice rows into auditable scouting inputs:
covered PK event samples, shift age at non-goal shot attempts, and goal exposure
outcomes. It is intentionally descriptive and source-covered only.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORT_PATH = REPORT_DIR / "latest_shift_pk_exposure.md"
PLAYER_CSV_PATH = REPORT_DIR / "latest_shift_pk_player_exposure.csv"
BUCKET_CSV_PATH = REPORT_DIR / "latest_shift_pk_shift_age_buckets.csv"
NON_GOAL_SHOT_EVENTS = ("shot-on-goal", "missed-shot", "blocked-shot")
SHOT_ATTEMPT_EVENTS = (*NON_GOAL_SHOT_EVENTS, "goal")


def shift_age_bucket(age_seconds):
    if age_seconds is None:
        return "unknown"
    if age_seconds < 30:
        return "00-29"
    if age_seconds < 45:
        return "30-44"
    if age_seconds < 60:
        return "45-59"
    return "60+"


def markdown_table(rows, columns):
    if not rows:
        return "_No rows._"

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(format_cell(row.get(col)) for col in columns) + " |")
    return "\n".join(lines)


def format_cell(value):
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|")


def query_params(game_limit):
    return (game_limit,) if game_limit else tuple()


def game_filter_sql(game_limit):
    if not game_limit:
        return ""
    return """
      AND e.game_id IN (
          SELECT game_id
          FROM games
          ORDER BY game_id DESC
          LIMIT %s
      )
    """


def load_player_exposure(db, game_limit):
    return db.query_to_df(
        f"""
        WITH pk_events AS (
            SELECT
                eoip.player_id,
                eoip.team_id,
                p.full_name AS player,
                t.abbreviation AS team,
                e.game_id,
                e.event_id,
                e.event_type,
                e.event_team_id,
                e.period_time_seconds - gs.start_seconds AS shift_age_seconds
            FROM event_on_ice_players eoip
            JOIN events e ON e.event_id = eoip.event_id
            JOIN players p ON p.player_id = eoip.player_id
            JOIN teams t ON t.team_id = eoip.team_id
            JOIN game_shifts gs
              ON gs.game_id = e.game_id
             AND gs.player_id = eoip.player_id
             AND gs.period = e.period
             AND gs.start_seconds <= e.period_time_seconds
             AND e.period_time_seconds < gs.end_seconds
            JOIN game_shift_source_status gsss
              ON gsss.game_id = e.game_id
             AND gsss.source_status = 'available'
            WHERE eoip.is_skater
              AND (
                  (eoip.is_home AND e.home_skaters < e.away_skaters)
                  OR (NOT eoip.is_home AND e.away_skaters < e.home_skaters)
              )
              {game_filter_sql(game_limit)}
        )
        SELECT
            player_id,
            player,
            team,
            COUNT(DISTINCT game_id)::int AS games,
            COUNT(*)::int AS pk_event_samples,
            ROUND(AVG(shift_age_seconds), 1)::float AS avg_shift_age_seconds,
            ROUND(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY shift_age_seconds)::numeric, 1)::float AS p90_shift_age_seconds,
            COUNT(*) FILTER (WHERE event_type = ANY(%s) AND event_team_id <> team_id)::int AS shot_attempt_events_against,
            COUNT(*) FILTER (WHERE event_type = 'goal' AND event_team_id <> team_id)::int AS goal_events_against
        FROM pk_events
        GROUP BY player_id, player, team
        HAVING COUNT(*) >= 10
        ORDER BY shot_attempt_events_against DESC, goal_events_against DESC, pk_event_samples DESC
        LIMIT 50
        """,
        (*query_params(game_limit), list(SHOT_ATTEMPT_EVENTS)),
    )


def load_shift_age_buckets(db, game_limit):
    return db.query_to_df(
        f"""
        WITH pk_shot_attempts_against AS (
            SELECT
                e.event_id,
                e.period_time_seconds - gs.start_seconds AS shift_age_seconds
            FROM event_on_ice_players eoip
            JOIN events e ON e.event_id = eoip.event_id
            JOIN game_shifts gs
              ON gs.game_id = e.game_id
             AND gs.player_id = eoip.player_id
             AND gs.period = e.period
             AND gs.start_seconds <= e.period_time_seconds
             AND e.period_time_seconds < gs.end_seconds
            JOIN game_shift_source_status gsss
              ON gsss.game_id = e.game_id
             AND gsss.source_status = 'available'
            WHERE eoip.is_skater
              AND e.event_type = ANY(%s)
              AND e.event_team_id <> eoip.team_id
              AND (
                  (eoip.is_home AND e.home_skaters < e.away_skaters)
                  OR (NOT eoip.is_home AND e.away_skaters < e.home_skaters)
              )
              {game_filter_sql(game_limit)}
        )
        SELECT
            CASE
                WHEN shift_age_seconds < 30 THEN '00-29'
                WHEN shift_age_seconds < 45 THEN '30-44'
                WHEN shift_age_seconds < 60 THEN '45-59'
                ELSE '60+'
            END AS shift_age_bucket,
            COUNT(*)::int AS player_shot_attempt_events_against,
            ROUND(AVG(shift_age_seconds), 1)::float AS avg_shift_age_seconds
        FROM pk_shot_attempts_against
        GROUP BY shift_age_bucket
        ORDER BY MIN(shift_age_seconds)
        """,
        (list(NON_GOAL_SHOT_EVENTS), *query_params(game_limit)),
    )


def load_source_summary(db, game_limit):
    return db.query_to_df(
        f"""
        WITH selected_games AS (
            SELECT game_id
            FROM games
            ORDER BY game_id DESC
            {"LIMIT %s" if game_limit else ""}
        )
        SELECT
            COUNT(*)::int AS requested_games,
            COUNT(*) FILTER (WHERE gsss.source_status = 'available')::int AS games_with_shiftcharts,
            COUNT(*) FILTER (WHERE gsss.source_status = 'missing_empty_response')::int AS games_without_shiftcharts,
            COUNT(*) FILTER (WHERE gsss.source_status = 'request_error')::int AS games_with_source_errors,
            COUNT(*) FILTER (WHERE gsss.game_id IS NULL OR gsss.source_status = 'not_checked')::int AS games_not_checked
        FROM selected_games
        LEFT JOIN game_shift_source_status gsss USING (game_id)
        """,
        query_params(game_limit),
    )


def write_report(source_summary, player_exposure, shift_age_buckets, game_limit):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    player_exposure.to_csv(PLAYER_CSV_PATH, index=False)
    shift_age_buckets.to_csv(BUCKET_CSV_PATH, index=False)

    source = source_summary.iloc[0].to_dict() if not source_summary.empty else {}
    report = [
        "# Shift-Covered PK Exposure",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Game limit: `{game_limit or 'all shift-covered games'}`",
        f"Requested games: `{int(source.get('requested_games') or 0)}`",
        f"Games with shiftcharts: `{int(source.get('games_with_shiftcharts') or 0)}`",
        f"Games without shiftcharts: `{int(source.get('games_without_shiftcharts') or 0)}`",
        f"Games with source errors: `{int(source.get('games_with_source_errors') or 0)}`",
        f"Games not checked: `{int(source.get('games_not_checked') or 0)}`",
        "",
        "## Shift-Age Buckets For PK Shot Attempts Against",
        "",
        markdown_table(
            shift_age_buckets.to_dict("records"),
            ["shift_age_bucket", "player_shot_attempt_events_against", "avg_shift_age_seconds"],
        ),
        "",
        "## Player PK Exposure Sample",
        "",
        markdown_table(
            player_exposure.head(25).to_dict("records"),
            [
                "player",
                "team",
                "games",
                "pk_event_samples",
                "avg_shift_age_seconds",
                "p90_shift_age_seconds",
                "shot_attempt_events_against",
                "goal_events_against",
            ],
        ),
        "",
        "## Interpretation",
        "",
        "This is a source-covered descriptive exposure report, not a player-impact model. "
        "Rows only include games where NHL shiftcharts returned source rows and only count player-event exposures where a skater was shift-derived as on ice while his team was shorthanded. Shot-attempt and goal counts are therefore exposure events, not unique team shot totals.",
        "",
        "The shift-age bucket table intentionally excludes goals. Several NHL shiftchart rows start or stop at scoring timestamps, so goal-event shift age can be reset to zero and should not be used as a fatigue proxy until that edge case is audited separately. Player rows still keep goal_events_against as an outcome exposure column.",
        "",
        "Use these outputs to design TOI/fatigue features; keep source coverage counts attached to any downstream model or UI claim.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build shift-covered PK exposure diagnostics.")
    parser.add_argument("--game-limit", type=int, default=50, help="Latest N NHL-ingested games to summarize.")
    args = parser.parse_args()

    from db import DatabaseConnection

    db = DatabaseConnection()
    db.connect()
    try:
        source_summary = load_source_summary(db, args.game_limit)
        player_exposure = load_player_exposure(db, args.game_limit)
        shift_age_buckets = load_shift_age_buckets(db, args.game_limit)
    finally:
        db.close()

    write_report(source_summary, player_exposure, shift_age_buckets, args.game_limit)
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {PLAYER_CSV_PATH}")
    print(f"Wrote {BUCKET_CSV_PATH}")


if __name__ == "__main__":
    main()
