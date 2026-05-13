"""
Sample 50 possessions and log full event chains for manual review.
Outputs to file. For detecting split entries, fake clears, and zone confusion.
"""

import logging
import os
import pandas as pd
from datetime import datetime
from db import DatabaseConnection

logger = logging.getLogger(__name__)


def _safe_text(value, fallback='?'):
    if pd.isna(value):
        return fallback
    text = str(value)
    return text if text else fallback


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

    # Stratified sample by entry type
    query = """
    (SELECT possession_id, game_id, start_event_id, end_event_id,
            entry_type, end_type, strength, start_zone, duration_seconds,
            'CONTROLLED' as stratum
     FROM possessions 
     WHERE strength IN ('4v5', '3v5') AND entry_type = 'CONTROLLED'
     ORDER BY RANDOM() LIMIT %s)
    UNION ALL
    (SELECT possession_id, game_id, start_event_id, end_event_id,
            entry_type, end_type, strength, start_zone, duration_seconds,
            'DUMP_IN' as stratum
     FROM possessions 
     WHERE strength IN ('4v5', '3v5') AND entry_type = 'DUMP_IN'
     ORDER BY RANDOM() LIMIT %s)
    UNION ALL
    (SELECT possession_id, game_id, start_event_id, end_event_id,
            entry_type, end_type, strength, start_zone, duration_seconds,
            'TURNOVER' as stratum
     FROM possessions 
     WHERE strength IN ('4v5', '3v5') AND entry_type = 'TURNOVER'
     ORDER BY RANDOM() LIMIT %s)
    UNION ALL
    (SELECT possession_id, game_id, start_event_id, end_event_id,
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
    
    with open(output_file, 'w') as f:
        f.write("POSSESSION VALIDATION REPORT\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Sample size: {len(possessions)}\n")
        f.write("=" * 80 + "\n\n")
        
        for idx, (_, possession) in enumerate(possessions.iterrows()):
            pid = possession['possession_id']
            
            f.write(f"\n{'='*80}\n")
            f.write(f"POSSESSION #{idx+1} (ID: {pid})\n")
            f.write(f"Stratum: {possession['stratum']}\n")
            f.write(f"Entry: {possession['entry_type']} -> End: {possession['end_type']}\n")
            f.write(f"Strength: {possession['strength']} | Zone: {possession['start_zone']}\n")
            f.write(f"Duration: {possession['duration_seconds']}s\n")
            f.write(f"{'='*80}\n")
            f.write(f"{'Event':30s} | {'Zone':5s} | Time | Team | Flags\n")
            f.write(f"{'-'*80}\n")
            
            # Get full event chain
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
            """, (possession['game_id'], possession['start_event_id'], 
                  possession['end_event_id']))
            
            prev_zone = None
            prev_team = None
            
            for _, event in events.iterrows():
                flags = []
                
                # Check zone jumps
                event_type = _safe_text(event['event_type'], 'unknown')
                zone = _safe_text(event['zone'])
                team_abbrev = _safe_text(event['team_abbrev'])
                period = int(event['period']) if not pd.isna(event['period']) else 0
                period_time = int(event['period_time_seconds']) if not pd.isna(event['period_time_seconds']) else 0
                event_team = None if pd.isna(event['event_team_id']) else event['event_team_id']

                if prev_zone and zone != '?' and prev_zone != zone:
                    if prev_zone == 'OZ' and zone == 'DZ':
                        flags.append("OZ->DZ_JUMP")
                        issues['zone_confusion'].append(pid)
                    elif prev_zone == 'DZ' and zone == 'OZ':
                        flags.append("DZ->OZ_JUMP")
                        issues['zone_confusion'].append(pid)
                
                # Check team changes
                if prev_team is not None and event_team is not None and prev_team != event_team:
                    flags.append("TEAM_CHANGE")
                    if event_type not in ('takeaway', 'giveaway', 'blocked-shot', 'faceoff'):
                        issues['fake_clears'].append(pid)
                
                flag_str = ", ".join(flags) if flags else ""

                f.write(f"{event_type:30s} | {zone:5s} | "
                       f"P{period} {period_time:5d}s | "
                       f"{team_abbrev:4s} | {flag_str}\n")
                
                prev_zone = None if zone == '?' else zone
                prev_team = event_team
            
            # Possession-level checks
            if len(events) <= 1:
                f.write("\nWARNING: SINGLE-EVENT POSSESSION - likely split entry\n")
                issues['single_event'].append(pid)
                issues['split_entries'].append(pid)
            
            if possession['duration_seconds'] and possession['duration_seconds'] < 1:
                f.write(f"\nWARNING: Very short duration ({possession['duration_seconds']}s)\n")
                issues['very_short'].append(pid)
            
            issues['total_checked'] += 1
            
            if (idx + 1) % 10 == 0:
                logger.info(f"Processed {idx+1}/{len(possessions)} possessions...")
        
        # Summary
        f.write(f"\n\n{'='*80}\nSUMMARY\n{'='*80}\n")
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
        f.write(f"Zone confusion: {len(zone_confusion)}\n")
        f.write(f"  IDs: {zone_confusion}\n")
        f.write(f"Single event: {len(single_event)}\n")
        f.write(f"Very short (<1s): {len(very_short)}\n")
        
        unique_issue_ids = set(split_entries + fake_clears + zone_confusion)
        total_issues = len(unique_issue_ids)
        issue_rate = total_issues / max(issues['total_checked'], 1)
        
        f.write(f"\nOverall issue rate: {issue_rate:.1%}\n")
        f.write(f"Unique possessions with issues: {total_issues}\n")
        
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
