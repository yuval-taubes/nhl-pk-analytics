"""
Validate shot and event coordinates for physical plausibility.
Checks rink bounds, distance distributions, and coordinate clustering.
"""

import logging
from db import DatabaseConnection

logger = logging.getLogger(__name__)


def validate_coordinates(db):
    """
    Run spatial sanity checks on all coordinate data.
    
    Returns:
        (checks_dict, passed_bool)
    """
    
    checks = {}
    critical_issues = False
    
    # Check 1: Shots within rink bounds
    logger.info("Checking shot coordinate bounds...")
    bounds = db.query_to_df("""
        SELECT 
            COUNT(*) as total_shots,
            SUM(CASE WHEN x_norm < 0 OR x_norm > 200 THEN 1 ELSE 0 END) as bad_x,
            SUM(CASE WHEN y_norm < 0 OR y_norm > 85 THEN 1 ELSE 0 END) as bad_y,
            SUM(CASE WHEN x_norm IS NULL OR y_norm IS NULL THEN 1 ELSE 0 END) as null_coords
        FROM shots
    """)
    
    checks['shot_bounds'] = bounds.to_dict('records')[0]
    total = checks['shot_bounds']['total_shots']
    bad = checks['shot_bounds']['bad_x'] + checks['shot_bounds']['bad_y']
    
    if bad > 0:
        pct = bad / total * 100 if total > 0 else 0
        logger.error(f"FOUND {bad} SHOTS OUTSIDE RINK BOUNDS ({pct:.2f}%)")
        logger.error("These will corrupt all distance/angle calculations")
        critical_issues = True
    else:
        logger.info(f"All {total:,} shots within rink bounds [0,200] x [0,85]")
    
    # Check 2: Behind-net locations
    behind = db.query_to_df("""
        SELECT COUNT(*) as count
        FROM shots
        WHERE (x_norm < 0 OR x_norm > 200)
          AND shot_type != 'wrap-around'
    """)
    checks['behind_net'] = int(behind['count'].iloc[0])
    
    if checks['behind_net'] > 100:
        logger.error(f"{checks['behind_net']} shots behind net - coordinate system may be flipped")
        critical_issues = True
    elif checks['behind_net'] > 0:
        logger.warning(f"{checks['behind_net']} shots behind net - investigate")
    else:
        logger.info("No impossible behind-net shot locations")
    
    # Check 3: Distance distribution
    logger.info("Checking distance distributions...")
    dist = db.query_to_df("""
        WITH shot_net AS (
            SELECT
                s.x_norm,
                s.y_norm,
                CASE
                    WHEN ABS(s.x_norm - 11) <= ABS(s.x_norm - 189) THEN 11
                    ELSE 189
                END AS target_net_x
            FROM shots s
            JOIN events e ON s.event_id = e.event_id
            WHERE s.x_norm IS NOT NULL
              AND s.y_norm IS NOT NULL
              AND e.event_team_id IS NOT NULL
        )
        SELECT
            AVG(SQRT(POWER(x_norm - target_net_x, 2) + POWER(y_norm - 42.5, 2))) as avg_ft,
            MIN(SQRT(POWER(x_norm - target_net_x, 2) + POWER(y_norm - 42.5, 2))) as min_ft,
            MAX(SQRT(POWER(x_norm - target_net_x, 2) + POWER(y_norm - 42.5, 2))) as max_ft
        FROM shot_net
        WHERE target_net_x IS NOT NULL
    """)
    checks['distance'] = dist.to_dict('records')[0]
    
    if checks['distance']['max_ft'] > 120:
        logger.warning(
            f"Max shot distance {checks['distance']['max_ft']:.0f}ft - "
            f"possible coordinate orientation issue (using wrong net)"
        )
    
    logger.info(
        f"Distance: min={checks['distance']['min_ft']:.1f}ft, "
        f"avg={checks['distance']['avg_ft']:.1f}ft, "
        f"max={checks['distance']['max_ft']:.1f}ft"
    )
    
    # Check 4: Zone coordinate consistency
    logger.info("Checking zone/coordinate consistency...")
    zone_coords = db.query_to_df("""
        SELECT 
            zone,
            COUNT(*) as count,
            AVG(x_norm) as avg_x,
            MIN(x_norm) as min_x,
            MAX(x_norm) as max_x
        FROM events
        WHERE x_norm IS NOT NULL AND zone IS NOT NULL
        GROUP BY zone
        ORDER BY zone
    """)
    checks['zone_coords'] = zone_coords.to_dict('records')
    
    for row in checks['zone_coords']:
        zone = row['zone']
        avg_x = row['avg_x']
        logger.info(f"  Zone '{zone}': avg_x={avg_x:.1f}, "
                   f"range=[{row['min_x']:.0f}, {row['max_x']:.0f}], "
                   f"n={row['count']:,}")
    
    # Check 5: Coordinate clustering (scorekeeper artifacts)
    clusters = db.query_to_df("""
        SELECT 
            ROUND(x_norm) as x_bin,
            ROUND(y_norm) as y_bin,
            COUNT(*) as count
        FROM shots
        WHERE x_norm IS NOT NULL AND y_norm IS NOT NULL
        GROUP BY ROUND(x_norm), ROUND(y_norm)
        HAVING COUNT(*) > 500
        ORDER BY count DESC
        LIMIT 10
    """)
    
    if len(clusters) > 0:
        logger.warning(f"Found {len(clusters)} coordinate clusters (possible scorekeeper rounding):")
        for _, row in clusters.iterrows():
            logger.warning(f"  ({row['x_bin']:.0f}, {row['y_bin']:.0f}): {row['count']:,} shots")
    else:
        logger.info("No suspicious coordinate clustering detected")
    
    # Summary
    if critical_issues:
        logger.error("\nCOORDINATE VALIDATION FAILED")
    else:
        logger.info("\nCoordinate validation passed")
    
    return checks, not critical_issues


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    db = DatabaseConnection()
    db.connect()
    try:
        validate_coordinates(db)
    finally:
        db.close()
