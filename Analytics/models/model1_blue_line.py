"""
Model 1: Blue Line Denial Causal Effect
Only model with causal claims. Propensity score matching + clustered bootstrap.
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime

from db import DatabaseConnection
from utils.bootstrap import cluster_bootstrap_by_game

logger = logging.getLogger(__name__)


class BlueLineDenialModel:
    """Causal effect of controlled entry vs dump-in on PK xGA."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None
        self.estimate = None
        self.bootstrap_result = None
    
    def fetch_data(self):
        query = """
        SELECT 
            p.possession_id,
            p.game_id,
            p.entry_type,
            p.xg_sum,
            p.strength,
            g.home_score,
            g.away_score,
            p.team_id,
            g.home_team_id,
            g.away_team_id,
            e.period,
            e.period_time_seconds,
            e.zone AS start_zone,
            CASE WHEN p.entry_type = 'CONTROLLED' THEN 1 ELSE 0 END AS treatment,
            CASE 
                WHEN p.team_id = g.home_team_id THEN g.home_score - g.away_score
                ELSE g.away_score - g.home_score
            END AS score_diff,
            (e.period - 1) * 1200 + e.period_time_seconds AS game_seconds
        FROM possessions p
        JOIN games g ON p.game_id = g.game_id
        JOIN events e ON p.start_event_id = e.event_id
        WHERE p.strength IN ('4v5', '3v5', '3v4')
          AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
          AND p.xg_sum IS NOT NULL
          AND p.xg_sum >= 0
        """
        
        logger.info("Fetching PK possession data...")
        self.data = self.db.query_to_df(query)
        
        n_t = self.data['treatment'].sum()
        n_c = len(self.data) - n_t
        n_g = self.data['game_id'].nunique()
        
        logger.info(f"Sample: {len(self.data):,} possessions from {n_g:,} games")
        logger.info(f"  Controlled: {n_t:,} ({n_t/len(self.data)*100:.1f}%)")
        logger.info(f"  Dump-ins: {n_c:,} ({n_c/len(self.data)*100:.1f}%)")
        
        if n_t < 100 or n_c < 100:
            raise ValueError(f"Insufficient sample: {n_t} treated, {n_c} control")
        
        return self.data
    
    def estimate_effect(self):
        logger.info("Estimating causal effect...")
        
        try:
            from dowhy import CausalModel
            
            model = CausalModel(
                data=self.data,
                treatment='treatment',
                outcome='xg_sum',
                common_causes=['score_diff', 'period', 'game_seconds', 'start_zone']
            )
            
            self.estimate = model.estimate_effect(
                model.identify_effect(),
                method_name="backdoor.propensity_score_matching",
                target_units="att",
                method_params={'caliper': 0.2}
            )
            
            logger.info(f"ATT: {self.estimate.value:.4f}")
            
        except ImportError:
            logger.error("DoWhy not installed. pip install dowhy")
            raise
        
        # Game-clustered bootstrap
        logger.info("Computing bootstrap CIs...")
        
        def compute_att(df):
            try:
                m = CausalModel(
                    data=df,
                    treatment='treatment',
                    outcome='xg_sum',
                    common_causes=['score_diff', 'period', 'game_seconds', 'start_zone']
                )
                return m.estimate_effect(
                    m.identify_effect(),
                    method_name="backdoor.propensity_score_matching",
                    target_units="att",
                    method_params={'caliper': 0.2}
                ).value
            except Exception:
                return np.nan
        
        self.bootstrap_result = cluster_bootstrap_by_game(
            data=self.data,
            game_id_column='game_id',
            statistic_func=compute_att,
            n_bootstrap=500
        )
        
        logger.info(f"Bootstrap: {self.bootstrap_result['value']:.4f} "
                   f"[{self.bootstrap_result['ci_lower']:.4f}, "
                   f"{self.bootstrap_result['ci_upper']:.4f}]")
    
    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 1: Blue Line Denial")
        logger.info("=" * 60)
        
        self.fetch_data()
        self.estimate_effect()
        
        return {
            'model': 'Blue Line Denial Analysis',
            'estimated_effect': {
                'att': float(self.estimate.value),
                'ci_lower': float(self.bootstrap_result['ci_lower']),
                'ci_upper': float(self.bootstrap_result['ci_upper']),
                'n_games': self.bootstrap_result['n_games'],
                'interpretation': (
                    f"Controlled entries associated with "
                    f"{self.estimate.value:.4f} additional xG against "
                    f"(95% CI: [{self.bootstrap_result['ci_lower']:.4f}, "
                    f"{self.bootstrap_result['ci_upper']:.4f}])"
                )
            },
            'caveats': [
                "Entry classification is automated, not manually validated",
                "Causal identification assumes no unmeasured confounders",
                "Results are average effects; team-specific effects may differ",
                "Bootstrap CIs account for game clustering but not opponent strength"
            ],
            'sample': {
                'n_possessions': len(self.data),
                'n_games': self.data['game_id'].nunique(),
                'n_controlled': int(self.data['treatment'].sum()),
                'n_dump_in': int(len(self.data) - self.data['treatment'].sum())
            },
            'completed_at': datetime.now().isoformat()
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    db = DatabaseConnection()
    db.connect()
    try:
        results = BlueLineDenialModel(db).run()
        print(f"\n{results['estimated_effect']['interpretation']}")
    finally:
        db.close()