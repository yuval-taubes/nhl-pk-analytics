"""
Sample possessions and write full event chains for manual review.

This validator is intentionally conservative about true segmentation failures.
Team-relative zone labels can flip on blocked shots or ownership changes, so
coordinate movement is used before counting a zone change as an issue.
"""

import logging
import os
from datetime import datetime

import pandas as pd

from db import DatabaseConnection

logger = logging.getLogger(__name__)


def _safe_text(value, fallback='?'):
    if pd.isna(value):
        return fallback
    text = str(value)
    return text if text else fallback


def _safe_int(value, fallback=0):
    return fallback if pd.isna(value) else int(value)


def _large_coordinate_jump(prev_x, curr_x, threshold=80):
    if pd.isna(prev_x) or pd.isna(curr_x):
        return False
    return abs(float(curr_x) - float(prev_x)) >= threshold


def validate_possessions(db, sample_size=50, output_file=None):
    """
    Sample possessions across entry types and write event chains for review.

    Returns:
        (issues_dict, issue_rate)
    """
    if output_file is None:
        output_file = f"runs/possession_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    controlled_limit = max(0, int(sample_size * 0.40))
    dump_in_limit = max(0, int(sample_size * 0.30))
    turnover_limit = max(0, int(sample_size * 0.20))
    faceoff_limit = max(0, sample_size - controlled_limit - dump_in_limit - turnover_limit)

    query = """
    (SELECT possession_id, game_id, team_id, start_event_id, end_event_id,
            entry_type, end_type, strength, start_zone, duration_seconds,
            'CONTROLLED' as stratum
     FROM possessions
     WHERE strength IN ('4v5', '3v5') AND entry_type = 'CONTROLLED'
     ORDER BY RANDOM() LIMIT %s)
    UNION ALL
    (SELECT possession_id, game_id, team_id, start_event_id, end_event_id,
            entry_type, end_type, strength, start_zone, duration_seconds,
            'DUMP_IN' as stratum
     FROM possessions
     WHERE strength IN ('4v5', '3v5') AND entry_type = 'DUMP_IN'
     ORDER BY RANDOM() LIMIT %s)
    UNION ALL
    (SELECT possession_id, game_id, team_id, start_event_id, end_event_id,
            entry_type, end_type, strength, start_zone, duration_seconds,
            'TURNOVER' as stratum
     FROM possessions
     WHERE strength IN ('4v5', '3v5') AND entry_type = 'TURNOVER'
     ORDER BY RANDOM() LIMIT %s)
    UNION ALL
    (SELECT possession_id, game_id, team_id, start_event_id, end_event_id,
            entry_type, end_type, strength, start_zone, duration_seconds,
            'FACEOFF' as stratum
     FROM possessions
     WHERE strength IN ('4v5', '3v5') AND entry_type = 'FACEOFF_START'
     ORDER BY RANDOM() LIMIT %s)
    """

    possessions = db.query_to_df(
        query,
        (controlled_limit, dump_in_limit, turnover_limit, faceoff_limit)
    )

    logger.info(f"Sampled {len(possessions)} possessions for validation")
    logger.info(f"Writing to {output_file}")

    issues = {
        'split_entries': [],
        'fake_clears': [],
        'zone_confusion': [],
        'single_event': [],
        'very_short': [],
        'total_checked': 0
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("POSSESSION VALIDATION REPORT\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Sample size: {len(possessions)}\n")
        f.write("=" * 80 + "\n\n")

        for idx, (_, possession) in enumerate(possessions.iterrows()):
            pid = possession['possession_id']

            f.write(f"\n{'=' * 80}\n")
            f.write(f"POSSESSION #{idx + 1} (ID: {pid})\n")
            f.write(f"Stratum: {possession['stratum']}\n")
            f.write(f"Entry: {possession['entry_type']} -> End: {possession['end_type']}\n")
            f.write(f"Strength: {possession['strength']} | Zone: {possession['start_zone']}\n")
            f.write(f"Duration: {possession['duration_seconds']}s\n")
            f.write(f"{'=' * 80}\n")
            f.write(f"{'Event':30s} | {'Zone':5s} | {'X':>5s} | Time | Team | Flags\n")
            f.write(f"{'-' * 92}\n")

            events = db.query_to_df("""
                SELECT e.event_type, e.zone, e.period_time_seconds, e.period,
                       et.abbreviation as team_abbrev, e.event_team_id,
                       e.x_norm, e.y_norm
                FROM events e
                LEFT JOIN teams et ON e.event_team_id = et.team_id
                WHERE e.game_id = %s
                  AND e.event_idx BETWEEN (
                      SELECT event_idx FROM events WHERE event_id = %s
                  ) AND (
                      SELECT event_idx FROM events WHERE event_id = %s
                  )
                ORDER BY e.event_idx
            """, (possession['game_id'], possession['start_event_id'], possession['end_event_id']))

            prev_zone = None
            prev_team = None
            prev_x = None
            last_event_position = len(events) - 1

            for event_position, (_, event) in enumerate(events.iterrows()):
                flags = []

                event_type = _safe_text(event['event_type'], 'unknown')
                zone = _safe_text(event['zone'])
                team_abbrev = _safe_text(event['team_abbrev'])
                period = _safe_int(event['period'])
                period_time = _safe_int(event['period_time_seconds'])
                event_team = None if pd.isna(event['event_team_id']) else event['event_team_id']
                x_norm = event['x_norm']

                if prev_zone and zone != '?' and prev_zone != zone:
                    if _large_coordinate_jump(prev_x, x_norm):
                        flags.append("LONG_ZONE_JUMP")
                        issues['zone_confusion'].append(pid)
                    else:
                        flags.append("ZONE_LABEL_FLIP")

                if prev_team is not None and event_team is not None and prev_team != event_team:
                    flags.append("TEAM_CHANGE")

                    is_final_turnover_event = (
                        event_position == last_event_position and
                        possession['end_type'] == 'TURNOVER'
                    )

                    if is_final_turnover_event:
                        flags.append("EXPECTED_TURNOVER_END")
                    elif event_type not in ('takeaway', 'giveaway', 'blocked-shot', 'faceoff'):
                        issues['fake_clears'].append(pid)

                flag_str = ", ".join(flags) if flags else ""
                x_display = "?" if pd.isna(x_norm) else f"{int(x_norm):d}"

                f.write(
                    f"{event_type:30s} | {zone:5s} | {x_display:>5s} | "
                    f"P{period} {period_time:5d}s | {team_abbrev:4s} | {flag_str}\n"
                )

                prev_zone = None if zone == '?' else zone
                prev_team = event_team
                prev_x = x_norm

            if len(events) <= 1:
                f.write("\nWARNING: SINGLE-EVENT POSSESSION - likely split entry\n")
                issues['single_event'].append(pid)
                issues['split_entries'].append(pid)

            if possession['duration_seconds'] and possession['duration_seconds'] < 1:
                f.write(f"\nWARNING: Very short duration ({possession['duration_seconds']}s)\n")
                issues['very_short'].append(pid)

            issues['total_checked'] += 1

            if (idx + 1) % 10 == 0:
                logger.info(f"Processed {idx + 1}/{len(possessions)} possessions...")

        f.write(f"\n\n{'=' * 80}\nSUMMARY\n{'=' * 80}\n")
        f.write(f"Total checked: {issues['total_checked']}\n")

        split_entries = sorted(set(issues['split_entries']))
        fake_clears = sorted(set(issues['fake_clears']))
        zone_confusion = sorted(set(issues['zone_confusion']))
        single_event = sorted(set(issues['single_event']))
        very_short = sorted(set(issues['very_short']))

        f.write(f"Split entries: {len(split_entries)}\n")
        f.write(f"  IDs: {split_entries}\n")
        f.write(f"Fake clears: {len(fake_clears)}\n")
        f.write(f"  IDs: {fake_clears}\n")
        f.write(f"Long coordinate zone jumps: {len(zone_confusion)}\n")
        f.write(f"  IDs: {zone_confusion}\n")
        f.write(f"Single event: {len(single_event)}\n")
        f.write(f"Very short (<1s): {len(very_short)}\n")

        hard_issue_ids = set(split_entries + fake_clears + single_event + very_short)
        review_issue_ids = set(zone_confusion)
        total_issues = len(hard_issue_ids)
        issue_rate = total_issues / max(issues['total_checked'], 1)
        review_rate = len(review_issue_ids) / max(issues['total_checked'], 1)

        f.write(f"\nOverall issue rate: {issue_rate:.1%}\n")
        f.write(f"Unique possessions with hard issues: {total_issues}\n")
        f.write(f"Coordinate review rate: {review_rate:.1%}\n")
        f.write(f"Unique possessions with coordinate review flags: {len(review_issue_ids)}\n")

        if issue_rate > 0.20:
            f.write("CONCLUSION: FAIL - Possession segmentation needs fixing\n")
        elif issue_rate > 0.10:
            f.write("CONCLUSION: WARN - Moderate issues, proceed with caution\n")
        else:
            f.write("CONCLUSION: PASS - Possession segmentation acceptable\n")

    logger.info(f"Validation complete: {issue_rate:.1%} issue rate")
    logger.info(f"Full report: {output_file}")

    return issues, issue_rate


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    db = DatabaseConnection()
    db.connect()
    try:
        validate_possessions(db, sample_size=50)
    finally:
        db.close()
