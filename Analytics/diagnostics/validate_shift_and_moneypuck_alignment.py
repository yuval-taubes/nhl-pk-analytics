"""Validate shift-derived on-ice data and MoneyPuck shot alignment.

This diagnostic is intentionally conservative. It does not bless new player-impact
models; it produces audit reports that explain whether the new shift/on-ice source
and MoneyPuck shot geometry are aligned well enough to build on.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError:
    pd = None

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
SHIFT_REPORT_PATH = REPORT_DIR / "latest_shift_on_ice_validation.md"
MP_REPORT_PATH = REPORT_DIR / "latest_moneypuck_shot_alignment.md"
SHOT_EVENTS = ("shot-on-goal", "goal", "missed-shot", "blocked-shot")
MODEL_SAFE_EVENT_TYPES = ("shot-on-goal", "goal", "missed-shot", "blocked-shot", "faceoff", "hit", "giveaway", "takeaway")


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
    if pd is not None and pd.isna(value):
        return ""
    if isinstance(value, float):
        if math.isfinite(value):
            return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|")


def pct(numerator, denominator):
    return float(numerator) / float(denominator) if denominator else 0.0


def shift_validation_status(events, manpower_rows, model_safe_mismatch_rate, threshold=0.02):
    """Return PASS only when coverage is complete and model-safe mismatches are low."""
    return "PASS" if manpower_rows == events and model_safe_mismatch_rate <= threshold else "REVIEW"

def validate_shift_on_ice(db, game_limit: int | None):
    game_filter = """
        AND e.game_id IN (
            SELECT DISTINCT e2.game_id
            FROM event_manpower em2
            JOIN events e2 ON e2.event_id = em2.event_id
        )
        """
    params: list[object] = []
    coverage_query = """
        WITH selected_games AS (
            SELECT game_id
            FROM game_shift_source_status
        )
        SELECT
            COUNT(*)::int AS requested_games,
            COUNT(*) FILTER (WHERE source_status = 'available')::int AS games_with_shifts,
            COUNT(*) FILTER (WHERE source_status = 'missing_empty_response')::int AS games_without_shifts,
            COUNT(*) FILTER (WHERE source_status = 'request_error')::int AS games_with_source_errors,
            COUNT(*) FILTER (WHERE source_status = 'not_checked')::int AS games_not_checked
        FROM game_shift_source_status
        """
    coverage_params: tuple[object, ...] = tuple()

    missing_source_query = """
        SELECT game_id
        FROM game_shift_source_status
        WHERE source_status <> 'available'
        ORDER BY game_id DESC
        LIMIT 30
        """
    missing_source_params: tuple[object, ...] = tuple()

    if game_limit:
        game_filter = """
        AND e.game_id IN (
            SELECT sg.game_id
            FROM (
                SELECT game_id
                FROM games
                ORDER BY game_id DESC
                LIMIT %s
            ) sg
            WHERE EXISTS (
                SELECT 1 FROM game_shift_source_status gsss
                WHERE gsss.game_id = sg.game_id AND gsss.source_status = 'available'
            )
        )
        """
        params.append(game_limit)
        coverage_query = """
        WITH selected_games AS (
            SELECT game_id
            FROM games
            ORDER BY game_id DESC
            LIMIT %s
        )
        SELECT
            COUNT(*)::int AS requested_games,
            COUNT(*) FILTER (WHERE gsss.source_status = 'available')::int AS games_with_shifts,
            COUNT(*) FILTER (WHERE gsss.source_status = 'missing_empty_response')::int AS games_without_shifts,
            COUNT(*) FILTER (WHERE gsss.source_status = 'request_error')::int AS games_with_source_errors,
            COUNT(*) FILTER (WHERE gsss.game_id IS NULL OR gsss.source_status = 'not_checked')::int AS games_not_checked
        FROM selected_games
        LEFT JOIN game_shift_source_status gsss USING (game_id)
        """
        coverage_params = (game_limit,)
        missing_source_query = """
        WITH selected_games AS (
            SELECT game_id
            FROM games
            ORDER BY game_id DESC
            LIMIT %s
        )
        SELECT game_id
        FROM selected_games sg
        LEFT JOIN game_shift_source_status gsss USING (game_id)
        WHERE gsss.game_id IS NULL OR gsss.source_status <> 'available'
        ORDER BY game_id DESC
        LIMIT 30
        """
        missing_source_params = (game_limit,)

    source_coverage = db.query_to_df(coverage_query, coverage_params).iloc[0]
    missing_source_games = db.query_to_df(missing_source_query, missing_source_params)

    summary = db.query_to_df(
        f"""
        WITH checked_events AS (
            SELECT e.*
            FROM events e
            WHERE TRUE
            {game_filter}
        )
        SELECT
            COUNT(DISTINCT e.game_id)::int AS games,
            COUNT(*)::int AS events,
            COUNT(*) FILTER (WHERE em.event_id IS NOT NULL)::int AS manpower_rows,
            COUNT(*) FILTER (WHERE em.matches_situation_code)::int AS matching_events,
            COUNT(*) FILTER (WHERE em.event_id IS NOT NULL AND NOT em.matches_situation_code)::int AS mismatching_events,
            COUNT(*) FILTER (WHERE e.event_type = ANY(%s))::int AS shot_events,
            COUNT(*) FILTER (WHERE e.event_type = ANY(%s))::int AS model_safe_events,
            COUNT(*) FILTER (WHERE e.event_type = ANY(%s) AND em.event_id IS NOT NULL)::int AS model_safe_manpower_rows,
            COUNT(*) FILTER (WHERE e.event_type = ANY(%s) AND em.matches_situation_code)::int AS model_safe_matches,
            COUNT(*) FILTER (WHERE e.event_type = ANY(%s) AND em.event_id IS NOT NULL AND NOT em.matches_situation_code)::int AS model_safe_mismatches,
            (SELECT COUNT(*)::int FROM game_shifts gs WHERE gs.game_id IN (SELECT DISTINCT game_id FROM checked_events)) AS shift_rows,
            (SELECT COUNT(*)::int FROM event_on_ice_players eoip JOIN checked_events ce ON ce.event_id = eoip.event_id) AS on_ice_rows
        FROM checked_events e
        LEFT JOIN event_manpower em ON em.event_id = e.event_id
        """,
        (*params, list(SHOT_EVENTS), list(MODEL_SAFE_EVENT_TYPES), list(MODEL_SAFE_EVENT_TYPES), list(MODEL_SAFE_EVENT_TYPES), list(MODEL_SAFE_EVENT_TYPES)),
    ).iloc[0]

    mismatch_by_type = db.query_to_df(
        f"""
        SELECT
            e.event_type,
            COUNT(*)::int AS mismatches,
            COUNT(*) FILTER (WHERE e.period_time_seconds IN (0, 1200))::int AS period_boundary,
            COUNT(*) FILTER (WHERE ABS(e.home_skaters - em.home_skaters_shift) + ABS(e.away_skaters - em.away_skaters_shift) = 1)::int AS one_skater_off,
            COUNT(*) FILTER (WHERE em.home_goalie_pulled OR em.away_goalie_pulled)::int AS goalie_pulled,
            COUNT(*) FILTER (WHERE e.event_type = ANY(%s))::int AS model_safe_mismatches
        FROM event_manpower em
        JOIN events e ON e.event_id = em.event_id
        WHERE NOT em.matches_situation_code
        {game_filter}
        GROUP BY e.event_type
        ORDER BY mismatches DESC, e.event_type
        """,
        (list(MODEL_SAFE_EVENT_TYPES), *params),
    )

    examples = db.query_to_df(
        f"""
        SELECT
            e.game_id,
            e.event_idx,
            e.period,
            e.period_time_seconds,
            e.event_type,
            e.strength AS situation_strength,
            e.home_skaters AS pbp_home,
            e.away_skaters AS pbp_away,
            em.home_skaters_shift AS shift_home,
            em.away_skaters_shift AS shift_away,
            em.strength_code_shift AS shift_code,
            em.home_goalie_id,
            em.away_goalie_id,
            em.home_goalie_pulled,
            em.away_goalie_pulled
        FROM event_manpower em
        JOIN events e ON e.event_id = em.event_id
        WHERE NOT em.matches_situation_code
        {game_filter}
        ORDER BY e.game_id DESC, e.event_idx
        LIMIT 30
        """,
        tuple(params),
    )

    by_game = db.query_to_df(
        f"""
        SELECT
            e.game_id,
            COUNT(*)::int AS events,
            COUNT(*) FILTER (WHERE em.matches_situation_code)::int AS matches,
            COUNT(*) FILTER (WHERE NOT em.matches_situation_code)::int AS mismatches,
            ROUND(100.0 * COUNT(*) FILTER (WHERE em.matches_situation_code) / NULLIF(COUNT(*), 0), 2) AS match_pct
        FROM event_manpower em
        JOIN events e ON e.event_id = em.event_id
        WHERE TRUE
        {game_filter}
        GROUP BY e.game_id
        ORDER BY mismatches DESC, e.game_id DESC
        LIMIT 20
        """,
        tuple(params),
    )

    events = int(summary["events"] or 0)
    manpower_rows = int(summary["manpower_rows"] or 0)
    matching_events = int(summary["matching_events"] or 0)
    mismatch_rate = 1.0 - pct(matching_events, manpower_rows)
    model_safe_events = int(summary["model_safe_events"] or 0)
    model_safe_manpower_rows = int(summary["model_safe_manpower_rows"] or 0)
    model_safe_matches = int(summary["model_safe_matches"] or 0)
    model_safe_mismatches = int(summary["model_safe_mismatches"] or 0)
    model_safe_mismatch_rate = 1.0 - pct(model_safe_matches, model_safe_manpower_rows)
    covered_status = shift_validation_status(events, manpower_rows, model_safe_mismatch_rate)
    games_without_shifts = int(source_coverage["games_without_shifts"] or 0)
    games_with_source_errors = int(source_coverage["games_with_source_errors"] or 0)
    games_not_checked = int(source_coverage["games_not_checked"] or 0)
    status = "PASS" if covered_status == "PASS" and games_without_shifts == 0 and games_with_source_errors == 0 and games_not_checked == 0 else "REVIEW"

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = [
        "# Shift / On-Ice Validation",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Status: **{status}**",
        "",
        f"Requested games: `{int(source_coverage['requested_games'] or 0)}`",
        f"Games with shiftcharts: `{int(source_coverage['games_with_shifts'] or 0)}`",
        f"Games without shiftcharts: `{games_without_shifts}`",
        f"Games with source errors: `{games_with_source_errors}`",
        f"Games not checked: `{games_not_checked}`",
        f"Covered-games status: **{covered_status}**",
        f"Games checked: `{int(summary['games'] or 0)}`",
        f"Events checked: `{events}`",
        f"Raw shift rows: `{int(summary['shift_rows'] or 0)}`",
        f"Event on-ice rows: `{int(summary['on_ice_rows'] or 0)}`",
        f"Manpower rows: `{manpower_rows}`",
        f"Situation-code matches: `{matching_events}`",
        f"All-event mismatch rate: `{mismatch_rate:.2%}`",
        f"Model-safe events: `{model_safe_events}`",
        f"Model-safe manpower rows: `{model_safe_manpower_rows}`",
        f"Model-safe mismatches: `{model_safe_mismatches}`",
        f"Model-safe mismatch rate: `{model_safe_mismatch_rate:.2%}`",
        "",
        "## Missing Shiftchart Source Games",
        "",
        markdown_table(missing_source_games.to_dict("records"), ["game_id"]),
        "",
        "## Mismatches By Event Type",
        "",
        markdown_table(
            mismatch_by_type.to_dict("records"),
            ["event_type", "mismatches", "period_boundary", "one_skater_off", "goalie_pulled", "model_safe_mismatches"],
        ),
        "",
        "## Highest-Mismatch Games",
        "",
        markdown_table(by_game.to_dict("records"), ["game_id", "events", "matches", "mismatches", "match_pct"]),
        "",
        "## Example Mismatches",
        "",
        markdown_table(
            examples.to_dict("records"),
            [
                "game_id",
                "event_idx",
                "period",
                "period_time_seconds",
                "event_type",
                "situation_strength",
                "pbp_home",
                "pbp_away",
                "shift_home",
                "shift_away",
                "shift_code",
                "home_goalie_pulled",
                "away_goalie_pulled",
            ],
        ),
        "",
        "## Interpretation",
        "",
        "A top-level `PASS` requires both complete shiftchart source coverage for the requested sample and low covered-game manpower mismatch rates. "
        "A `Covered-games status` of `PASS` means shift-derived manpower agrees with NHL play-by-play skater counts for games where shiftcharts exist. "
        "It does not validate player positioning or tactical shape. Missing shiftchart source games should be excluded from shift-derived models until source coverage is understood.",
        "",
    ]
    SHIFT_REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    return {
        "status": status,
        "path": str(SHIFT_REPORT_PATH),
        "mismatch_rate": mismatch_rate,
        "model_safe_mismatch_rate": model_safe_mismatch_rate,
        "games_without_shifts": games_without_shifts,
    }

def validate_moneypuck_alignment(db, game_limit: int | None):
    limit_clause = "WHERE TRUE"
    params: list[object] = []
    if game_limit:
        limit_clause = """
        WHERE e.game_id IN (
            SELECT game_id
            FROM games
            ORDER BY game_id DESC
            LIMIT %s
        )
        """
        params.append(game_limit)

    base_cte = f"""
        WITH nhl_shots AS (
            SELECT
                e.game_id AS nhl_game_id,
                (g.season::int / 10000)::int AS mp_season,
                mod(e.game_id, 1000000)::int AS mp_game_id,
                e.event_id,
                e.event_idx,
                e.period,
                e.period_time_seconds,
                (e.period_time_seconds + (1200 * (e.period - 1))) AS game_time_seconds,
                e.event_type,
                t.abbreviation AS shooting_team_code,
                s.x_norm::numeric AS nhl_x_norm,
                s.y_norm::numeric AS nhl_y_norm,
                (s.x_norm::numeric - 100) AS nhl_x_centered,
                (s.y_norm::numeric - 42.5) AS nhl_y_centered,
                s.is_goal
            FROM shots s
            JOIN events e ON e.event_id = s.event_id
            JOIN games g ON g.game_id = e.game_id
            LEFT JOIN teams t ON t.team_id = e.event_team_id
            {limit_clause}
              AND e.event_type <> 'blocked-shot'
        ),
        candidates AS (
            SELECT
                n.*,
                mp.shot_id,
                mp.event AS mp_event,
                mp.time_seconds AS mp_time_seconds,
                mp.shooting_team_code AS mp_team,
                mp.x_cord,
                mp.y_cord,
                mp.x_cord_adjusted,
                mp.y_cord_adjusted,
                mp.arena_adjusted_x_cord,
                mp.arena_adjusted_y_cord,
                mp.goal AS mp_goal,
                ABS(mp.time_seconds - n.game_time_seconds) AS time_delta,
                ROW_NUMBER() OVER (
                    PARTITION BY n.event_id
                    ORDER BY ABS(mp.time_seconds - n.game_time_seconds), mp.shot_id
                ) AS candidate_rank
            FROM nhl_shots n
            JOIN mp_shots mp
              ON mp.season = n.mp_season
             AND mp.game_id = n.mp_game_id
             AND mp.period = n.period
             AND mp.shooting_team_code = n.shooting_team_code
             AND ABS(mp.time_seconds - n.game_time_seconds) <= 2
        ),
        matched AS (
            SELECT *
            FROM candidates
            WHERE candidate_rank = 1
        )
    """

    summary = db.query_to_df(
        base_cte
        + """
        SELECT
            (SELECT COUNT(*) FROM nhl_shots)::int AS nhl_shots,
            (SELECT COUNT(*) FROM matched)::int AS matched_shots,
            COUNT(*) FILTER (WHERE is_goal = mp_goal)::int AS goal_matches,
            COUNT(*) FILTER (WHERE event_type = 'goal' AND mp_goal)::int AS goal_event_matches
        FROM matched
        """,
        tuple(params),
    ).iloc[0]

    coordinate_summary = db.query_to_df(
        base_cte
        + """
        SELECT
            COUNT(*)::int AS matched_shots,
            ROUND(AVG(ABS(nhl_x_centered - x_cord)), 2) AS avg_abs_x_raw,
            ROUND(AVG(ABS(nhl_y_centered - y_cord)), 2) AS avg_abs_y_raw,
            ROUND(AVG(ABS(nhl_x_centered - x_cord_adjusted)), 2) AS avg_abs_x_adjusted,
            ROUND(AVG(ABS(nhl_y_centered - y_cord_adjusted)), 2) AS avg_abs_y_adjusted,
            ROUND(AVG(ABS(nhl_x_centered - arena_adjusted_x_cord)), 2) AS avg_abs_x_arena_adjusted,
            ROUND(AVG(ABS(nhl_y_centered - arena_adjusted_y_cord)), 2) AS avg_abs_y_arena_adjusted,
            ROUND(AVG(ABS(nhl_x_centered - (-1 * x_cord_adjusted))), 2) AS avg_abs_x_mirrored_adjusted,
            ROUND(AVG(ABS(nhl_y_centered - (-1 * y_cord_adjusted))), 2) AS avg_abs_y_flipped_adjusted,
            ROUND(AVG(ABS(ABS(nhl_x_centered) - ABS(x_cord_adjusted))), 2) AS avg_abs_x_magnitude_adjusted,
            ROUND(AVG(ABS(ABS(nhl_y_centered) - ABS(y_cord_adjusted))), 2) AS avg_abs_y_magnitude_adjusted,
            ROUND(AVG(ABS(ABS(nhl_x_centered) - ABS(arena_adjusted_x_cord))), 2) AS avg_abs_x_magnitude_arena,
            ROUND(AVG(ABS(ABS(nhl_y_centered) - ABS(arena_adjusted_y_cord))), 2) AS avg_abs_y_magnitude_arena
        FROM matched
        """,
        tuple(params),
    )

    time_summary = db.query_to_df(
        base_cte
        + """
        SELECT
            time_delta,
            COUNT(*)::int AS shots
        FROM matched
        GROUP BY time_delta
        ORDER BY time_delta
        """,
        tuple(params),
    )

    examples = db.query_to_df(
        base_cte
        + """
        SELECT
            nhl_game_id,
            event_idx,
            period,
            period_time_seconds,
            event_type,
            shooting_team_code,
            shot_id AS mp_shot_id,
            mp_time_seconds,
            nhl_x_norm,
            nhl_y_norm,
            nhl_x_centered,
            nhl_y_centered,
            x_cord_adjusted AS mp_x_adjusted,
            y_cord_adjusted AS mp_y_adjusted,
            arena_adjusted_x_cord AS mp_x_arena_adjusted,
            arena_adjusted_y_cord AS mp_y_arena_adjusted,
            ABS(nhl_x_centered - x_cord_adjusted) AS adjusted_x_delta,
            ABS(nhl_y_centered - y_cord_adjusted) AS adjusted_y_delta
        FROM matched
        ORDER BY adjusted_x_delta DESC NULLS LAST, adjusted_y_delta DESC NULLS LAST
        LIMIT 25
        """,
        tuple(params),
    )

    nhl_shots = int(summary["nhl_shots"] or 0)
    matched_shots = int(summary["matched_shots"] or 0)
    match_rate = pct(matched_shots, nhl_shots)
    status = "PASS" if match_rate >= 0.95 else "REVIEW"

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = [
        "# MoneyPuck Shot Alignment",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Status: **{status}**",
        "",
        "Join convention: NHL full game IDs are mapped to MoneyPuck by `season = left 4 digits of NHL season` and `game_id = nhl_game_id % 1000000`.",
        "MoneyPuck excludes blocked shots, so only NHL shot-on-goal, missed-shot, and goal rows are matched. Shots are matched by game, period, shooting team, and game-elapsed time within two seconds.",
        "",
        f"NHL unblocked shot rows checked: `{nhl_shots}`",
        f"Matched MoneyPuck shots: `{matched_shots}`",
        f"Match rate: `{match_rate:.2%}`",
        f"Goal flag matches: `{int(summary['goal_matches'] or 0)}`",
        "",
        "## Coordinate Candidate Summary",
        "",
        markdown_table(coordinate_summary.to_dict("records"), list(coordinate_summary.columns)),
        "",
        "## Time Delta Summary",
        "",
        markdown_table(time_summary.to_dict("records"), ["time_delta", "shots"]),
        "",
        "## Largest Adjusted-Coordinate Differences",
        "",
        markdown_table(examples.to_dict("records"), list(examples.columns)),
        "",
        "## Interpretation",
        "",
        "This report is a convention finder as much as a validator. Direct signed X deltas can be large when the two sources encode attack direction differently. The magnitude columns test whether the shot geometry itself agrees independent of rink side. "
        "If all coordinate deltas are large, local coordinate normalization should be audited before using shot location models as trusted evidence.",
        "",
    ]
    MP_REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    return {"status": status, "path": str(MP_REPORT_PATH), "match_rate": match_rate}


def main():
    parser = argparse.ArgumentParser(description="Validate shift/on-ice and MoneyPuck shot alignment.")
    parser.add_argument("--game-limit", type=int, default=None, help="Limit checks to the latest N NHL-ingested games.")
    args = parser.parse_args()

    from db import DatabaseConnection

    db = DatabaseConnection()
    db.connect()
    try:
        shift_result = validate_shift_on_ice(db, args.game_limit)
        mp_result = validate_moneypuck_alignment(db, args.game_limit)
    finally:
        db.close()

    print(f"{shift_result['status']}: wrote {shift_result['path']}")
    print(f"{mp_result['status']}: wrote {mp_result['path']}")
    if shift_result["status"] != "PASS" or mp_result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
