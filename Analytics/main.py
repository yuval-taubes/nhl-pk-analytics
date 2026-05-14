#!/usr/bin/env python3
"""
NHL Penalty Kill Analytics - Main Orchestrator
Runs validation gates, xG model, then Model 1.
"""

import logging
import sys
import os
from datetime import datetime

os.makedirs('runs', exist_ok=True)
os.makedirs('models/trained', exist_ok=True)

from db import DatabaseConnection
from diagnostics.join_explosion import diagnose_join_explosion
from diagnostics.validate_coordinates import validate_coordinates
from diagnostics.validate_possessions import validate_possessions
from config import Thresholds

logger = logging.getLogger(__name__)


def main():
    start_time = datetime.now()
    logger.info(f"NHL PK Analytics - Pipeline Start: {start_time.isoformat()}")
    
    db = DatabaseConnection()
    db.connect()
    
    try:
        # ================================================================
        # GATE 1: Join explosion check
        # ================================================================
        logger.info("\n" + "=" * 60)
        logger.info("GATE 1: Join Explosion Diagnostic")
        logger.info("=" * 60)
        
        join_results = diagnose_join_explosion(db)
        
        for label, raw_key, dedup_key in [
            ('Forward Forechecking', 'model6_raw', 'model6_deduped'),
            ('Defenseman Gap Control', 'model7_raw', 'model7_deduped'),
            ('Shot Suppression', 'model8_raw', 'model8_deduped'),
            ('Net-Front Defense', 'model10_raw', 'model10_deduped')
        ]:
            raw = join_results.get(raw_key, 0)
            dedup = join_results.get(dedup_key, raw)
            ratio = raw / dedup if dedup > 0 else float('inf')
            
            if ratio > Thresholds.MAX_JOIN_INFLATION:
                logger.error(f"  {label}: {ratio:.1f}x inflation - REQUIRES DISTINCT ON")
                raise ValueError(f"Join explosion detected: {label} ({ratio:.1f}x)")
            elif ratio > 1.5:
                logger.warning(f"  {label}: {ratio:.1f}x inflation")
            else:
                logger.info(f"  {label}: {ratio:.1f}x - ok")
        
        logger.info("GATE 1 PASSED")
        
        # ================================================================
        # GATE 2: Coordinate validation
        # ================================================================
        logger.info("\n" + "=" * 60)
        logger.info("GATE 2: Coordinate Validation")
        logger.info("=" * 60)
        
        coord_checks, coord_passed = validate_coordinates(db)
        
        if not coord_passed:
            raise ValueError("Coordinate validation failed - check log for details")
        
        logger.info("GATE 2 PASSED")
        
        # ================================================================
        # GATE 3: Possession quality
        # ================================================================
        logger.info("\n" + "=" * 60)
        logger.info("GATE 3: Possession Validation")
        logger.info("=" * 60)
        
        issues, issue_rate = validate_possessions(db, sample_size=50)
        
        if issue_rate > Thresholds.MAX_POSSESSION_ISSUE_RATE:
            raise ValueError(
                f"Possession quality failure: {issue_rate:.1%} issue rate "
                f"(threshold: {Thresholds.MAX_POSSESSION_ISSUE_RATE:.1%})"
            )
        
        logger.info(f"GATE 3 PASSED (issue rate: {issue_rate:.1%})")
        
        # ================================================================
        # GATE 4: xG Model training and backfill
        # ================================================================
        logger.info("\n" + "=" * 60)
        logger.info("GATE 4: xG Model Training")
        logger.info("=" * 60)
        
        from models.xg_model import XGModel
        
        xg = XGModel(db)
        model_path = 'models/trained/xg_model.joblib'
        
        if os.path.exists(model_path):
            logger.info("Loading existing xG model...")
            xg.load_model(model_path)
            logger.info(f"  AUC: {xg.training_metrics.get('auc', 'N/A'):.4f}")
            logger.info("Backfilling xG values...")
            xg.backfill_xg()
        else:
            logger.info("Training new xG model...")
            xg.train()
            xg.save_model(model_path)
            xg.backfill_xg()
        
        # Validate xG quality
        auc = xg.training_metrics.get('auc', 0)
        if auc < Thresholds.MIN_XG_AUC:
            logger.error(f"xG AUC {auc:.4f} below threshold {Thresholds.MIN_XG_AUC}")
            raise ValueError("xG model quality insufficient")
        
        logger.info("GATE 4 PASSED")
        
        # ================================================================
        # ALL GATES PASSED - Run Model 1
        # ================================================================
        logger.info("\n" + "=" * 60)
        logger.info("ALL VALIDATION GATES PASSED")
        logger.info("Running Model 1: Controlled Entry Impact Analysis")
        logger.info("=" * 60)
        
        from models.model1_blue_line import BlueLineDenialModel
        
        model1 = BlueLineDenialModel(db)
        results = model1.run()
        
        # Save results
        import json
        results_path = f"runs/model1_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"\nResults saved to {results_path}")
        logger.info(f"\n{'='*60}")
        logger.info(f"INTERPRETATION:")
        logger.info(f"{results['estimated_effect']['interpretation']}")
        logger.info(f"{'='*60}")
        
        end_time = datetime.now()
        logger.info(f"\nPipeline complete: {end_time.isoformat()}")
        logger.info(f"Duration: {end_time - start_time}")
        
        return results
        
    except Exception as e:
        logger.error(f"\nPIPELINE FAILED: {e}")
        sys.exit(1)
    
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    main()
