"""Describe PK pressure by shift-age and rest buckets on source-covered games."""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from diagnostics.shift_pk_exposure import format_cell, markdown_table


REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORT_PATH = REPORT_DIR / "latest_shift_pk_fatigue_pressure.md"
SHIFT_AGE_CSV = REPORT_DIR / "latest_shift_pk_fatigue_by_shift_age.csv"
REST_CSV = REPORT_DIR / "latest_shift_pk_fatigue_by_rest.csv"
MIN_EVENTS_PER_BUCKET = 100


def trust_label(events, min_events=MIN_EVENTS_PER_BUCKET):
    return "descriptive" if events >= min_events else "small_sample"


def wilson_interval(successes, total, z=1.96):
    if total <= 0:
        return (None, None)
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return (100 * (center - margin), 100 * (center + margin))


def load_bucket_summary(db, bucket_expression, order_expression):
    return db.query_to_df(
        f"""
        WITH team_events AS (
            SELECT
                f.game_id,
                f.event_id,
                f.team_id,
                f.event_type,
                f.event_team_id,
                f.period,
                f.period_time_seconds,
                MAX(f.shift_age_seconds)::float AS oldest_shift_age_seconds,
                MIN(f.rest_before_shift_seconds)::float AS shortest_rest_seconds
            FROM pk_shift_player_event_features f
            WHERE f.is_penalty_killing
              AND f.event_type <> 'goal'
            GROUP BY f.game_id, f.event_id, f.team_id, f.event_type,
                     f.event_team_id, f.period, f.period_time_seconds
        ), mp_candidates AS (
            SELECT
                te.event_id,
                te.team_id,
                mp.x_goal::float AS x_goal,
                ROW_NUMBER() OVER (
                    PARTITION BY te.event_id, te.team_id
                    ORDER BY ABS(mp.time_seconds - (te.period_time_seconds + 1200 * (te.period - 1))), mp.shot_id
                ) AS candidate_rank
            FROM team_events te
            JOIN games g ON g.game_id = te.game_id
            JOIN teams attacking_team ON attacking_team.team_id = te.event_team_id
            JOIN mp_shots mp
              ON mp.season = (g.season::int / 10000)::int
             AND mp.game_id = mod(te.game_id, 1000000)::int
             AND mp.period = te.period
             AND mp.shooting_team_code = attacking_team.abbreviation
             AND ABS(mp.time_seconds - (te.period_time_seconds + 1200 * (te.period - 1))) <= 2
            WHERE te.event_type IN ('shot-on-goal', 'missed-shot')
              AND te.event_team_id <> te.team_id
        ), mp_matched AS (
            SELECT event_id, team_id, x_goal
            FROM mp_candidates
            WHERE candidate_rank = 1
        ), event_outcomes AS (
            SELECT
                te.*,
                CASE WHEN te.event_type IN ('shot-on-goal', 'missed-shot', 'blocked-shot') THEN 1 ELSE 0 END AS shot_attempt_against,
                mp.x_goal::float AS xg_against
            FROM team_events te
            LEFT JOIN mp_matched mp ON mp.event_id = te.event_id AND mp.team_id = te.team_id
        )
        SELECT
            {bucket_expression} AS bucket,
            COUNT(*)::int AS pk_team_events,
            SUM(shot_attempt_against)::int AS shot_attempts_against,
            COUNT(*) FILTER (WHERE event_type IN ('shot-on-goal', 'missed-shot'))::int AS unblocked_shot_attempts,
            ROUND((100.0 * AVG(shot_attempt_against))::numeric, 2)::float AS shot_attempts_per_100_events,
            COUNT(xg_against)::int AS shots_with_xg,
            ROUND((100.0 * COUNT(xg_against) / NULLIF(COUNT(*) FILTER (WHERE event_type IN ('shot-on-goal', 'missed-shot')), 0))::numeric, 2)::float AS xg_match_rate,
            ROUND(SUM(xg_against)::numeric, 3)::float AS xg_against,
            ROUND((100.0 * SUM(xg_against) / COUNT(*))::numeric, 3)::float AS xg_per_100_events
        FROM event_outcomes
        GROUP BY bucket
        ORDER BY {order_expression}
        """
    )


def add_trust(rows):
    rows = rows.copy()
    rows["trust"] = rows["pk_team_events"].map(trust_label)
    intervals = [wilson_interval(int(row.shot_attempts_against), int(row.pk_team_events)) for row in rows.itertuples()]
    rows["pressure_ci_low"] = [round(interval[0], 2) for interval in intervals]
    rows["pressure_ci_high"] = [round(interval[1], 2) for interval in intervals]
    rows["xg_trust"] = rows["xg_match_rate"].map(lambda rate: "validated" if rate is not None and rate >= 95 else "incomplete")
    return rows


def write_report(shift_age, rest):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    shift_age.to_csv(SHIFT_AGE_CSV, index=False)
    rest.to_csv(REST_CSV, index=False)
    columns = ["bucket", "pk_team_events", "shot_attempts_against", "shot_attempts_per_100_events", "pressure_ci_low", "pressure_ci_high", "unblocked_shot_attempts", "shots_with_xg", "xg_match_rate", "xg_against", "xg_per_100_events", "xg_trust", "trust"]
    report = [
        "# Source-Covered PK Fatigue Pressure",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Oldest Active PK Shift",
        "",
        markdown_table(shift_age.to_dict("records"), columns),
        "",
        "## Shortest Rest Among Active PK Skaters",
        "",
        markdown_table(rest.to_dict("records"), columns),
        "",
        "## Interpretation",
        "",
        "The unit is one source-covered PK team-event. Shift age uses the oldest active PK skater; rest uses the shortest game-clock gap among active PK skaters. Intermission duration is excluded, so rest is not wall-clock recovery. "
        "Rates describe non-goal shot-attempt pressure per 100 recorded play-by-play events. They are not possession-adjusted, opponent-adjusted, score-adjusted, or causal.",
        "",
        "Goal events are excluded because NHL shift segments can start or stop at the scoring timestamp and reset apparent shift age. "
        "Pressure intervals are 95% Wilson intervals. Rows below 100 PK team-events are labeled `small_sample`. "
        "xG is joined from MoneyPuck for unblocked shots using the separately validated game, period, shooting-team, and elapsed-time-within-two-seconds contract. Blocked attempts remain in pressure counts but do not receive fabricated xG.",
        "",
        "Bucket-level xG is labeled `incomplete` below a 95% unblocked-shot match rate. Incomplete xG can be used as directional audit evidence only, not as a trusted fatigue estimate.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build source-covered PK fatigue pressure diagnostics.")
    parser.parse_args()
    from db import DatabaseConnection

    db = DatabaseConnection()
    db.connect()
    try:
        shift_age = load_bucket_summary(
            db,
            "CASE WHEN oldest_shift_age_seconds < 30 THEN '00-29' WHEN oldest_shift_age_seconds < 45 THEN '30-44' WHEN oldest_shift_age_seconds < 60 THEN '45-59' ELSE '60+' END",
            "MIN(oldest_shift_age_seconds)",
        )
        rest = load_bucket_summary(
            db,
            "CASE WHEN shortest_rest_seconds < 15 THEN '00-14' WHEN shortest_rest_seconds < 30 THEN '15-29' WHEN shortest_rest_seconds < 45 THEN '30-44' ELSE '45+' END",
            "MIN(shortest_rest_seconds)",
        )
    finally:
        db.close()

    write_report(add_trust(shift_age), add_trust(rest))
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {SHIFT_AGE_CSV}")
    print(f"Wrote {REST_CSV}")


if __name__ == "__main__":
    main()
