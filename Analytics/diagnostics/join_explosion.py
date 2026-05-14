"""
Measure row inflation from event_players joins before/after DISTINCT ON.
Must run before any player-level model to detect join explosions.
"""

import logging
from db import DatabaseConnection

logger = logging.getLogger(__name__)


def diagnose_join_explosion(db):
    """Compare raw vs deduped row counts for player-event join patterns."""
    
    tests = {
        'model6_raw': """
            SELECT COUNT(*) as row_count
            FROM event_players ep
            JOIN events e ON ep.event_id = e.event_id
            JOIN possessions p ON e.game_id = p.game_id 
                AND e.event_id BETWEEN p.start_event_id AND p.end_event_id
            WHERE p.strength IN ('4v5', '3v5', '3v4')
              AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
        """,
        
        'model6_deduped': """
            SELECT COUNT(*) as row_count
            FROM (
                SELECT DISTINCT ON (ep.player_id, p.possession_id)
                    ep.player_id, p.possession_id
                FROM event_players ep
                JOIN events e ON ep.event_id = e.event_id
                JOIN possessions p ON e.game_id = p.game_id 
                    AND e.event_id BETWEEN p.start_event_id AND p.end_event_id
                WHERE p.strength IN ('4v5', '3v5', '3v4')
                  AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
            ) dedup
        """,
        
        'model7_raw': """
            SELECT COUNT(*) as row_count
            FROM event_players ep
            JOIN events e ON ep.event_id = e.event_id
            JOIN possessions p ON e.game_id = p.game_id 
                AND e.event_id BETWEEN p.start_event_id AND p.end_event_id
            JOIN players pl ON ep.player_id = pl.player_id
            WHERE p.strength IN ('4v5', '3v5', '3v4')
              AND pl.position IN ('LD', 'RD', 'D')
        """,
        
        'model7_deduped': """
            SELECT COUNT(*) as row_count
            FROM (
                SELECT DISTINCT ON (ep.player_id, p.possession_id)
                    ep.player_id, p.possession_id
                FROM event_players ep
                JOIN events e ON ep.event_id = e.event_id
                JOIN possessions p ON e.game_id = p.game_id 
                    AND e.event_id BETWEEN p.start_event_id AND p.end_event_id
                JOIN players pl ON ep.player_id = pl.player_id
                WHERE p.strength IN ('4v5', '3v5', '3v4')
                  AND pl.position IN ('LD', 'RD', 'D')
            ) dedup
        """,
        
        'model8_raw': """
            SELECT COUNT(*) as row_count
            FROM shots s
            JOIN events e ON s.event_id = e.event_id
            JOIN event_players ep ON e.event_id = ep.event_id
            WHERE e.strength IN ('4v5', '3v5', '3v4')
        """,
        
        'model8_deduped': """
            SELECT COUNT(*) as row_count
            FROM (
                SELECT DISTINCT ON (s.shot_id, ep.player_id)
                    s.shot_id, ep.player_id
                FROM shots s
                JOIN events e ON s.event_id = e.event_id
                JOIN event_players ep ON e.event_id = ep.event_id
                WHERE e.strength IN ('4v5', '3v5', '3v4')
            ) dedup
        """,
        
        'model10_raw': """
            SELECT COUNT(*) as row_count
            FROM shots s
            JOIN events e ON s.event_id = e.event_id
            JOIN event_players ep ON e.event_id = ep.event_id
            JOIN players pl ON ep.player_id = pl.player_id
            WHERE e.strength IN ('4v5', '3v5', '3v4')
              AND pl.position IN ('LD', 'RD', 'D')
              AND s.x_norm IS NOT NULL
        """,
        
        'model10_deduped': """
            SELECT COUNT(*) as row_count
            FROM (
                SELECT DISTINCT ON (s.shot_id, ep.player_id)
                    s.shot_id, ep.player_id
                FROM shots s
                JOIN events e ON s.event_id = e.event_id
                JOIN event_players ep ON e.event_id = ep.event_id
                JOIN players pl ON ep.player_id = pl.player_id
                WHERE e.strength IN ('4v5', '3v5', '3v4')
                  AND pl.position IN ('LD', 'RD', 'D')
                  AND s.x_norm IS NOT NULL
            ) dedup
        """
    }
    
    results = {}
    
    for test_name, query in tests.items():
        df = db.query_to_df(query)
        count = df['row_count'].iloc[0] if not df.empty else 0
        results[test_name] = count
    
    logger.info("=" * 60)
    logger.info("JOIN EXPLOSION DIAGNOSTIC")
    logger.info("=" * 60)
    
    pairs = [
        ('model6_raw', 'model6_deduped', 'Forward Forechecking'),
        ('model7_raw', 'model7_deduped', 'Defenseman Gap Control'),
        ('model8_raw', 'model8_deduped', 'Shot Suppression'),
        ('model10_raw', 'model10_deduped', 'Net-Front Defense')
    ]
    
    for raw_key, dedup_key, label in pairs:
        raw = results.get(raw_key, 0)
        dedup = results.get(dedup_key, raw) if raw > 0 else 1
        ratio = raw / dedup if dedup > 0 else float('inf')
        
        logger.info(f"\n{label}:")
        logger.info(f"  Raw rows:    {raw:>10,}")
        logger.info(f"  Deduped:     {dedup:>10,}")
        logger.info(f"  Inflation:   {ratio:>10.1f}x")
        
        if ratio > 3.0:
            logger.error("  CRITICAL: DISTINCT ON required before player-level models")
        elif ratio > 1.5:
            logger.warning("  Warning: DISTINCT ON recommended")
        else:
            logger.info("  Acceptable")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    db = DatabaseConnection()
    db.connect()
    try:
        diagnose_join_explosion(db)
    finally:
        db.close()
