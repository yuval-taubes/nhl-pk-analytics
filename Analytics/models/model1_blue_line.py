"""
Model 1: Blue Line Denial / Entry Impact.

This is an exploratory treatment-effect workflow using propensity score
matching and game-clustered bootstrap intervals. Do not treat the result as a
settled causal estimate until entry classification and possession segmentation
are manually validated.
"""

import logging
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from db import DatabaseConnection
from config import Thresholds
from utils.bootstrap import cluster_bootstrap_by_game

logger = logging.getLogger(__name__)


class BlueLineDenialModel:
    """Estimated association between PP controlled entries and PK xGA."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None
        self.estimate = None
        self.bootstrap_result = None

    def fetch_data(self):
        query = """
        WITH pp_possessions AS (
            SELECT
                p.*,
                CASE
                    WHEN split_part(p.strength, 'v', 1)::int > split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int > split_part(p.strength, 'v', 1)::int THEN g.home_team_id
                    ELSE NULL
                END AS pp_team_id,
                CASE
                    WHEN split_part(p.strength, 'v', 1)::int < split_part(p.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(p.strength, 'v', 2)::int < split_part(p.strength, 'v', 1)::int THEN g.home_team_id
                    ELSE NULL
                END AS pk_team_id
            FROM possessions p
            JOIN games g ON p.game_id = g.game_id
            WHERE p.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
              AND p.entry_type IN ('CONTROLLED', 'DUMP_IN')
              AND p.xg_sum IS NOT NULL
              AND p.xg_sum >= 0
        )
        SELECT
            p.possession_id,
            p.game_id,
            p.entry_type,
            p.xg_sum,
            p.strength,
            g.home_score,
            g.away_score,
            p.team_id AS pp_team_id,
            p.pk_team_id,
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
            END AS pp_score_diff,
            (e.period - 1) * 1200 + e.period_time_seconds AS game_seconds,
            p.duration_seconds,
            p.shot_count
        FROM pp_possessions p
        JOIN games g ON p.game_id = g.game_id
        JOIN events e ON p.start_event_id = e.event_id
        WHERE p.team_id = p.pp_team_id
          AND e.event_type <> 'faceoff'
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

        if n_treated < Thresholds.MIN_POSSESSIONS_FOR_ATT or n_control < Thresholds.MIN_POSSESSIONS_FOR_ATT:
            raise ValueError(f"Insufficient sample: {n_treated} treated, {n_control} control")
        if (
            n_treated < Thresholds.TARGET_POSSESSIONS_FOR_ATT
            or n_control < Thresholds.TARGET_POSSESSIONS_FOR_ATT
        ):
            logger.warning(
                "Small exploratory sample below target size "
                f"({n_treated} treated, {n_control} control); interpret Model 1 cautiously."
            )

        return self.data

    def _prepare_model_frame(self, data):
        """Return numeric modeling frame and covariate list for DoWhy."""
        frame = data.copy()
        frame['xg_sum'] = frame['xg_sum'].fillna(0).astype(float)
        frame['pp_score_diff'] = frame['pp_score_diff'].fillna(0).astype(float)
        frame['period'] = frame['period'].fillna(0).astype(int)
        frame['game_seconds'] = frame['game_seconds'].fillna(0).astype(float)
        frame['is_home_team'] = frame['is_home_team'].fillna(0).astype(int)
        frame = pd.get_dummies(
            frame,
            columns=['strength', 'start_zone'],
            prefix=['strength', 'start_zone'],
            dummy_na=True,
            dtype=int
        )

        common_causes = [
            'pp_score_diff',
            'period',
            'game_seconds',
            'is_home_team'
        ]
        common_causes.extend([c for c in frame.columns if c.startswith('strength_')])
        common_causes.extend([c for c in frame.columns if c.startswith('start_zone_')])

        return frame, common_causes

    def estimate_effect(self):
        logger.info("Estimating entry-type association...")

        att, diagnostics = self._estimate_att_psm(self.data, return_diagnostics=True)
        self.estimate = SimpleNamespace(value=att)
        self.matching_diagnostics = diagnostics

        logger.info(f"Estimated ATT: {self.estimate.value:.4f}")
        logger.info("Computing game-clustered bootstrap CIs...")

        def compute_att(df):
            try:
                return self._estimate_att_psm(df)
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

    def _estimate_att_psm(self, data, caliper=0.2, return_diagnostics=False):
        """
        Estimate ATT with simple one-to-one propensity score matching.

        This keeps Model 1 independent from DoWhy/networkx version churn while
        retaining the intended exploratory matching workflow.
        """
        frame, common_causes = self._prepare_model_frame(data)
        treated = frame[frame['treatment'] == 1].copy()
        controls = frame[frame['treatment'] == 0].copy()

        if treated.empty or controls.empty:
            diagnostics = {
                'treated_total': int(len(treated)),
                'control_total': int(len(controls)),
                'treated_matched': 0,
                'match_rate': 0.0,
                'mean_distance': None,
                'max_distance': None,
                'unique_controls_used': 0,
                'caliper': float(caliper),
            }
            return (np.nan, diagnostics) if return_diagnostics else np.nan

        X = frame[common_causes].astype(float)
        y = frame['treatment'].astype(int)

        propensity_model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, random_state=42)
        )
        propensity_model.fit(X, y)

        frame = frame.copy()
        frame['propensity'] = propensity_model.predict_proba(X)[:, 1]
        treated = frame[frame['treatment'] == 1].copy()
        controls = frame[frame['treatment'] == 0].copy()

        nn = NearestNeighbors(n_neighbors=1)
        nn.fit(controls[['propensity']])
        distances, indices = nn.kneighbors(treated[['propensity']])

        matched_controls = controls.iloc[indices.flatten()].reset_index(drop=True)
        matched_treated = treated.reset_index(drop=True)
        keep = distances.flatten() <= caliper

        diagnostics = {
            'treated_total': int(len(treated)),
            'control_total': int(len(controls)),
            'treated_matched': int(keep.sum()),
            'match_rate': float(keep.mean()),
            'mean_distance': float(distances.flatten()[keep].mean()) if keep.sum() else None,
            'max_distance': float(distances.flatten()[keep].max()) if keep.sum() else None,
            'unique_controls_used': int(pd.Series(indices.flatten()[keep]).nunique()) if keep.sum() else 0,
            'caliper': float(caliper),
        }

        if keep.sum() == 0:
            return (np.nan, diagnostics) if return_diagnostics else np.nan

        att = float(
            matched_treated.loc[keep, 'xg_sum'].astype(float).mean()
            - matched_controls.loc[keep, 'xg_sum'].astype(float).mean()
        )
        return (att, diagnostics) if return_diagnostics else att

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 1: Blue Line Denial / Entry Impact")
        logger.info("=" * 60)

        self.fetch_data()
        self.estimate_effect()

        return {
            'model': 'Power-Play Entry Impact Against Penalty Kill',
            'estimated_effect': {
                'att': float(self.estimate.value),
                'ci_lower': float(self.bootstrap_result['ci_lower']),
                'ci_upper': float(self.bootstrap_result['ci_upper']),
                'n_games': self.bootstrap_result['n_games'],
                'interpretation': (
                    f"Power-play controlled entries are associated with "
                    f"{self.estimate.value:.4f} additional xG against the PK "
                    f"(95% CI: [{self.bootstrap_result['ci_lower']:.4f}, "
                    f"{self.bootstrap_result['ci_upper']:.4f}])"
                )
            },
            'matching': self.matching_diagnostics,
            'caveats': [
                "Exploratory result; do not treat as a settled causal claim",
                "Entry classification is automated, not manually validated",
                "Matching now uses pre-entry covariates only; duration_seconds and shot_count are reported descriptively but excluded as post-treatment variables",
                "Only power-play-owned possessions are included; shorthanded counterattack possessions are excluded",
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
