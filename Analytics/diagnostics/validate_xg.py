"""
Validate trained xG model outputs against basic sanity checks.
"""

import logging

from db import DatabaseConnection

logger = logging.getLogger(__name__)


def validate_xg(db, model=None):
    """Run validation checks on xG model outputs."""
    checks = {}
    all_passed = True

    if model and hasattr(model, 'training_metrics'):
        auc = model.training_metrics.get('auc', 0)
        logger.info(f"AUC: {auc:.4f}")
        if auc < 0.70:
            logger.warning("AUC below 0.70 - features may be insufficient")
            all_passed = False
        else:
            logger.info("AUC acceptable")
        checks['auc'] = auc

    rebound_check = db.query_to_df("""
        SELECT
            AVG(CASE WHEN e_prev.event_type IN ('shot-on-goal', 'missed-shot', 'blocked-shot')
                     AND e_prev.event_team_id = e.event_team_id
                     THEN s.xg END) as rebound_avg_xg,
            AVG(CASE WHEN e_prev.event_type NOT IN ('shot-on-goal', 'missed-shot', 'blocked-shot')
                      OR e_prev.event_type IS NULL
                      OR e_prev.event_team_id <> e.event_team_id
                     THEN s.xg END) as non_rebound_avg_xg
        FROM shots s
        JOIN events e ON s.event_id = e.event_id
        LEFT JOIN events e_prev ON e.game_id = e_prev.game_id
            AND e_prev.event_idx = e.event_idx - 1
        WHERE s.xg IS NOT NULL
    """)

    if not rebound_check.empty:
        rebound_avg = rebound_check['rebound_avg_xg'].iloc[0] or 0
        non_rebound_avg = rebound_check['non_rebound_avg_xg'].iloc[0] or 0

        logger.info(f"Rebound xG: {rebound_avg:.4f} vs Non-rebound: {non_rebound_avg:.4f}")

        if rebound_avg > non_rebound_avg:
            logger.info("Rebound shots have higher xG (expected)")
        else:
            logger.warning("Rebound xG not higher - check rebound detection logic")
            all_passed = False
        checks['rebound'] = {
            'rebound_xg': float(rebound_avg),
            'non_rebound_xg': float(non_rebound_avg)
        }

    distance_check = db.query_to_df("""
        WITH shot_net AS (
            SELECT
                s.x_norm,
                s.y_norm,
                s.xg,
                CASE
                    WHEN e.event_team_id = g.home_team_id THEN 189
                    WHEN e.event_team_id = g.away_team_id THEN 11
                    ELSE NULL
                END AS target_net_x
            FROM shots s
            JOIN events e ON s.event_id = e.event_id
            JOIN games g ON e.game_id = g.game_id
            WHERE s.xg IS NOT NULL
              AND s.xg > 0
              AND e.event_team_id IS NOT NULL
        )
        SELECT
            CORR(
                CAST(SQRT(POWER(x_norm - target_net_x, 2) + POWER(y_norm - 42.5, 2)) AS numeric),
                xg
            ) as dist_corr
        FROM shot_net
        WHERE target_net_x IS NOT NULL
    """)

    if not distance_check.empty:
        corr = distance_check['dist_corr'].iloc[0]
        logger.info(f"Distance-xG correlation: {corr:.4f}")
        if corr is not None and corr < 0:
            logger.info("Closer shots have higher xG (expected)")
        else:
            logger.warning("Distance-xG correlation unexpected")
            all_passed = False
        checks['distance_correlation'] = float(corr) if corr else None

    xg_dist = db.query_to_df("""
        SELECT
            MIN(xg) as min_xg,
            MAX(xg) as max_xg,
            AVG(xg) as avg_xg,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY xg) as median_xg,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY xg) as p95_xg
        FROM shots
        WHERE xg IS NOT NULL AND xg > 0
    """)

    if not xg_dist.empty:
        d = xg_dist.to_dict('records')[0]
        logger.info(
            f"xG distribution: min={d['min_xg']:.4f}, median={d['median_xg']:.4f}, "
            f"max={d['max_xg']:.4f}, p95={d['p95_xg']:.4f}"
        )

        if d['max_xg'] < 0.6:
            logger.warning("Max xG < 0.6 - model may be severely underfit")
            all_passed = False
        elif d['max_xg'] > 0.95:
            logger.warning("Max xG > 0.95 - check for data leaks")
            all_passed = False
        else:
            logger.info("xG range reasonable")
        checks['xg_distribution'] = d

    if all_passed:
        logger.info("\nxG VALIDATION PASSED")
    else:
        logger.error("\nxG VALIDATION FAILED - fix issues before Model 1")

    return checks, all_passed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    db = DatabaseConnection()
    db.connect()
    try:
        try:
            import joblib
            model_data = joblib.load('models/trained/xg_model.joblib')
            model = type('Model', (), {'training_metrics': model_data.get('training_metrics', {})})()
            validate_xg(db, model)
        except FileNotFoundError:
            logger.info("No trained model found. Running database checks only.")
            validate_xg(db)
    finally:
        db.close()
