"""
Model 1: Blue Line Denial / Entry Impact.

This is an exploratory treatment-effect workflow using propensity score
matching and game-clustered bootstrap intervals. Do not treat the result as a
settled causal estimate until entry classification and possession segmentation
are manually validated.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from db import DatabaseConnection
from utils.bootstrap import cluster_bootstrap_by_game

logger = logging.getLogger(__name__)


class BlueLineDenialModel:
    """Estimated association between controlled entries and PK xGA."""

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
            CASE WHEN p.team_id = g.home_team_id THEN 1 ELSE 0 END AS is_home_team,
            e.period,
            e.period_time_seconds,
            e.zone AS start_zone,
            CASE WHEN p.entry_type = 'CONTROLLED' THEN 1 ELSE 0 END AS treatment,
            CASE
                WHEN p.team_id = g.home_team_id THEN g.home_score - g.away_score
                ELSE g.away_score - g.home_score
            END AS score_diff,
            (e.period - 1) * 1200 + e.period_time_seconds AS game_seconds,
            p.duration_seconds,
            p.shot_count
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

        if self.data.empty:
            raise ValueError("No PK possession data available for Model 1")

        n_treated = int(self.data['treatment'].sum())
        n_control = int(len(self.data) - n_treated)
        n_games = int(self.data['game_id'].nunique())

        logger.info(f"Sample: {len(self.data):,} possessions from {n_games:,} games")
        logger.info(f"  Controlled: {n_treated:,} ({n_treated / len(self.data) * 100:.1f}%)")
        logger.info(f"  Dump-ins: {n_control:,} ({n_control / len(self.data) * 100:.1f}%)")

        if n_treated < 100 or n_control < 100:
            raise ValueError(f"Insufficient sample: {n_treated} treated, {n_control} control")

        return self.data

    def _prepare_model_frame(self, data):
        """Return numeric modeling frame and covariate list for DoWhy."""
        frame = data.copy()
        frame['xg_sum'] = frame['xg_sum'].fillna(0).astype(float)
        frame['score_diff'] = frame['score_diff'].fillna(0).astype(float)
        frame['period'] = frame['period'].fillna(0).astype(int)
        frame['game_seconds'] = frame['game_seconds'].fillna(0).astype(float)
        frame['is_home_team'] = frame['is_home_team'].fillna(0).astype(int)
        frame['duration_seconds'] = frame['duration_seconds'].fillna(0).astype(float)
        frame['shot_count'] = frame['shot_count'].fillna(0).astype(float)

        frame = pd.get_dummies(
            frame,
            columns=['strength', 'start_zone'],
            prefix=['strength', 'start_zone'],
            dummy_na=True,
            dtype=int
        )

        common_causes = [
            'score_diff',
            'period',
            'game_seconds',
            'is_home_team',
            'duration_seconds',
            'shot_count'
        ]
        common_causes.extend([c for c in frame.columns if c.startswith('strength_')])
        common_causes.extend([c for c in frame.columns if c.startswith('start_zone_')])

        return frame, common_causes

    def estimate_effect(self):
        logger.info("Estimating entry-type association...")

        try:
            from dowhy import CausalModel
        except ImportError:
            logger.error("DoWhy not installed. Run: pip install dowhy")
            raise

        model_data, common_causes = self._prepare_model_frame(self.data)
        model = CausalModel(
            data=model_data,
            treatment='treatment',
            outcome='xg_sum',
            common_causes=common_causes
        )

        self.estimate = model.estimate_effect(
            model.identify_effect(),
            method_name="backdoor.propensity_score_matching",
            target_units="att",
            method_params={'caliper': 0.2}
        )

        logger.info(f"Estimated ATT: {self.estimate.value:.4f}")
        logger.info("Computing game-clustered bootstrap CIs...")

        def compute_att(df):
            try:
                bootstrap_frame, bootstrap_causes = self._prepare_model_frame(df)
                bootstrap_model = CausalModel(
                    data=bootstrap_frame,
                    treatment='treatment',
                    outcome='xg_sum',
                    common_causes=bootstrap_causes
                )
                estimate = bootstrap_model.estimate_effect(
                    bootstrap_model.identify_effect(),
                    method_name="backdoor.propensity_score_matching",
                    target_units="att",
                    method_params={'caliper': 0.2}
                )
                return estimate.value
            except Exception:
                return np.nan

        self.bootstrap_result = cluster_bootstrap_by_game(
            data=self.data,
            game_id_column='game_id',
            statistic_func=compute_att,
            n_bootstrap=500
        )

        logger.info(
            f"Bootstrap: {self.bootstrap_result['value']:.4f} "
            f"[{self.bootstrap_result['ci_lower']:.4f}, "
            f"{self.bootstrap_result['ci_upper']:.4f}]"
        )

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 1: Blue Line Denial / Entry Impact")
        logger.info("=" * 60)

        self.fetch_data()
        self.estimate_effect()

        return {
            'model': 'Blue Line Denial / Entry Impact Analysis',
            'estimated_effect': {
                'att': float(self.estimate.value),
                'ci_lower': float(self.bootstrap_result['ci_lower']),
                'ci_upper': float(self.bootstrap_result['ci_upper']),
                'n_games': self.bootstrap_result['n_games'],
                'interpretation': (
                    f"Controlled entries are associated with "
                    f"{self.estimate.value:.4f} additional xG against "
                    f"(95% CI: [{self.bootstrap_result['ci_lower']:.4f}, "
                    f"{self.bootstrap_result['ci_upper']:.4f}])"
                )
            },
            'caveats': [
                "Exploratory result; do not treat as a settled causal claim",
                "Entry classification is automated, not manually validated",
                "Possession segmentation must pass validation before interpretation",
                "Identification still assumes no unmeasured confounders",
                "Results are average effects; team-specific effects may differ",
                "Bootstrap CIs account for game clustering but not team/opponent clustering"
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
