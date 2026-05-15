"""
Model 1B: Power-play entry attempt impact.

The retained-possession Model 1 only sees entries that became stored
possessions, which excludes many failed entries and can bias dump-in/control
comparisons. This attempt-level model reconstructs candidate PP entries from
events and measures PP xG generated in the next short window, assigning zero
xG to failed attempts with no shot.
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


class EntryAttemptImpactModel:
    """Estimated association between PP controlled-entry attempts and short-window xG."""

    def __init__(self, db_connection, outcome_window_seconds=20):
        self.db = db_connection
        self.outcome_window_seconds = outcome_window_seconds
        self.data = None
        self.estimate = None
        self.bootstrap_result = None

    def fetch_data(self):
        query = """
        WITH event_context AS (
            SELECT
                e.event_id,
                e.game_id,
                e.event_idx,
                e.period,
                e.period_time_seconds,
                e.event_type,
                e.event_team_id,
                e.zone,
                e.x_norm,
                e.y_norm,
                e.strength,
                g.home_team_id,
                g.away_team_id,
                g.home_score,
                g.away_score,
                LAG(e.zone) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_zone,
                LAG(e.event_team_id) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_team_id,
                LAG(e.x_norm) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_x_norm,
                LAG(e.event_type) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_event_type,
                CASE
                    WHEN split_part(e.strength, 'v', 1)::int > split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(e.strength, 'v', 2)::int > split_part(e.strength, 'v', 1)::int THEN g.home_team_id
                END AS pp_team_id,
                CASE
                    WHEN split_part(e.strength, 'v', 1)::int < split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(e.strength, 'v', 2)::int < split_part(e.strength, 'v', 1)::int THEN g.home_team_id
                END AS pk_team_id
            FROM events e
            JOIN games g ON e.game_id = g.game_id
            WHERE e.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
        ),
        candidates AS (
            SELECT
                ec.*,
                CASE
                    WHEN p.entry_type IN ('CONTROLLED', 'DUMP_IN') THEN p.entry_type
                    WHEN ec.event_type IN ('dumpin', 'dump') OR ec.prev_event_type IN ('dumpin', 'dump') THEN 'DUMP_IN'
                    WHEN ec.event_type IN ('shot-on-goal', 'missed-shot') AND ec.prev_zone = 'NZ' THEN 'DUMP_IN'
                    ELSE 'CONTROLLED'
                END AS entry_type,
                p.possession_id AS retained_possession_id
            FROM event_context ec
            LEFT JOIN possessions p ON p.start_event_id = ec.event_id
            WHERE ec.event_team_id = ec.pp_team_id
              AND ec.zone = 'OZ'
              AND ec.event_type NOT IN (
                  'faceoff', 'penalty', 'delayed-penalty', 'stoppage',
                  'period-start', 'period-end', 'game-end', 'hit',
                  'giveaway', 'takeaway'
              )
              AND COALESCE(ec.prev_event_type, '') NOT IN (
                  'faceoff', 'penalty', 'delayed-penalty', 'stoppage',
                  'period-start', 'period-end', 'game-end'
              )
              AND (
                  (ec.prev_team_id = ec.event_team_id AND ec.prev_zone = 'NZ')
                  OR (
                      ec.prev_x_norm BETWEEN 76 AND 124
                      AND (
                          (ec.event_team_id = ec.home_team_id AND ec.x_norm >= 125)
                          OR (ec.event_team_id = ec.away_team_id AND ec.x_norm <= 75)
                      )
                  )
              )
        )
        SELECT
            c.event_id,
            c.game_id,
            c.period,
            c.period_time_seconds,
            c.strength,
            c.entry_type,
            c.pp_team_id,
            c.pk_team_id,
            c.home_team_id,
            c.away_team_id,
            CASE WHEN c.pp_team_id = c.home_team_id THEN 1 ELSE 0 END AS is_home_pp,
            CASE
                WHEN c.pp_team_id = c.home_team_id THEN c.home_score - c.away_score
                ELSE c.away_score - c.home_score
            END AS pp_score_diff,
            (c.period - 1) * 1200 + c.period_time_seconds AS game_seconds,
            CASE WHEN c.entry_type = 'CONTROLLED' THEN 1 ELSE 0 END AS treatment,
            CASE WHEN c.retained_possession_id IS NULL THEN 0 ELSE 1 END AS retained_possession,
            COALESCE(SUM(s.xg), 0) AS window_xg,
            COUNT(s.shot_id) AS window_shots
        FROM candidates c
        LEFT JOIN events shot_event
          ON shot_event.game_id = c.game_id
         AND shot_event.period = c.period
         AND shot_event.event_team_id = c.pp_team_id
         AND shot_event.event_idx >= c.event_idx
         AND shot_event.period_time_seconds BETWEEN c.period_time_seconds AND c.period_time_seconds + %s
        LEFT JOIN shots s ON s.event_id = shot_event.event_id
        GROUP BY
            c.event_id, c.game_id, c.period, c.period_time_seconds, c.strength,
            c.entry_type, c.pp_team_id, c.pk_team_id, c.home_team_id, c.away_team_id,
            c.home_score, c.away_score, c.retained_possession_id
        """

        logger.info("Fetching PP entry attempt data...")
        self.data = self.db.query_to_df(query, (self.outcome_window_seconds,))

        if self.data.empty:
            raise ValueError("No PP entry attempt data available")

        n_treated = int(self.data['treatment'].sum())
        n_control = int(len(self.data) - n_treated)
        n_games = int(self.data['game_id'].nunique())
        retained_rate = float(self.data['retained_possession'].mean())

        logger.info(f"Sample: {len(self.data):,} attempts from {n_games:,} games")
        logger.info(f"  Controlled: {n_treated:,} ({n_treated / len(self.data) * 100:.1f}%)")
        logger.info(f"  Dump-ins: {n_control:,} ({n_control / len(self.data) * 100:.1f}%)")
        logger.info(f"  Retained possession table coverage: {retained_rate:.1%}")

        if n_treated < Thresholds.MIN_POSSESSIONS_FOR_ATT or n_control < Thresholds.MIN_POSSESSIONS_FOR_ATT:
            raise ValueError(f"Insufficient attempt sample: {n_treated} treated, {n_control} control")

        return self.data

    def _prepare_model_frame(self, data):
        frame = data.copy()
        frame['window_xg'] = frame['window_xg'].fillna(0).astype(float)
        frame['pp_score_diff'] = frame['pp_score_diff'].fillna(0).astype(float)
        frame['period'] = frame['period'].fillna(0).astype(int)
        frame['game_seconds'] = frame['game_seconds'].fillna(0).astype(float)
        frame['is_home_pp'] = frame['is_home_pp'].fillna(0).astype(int)

        frame = pd.get_dummies(
            frame,
            columns=['strength'],
            prefix=['strength'],
            dummy_na=True,
            dtype=int
        )

        common_causes = [
            'pp_score_diff',
            'period',
            'game_seconds',
            'is_home_pp',
        ]
        common_causes.extend([c for c in frame.columns if c.startswith('strength_')])

        return frame, common_causes

    def _estimate_att_psm(self, data, caliper=0.2):
        frame, common_causes = self._prepare_model_frame(data)
        treated = frame[frame['treatment'] == 1].copy()
        controls = frame[frame['treatment'] == 0].copy()

        if treated.empty or controls.empty:
            return np.nan

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

        if keep.sum() == 0:
            return np.nan

        return float(
            matched_treated.loc[keep, 'window_xg'].astype(float).mean()
            - matched_controls.loc[keep, 'window_xg'].astype(float).mean()
        )

    def estimate_effect(self):
        logger.info("Estimating attempt-level entry association...")
        att = self._estimate_att_psm(self.data)
        self.estimate = SimpleNamespace(value=att)

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

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 1B: Power-Play Entry Attempt Impact")
        logger.info("=" * 60)

        self.fetch_data()
        self.estimate_effect()

        return {
            'model': 'Power-Play Entry Attempt Impact',
            'estimated_effect': {
                'att': float(self.estimate.value),
                'ci_lower': float(self.bootstrap_result['ci_lower']),
                'ci_upper': float(self.bootstrap_result['ci_upper']),
                'n_games': self.bootstrap_result['n_games'],
                'interpretation': (
                    f"Power-play controlled entry attempts are associated with "
                    f"{self.estimate.value:.4f} additional {self.outcome_window_seconds}s xG "
                    f"against the PK (95% CI: [{self.bootstrap_result['ci_lower']:.4f}, "
                    f"{self.bootstrap_result['ci_upper']:.4f}])"
                )
            },
            'sample': {
                'n_attempts': len(self.data),
                'n_games': self.data['game_id'].nunique(),
                'n_controlled': int(self.data['treatment'].sum()),
                'n_dump_in': int(len(self.data) - self.data['treatment'].sum()),
                'retained_possession_rate': float(self.data['retained_possession'].mean()),
                'outcome_window_seconds': self.outcome_window_seconds
            },
            'caveats': [
                "Attempt classification is inferred from play-by-play events and stored possession starts",
                "Failed entries with no PP shot in the outcome window receive zero xG",
                "Outcome is short-window xG, not full power-play possession value",
                "Exploratory result; manual video validation is still needed"
            ],
            'completed_at': datetime.now().isoformat()
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    db = DatabaseConnection()
    db.connect()
    try:
        results = EntryAttemptImpactModel(db).run()
        print(f"\n{results['estimated_effect']['interpretation']}")
    finally:
        db.close()
