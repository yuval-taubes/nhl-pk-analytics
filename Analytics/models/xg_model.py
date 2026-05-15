"""
Expected Goals Model - NHL Penalty Kill Analytics
Trains logistic regression on shot distance, angle, type, rebound, and strength.
Backfills xG to shots and possessions tables.
"""

import logging
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, brier_score_loss
import joblib
import os

logger = logging.getLogger(__name__)


class XGModel:
    def __init__(self, db_connection):
        self.db = db_connection
        self.model = None
        self.feature_names = None
        self.training_metrics = {}
    
    def fetch_training_data(self):
        """Fetch shots with correct geometry and rebound detection."""
        query = """
        WITH shot_chronology AS (
            SELECT 
                s.shot_id,
                s.x_norm,
                s.y_norm,
                s.shot_type,
                s.is_goal,
                e.strength,
                e.event_idx,
                e.period,
                e.period_time_seconds AS shot_time,
                e.game_id,
                e.event_team_id,
                g.home_team_id,
                g.away_team_id,
                -- Target net in home-perspective normalized coordinates.
                -- Home team attacks the away net (x=189); away team attacks
                -- the home net (x=11). This relies on ingestion resolving
                -- event_team_id to the shooter/scorer team for shot events.
                CASE 
                    WHEN e.event_team_id = g.home_team_id THEN 189
                    WHEN e.event_team_id = g.away_team_id THEN 11
                    ELSE NULL
                END AS target_net_x,
                -- Previous event for rebound detection (game-level chronology, FIXED)
                LAG(e.event_type) OVER (
                    PARTITION BY e.game_id ORDER BY e.event_idx
                ) AS prev_event_type,
                LAG(e.event_team_id) OVER (
                    PARTITION BY e.game_id ORDER BY e.event_idx
                ) AS prev_event_team,
                LAG(e.period) OVER (
                    PARTITION BY e.game_id ORDER BY e.event_idx
                ) AS prev_period,
                LAG(e.period_time_seconds) OVER (
                    PARTITION BY e.game_id ORDER BY e.event_idx
                ) AS prev_time
            FROM shots s
            JOIN events e ON s.event_id = e.event_id
            JOIN games g ON e.game_id = g.game_id
            WHERE s.x_norm IS NOT NULL 
              AND s.y_norm IS NOT NULL
              AND s.shot_type IS NOT NULL
              AND s.is_goal IS NOT NULL
              AND e.event_team_id IS NOT NULL
        )
        SELECT 
            shot_id,
            x_norm,
            y_norm,
            shot_type,
            strength,
            is_goal,
            target_net_x,
            CASE 
                WHEN prev_event_type IN ('shot-on-goal', 'missed-shot', 'blocked-shot')
                 AND prev_event_team = event_team_id
                 AND prev_period = period
                 AND (shot_time - prev_time) BETWEEN 1 AND 3
                THEN 1 ELSE 0 
            END AS is_rebound,
            SQRT(POWER(x_norm - target_net_x, 2) + POWER(y_norm - 42.5, 2)) AS distance_to_net,
            DEGREES(ATAN2(ABS(y_norm - 42.5), ABS(x_norm - target_net_x))) AS shot_angle
        FROM shot_chronology
        """
        
        logger.info("Fetching training data...")
        df = self.db.query_to_df(query)
        
        # Hard filter impossible coordinates
        initial = len(df)
        df = df[
            (df['x_norm'].between(0, 200)) &
            (df['y_norm'].between(0, 85))
        ]
        if len(df) < initial:
            logger.warning(f"Filtered {initial - len(df)} shots with impossible coordinates")

        df['is_goal'] = df['is_goal'].astype(bool).astype(int)
        
        logger.info(f"Training sample: {len(df):,} shots, "
                   f"goal rate: {df['is_goal'].mean():.3f}")
        
        # Distance diagnostics
        d = df['distance_to_net'].quantile([0.1, 0.5, 0.9, 0.99])
        logger.info(f"Distance: median={d[0.5]:.0f}ft, "
                   f"90th={d[0.9]:.0f}ft, 99th={d[0.99]:.0f}ft")
        
        # Angle diagnostics
        a = df['shot_angle'].quantile([0.1, 0.5, 0.9])
        logger.info(f"Angle: median={a[0.5]:.1f} deg, 90th={a[0.9]:.1f} deg")
        
        # Validate orientation
        if d[0.99] > 120:
            logger.warning("99th percentile distance > 120ft - check coordinate orientation")
        if a[0.5] > 60:
            logger.warning("Median angle > 60 deg - possible arctan inversion")
        
        return df
    
    def prepare_features(self, df):
        """Feature engineering for xG model."""
        features = pd.DataFrame()
        
        features['distance_to_net'] = df['distance_to_net'].fillna(50)
        features['distance_squared'] = features['distance_to_net'] ** 2
        features['shot_angle'] = df['shot_angle'].fillna(30)
        features['distance_angle'] = features['distance_to_net'] * features['shot_angle']
        features['is_rebound'] = df['is_rebound'].fillna(0).astype(int)
        
        # Shot type dummies
        for st in ['wrist', 'slap', 'snap', 'backhand', 'tip', 'wrap-around', 'deflected']:
            features[f'shot_{st}'] = (df['shot_type'].str.lower() == st).astype(int)
        
        # Strength state (5v4 is reference)
        features['strength_5v3'] = (df['strength'] == '5v3').astype(int)
        features['strength_4v3'] = (df['strength'] == '4v3').astype(int)
        features['strength_3v5'] = (df['strength'] == '3v5').astype(int)
        
        self.feature_names = features.columns.tolist()
        logger.info(f"Features ({len(self.feature_names)}): {self.feature_names}")
        
        return features
    
    def train(self, test_size=0.2, random_state=42):
        """Train logistic regression xG model."""
        
        df = self.fetch_training_data()
        X = self.prepare_features(df)
        y = df['is_goal'].astype(int).values
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        logger.info(f"Train: {len(X_train):,}, Test: {len(X_test):,}")
        
        self.model = LogisticRegression(
            max_iter=2000,
            random_state=random_state,
            C=0.1
            # No class_weight: calibration matters more than classification.
        )
        
        self.model.fit(X_train, y_train)
        
        y_pred = self.model.predict_proba(X_test)[:, 1]
        
        auc = roc_auc_score(y_test, y_pred)
        brier = brier_score_loss(y_test, y_pred)
        
        # Calibration by decile
        deciles = []
        edges = np.percentile(y_pred, np.arange(0, 101, 10))
        for i in range(10):
            mask = (y_pred >= edges[i]) & (y_pred < edges[i+1])
            if mask.sum() > 0:
                deciles.append({
                    'decile': i + 1,
                    'n': int(mask.sum()),
                    'predicted': float(y_pred[mask].mean()),
                    'actual': float(y_test[mask].mean())
                })
        
        # Feature importance
        coefs = dict(zip(self.feature_names, self.model.coef_[0].tolist()))
        
        self.training_metrics = {
            'auc': float(auc),
            'brier_score': float(brier),
            'n_train': len(X_train),
            'n_test': len(X_test),
            'goal_rate': float(y.mean()),
            'calibration': deciles,
            'feature_importance': coefs
        }
        
        logger.info(f"Training complete: AUC={auc:.4f}, Brier={brier:.4f}")
        
        if auc < 0.70:
            logger.warning(f"AUC {auc:.3f} below 0.70 - features may be insufficient")
        else:
            logger.info("AUC acceptable")
        
        if brier > 0.10:
            logger.warning(f"Brier {brier:.4f} above 0.10 - calibration check recommended")
        else:
            logger.info("Brier acceptable")
        
        # Log top coefficients
        sorted_coefs = sorted(coefs.items(), key=lambda x: x[1], reverse=True)
        logger.info("Top positive features:")
        for name, coef in sorted_coefs[:5]:
            logger.info(f"  {name}: {coef:.4f}")
        logger.info("Top negative features:")
        for name, coef in sorted_coefs[-5:]:
            logger.info(f"  {name}: {coef:.4f}")
        
        return self.model, self.training_metrics
    
    def predict(self, df):
        """Generate xG predictions."""
        if self.model is None:
            raise ValueError("Model not trained or loaded")
        X = self.prepare_features(df)
        X = X[self.feature_names]
        return self.model.predict_proba(X)[:, 1]
    
    def backfill_xg(self):
        """Backfill xG into shots and possessions tables."""
        logger.info("Backfilling xG values...")
        
        query = """
        WITH shot_chronology AS (
            SELECT 
                s.shot_id,
                s.x_norm,
                s.y_norm,
                s.shot_type,
                e.strength,
                e.event_idx,
                e.period,
                e.period_time_seconds AS shot_time,
                e.game_id,
                e.event_team_id,
                g.home_team_id,
                g.away_team_id,
                CASE 
                    WHEN e.event_team_id = g.home_team_id THEN 189
                    WHEN e.event_team_id = g.away_team_id THEN 11
                    ELSE NULL
                END AS target_net_x,
                LAG(e.event_type) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_event_type,
                LAG(e.event_team_id) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_event_team,
                LAG(e.period) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_period,
                LAG(e.period_time_seconds) OVER (PARTITION BY e.game_id ORDER BY e.event_idx) AS prev_time
            FROM shots s
            JOIN events e ON s.event_id = e.event_id
            JOIN games g ON e.game_id = g.game_id
            WHERE s.x_norm IS NOT NULL 
              AND s.y_norm IS NOT NULL
              AND s.shot_type IS NOT NULL
              AND s.xg IS NULL
              AND s.x_norm BETWEEN 0 AND 200
              AND s.y_norm BETWEEN 0 AND 85
              AND e.event_team_id IS NOT NULL
        )
        SELECT 
            shot_id,
            x_norm,
            y_norm,
            shot_type,
            strength,
            target_net_x,
            CASE 
                WHEN prev_event_type IN ('shot-on-goal', 'missed-shot', 'blocked-shot')
                 AND prev_event_team = event_team_id
                 AND prev_period = period
                 AND (shot_time - prev_time) BETWEEN 1 AND 3
                THEN 1 ELSE 0 
            END AS is_rebound,
            SQRT(POWER(x_norm - target_net_x, 2) + POWER(y_norm - 42.5, 2)) AS distance_to_net,
            DEGREES(ATAN2(ABS(y_norm - 42.5), ABS(x_norm - target_net_x))) AS shot_angle
        FROM shot_chronology
        """
        
        shots_df = self.db.query_to_df(query)
        
        if len(shots_df) == 0:
            logger.info("All shots already have xG. Skipping.")
            return 0, 0
        
        logger.info(f"Computing xG for {len(shots_df):,} shots...")
        
        # Predict in batches
        batch_size = 5000
        xg_values = []
        for i in range(0, len(shots_df), batch_size):
            batch = shots_df.iloc[i:i+batch_size]
            xg_values.extend(self.predict(batch))
        
        shots_df['xg'] = xg_values
        
        # Batch UPDATE shots (avoids giant SQL string)
        logger.info("Updating shots.xg...")
        update_batch_size = 500
        total_updated = 0
        
        for i in range(0, len(shots_df), update_batch_size):
            batch = shots_df.iloc[i:i+update_batch_size]
            
            cases = " ".join([
                f"WHEN shot_id = {row['shot_id']} THEN {row['xg']:.6f}"
                for _, row in batch.iterrows()
            ])
            ids = ",".join([str(row['shot_id']) for _, row in batch.iterrows()])
            
            self.db.execute(f"""
                UPDATE shots SET xg = CASE {cases} END
                WHERE shot_id IN ({ids})
            """)
            total_updated += len(batch)
        
        logger.info(f"Updated {total_updated:,} shots")
        
        # Aggregate to possessions
        logger.info("Aggregating xG to possessions...")
        
        updated = self.db.execute("""
            UPDATE possessions p
            SET xg_sum = (
                SELECT COALESCE(SUM(s.xg), 0)
                FROM shots s
                WHERE s.possession_id = p.possession_id
                  AND s.xg IS NOT NULL
            )
        """)
        
        logger.info(f"Updated {updated} possessions with xG sums")
        
        return total_updated, updated
    
    def save_model(self, path='models/trained/xg_model.joblib'):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({
            'model': self.model,
            'feature_names': self.feature_names,
            'training_metrics': self.training_metrics
        }, path)
        logger.info(f"Model saved to {path}")
    
    def load_model(self, path='models/trained/xg_model.joblib'):
        data = joblib.load(path)
        self.model = data['model']
        self.feature_names = data['feature_names']
        self.training_metrics = data.get('training_metrics', {})
        logger.info(f"Model loaded from {path} (AUC: {self.training_metrics.get('auc', 'N/A')})")
    
    def run(self):
        self.train()
        self.save_model()
        return self.backfill_xg()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    from db import DatabaseConnection
    db = DatabaseConnection()
    db.connect()
    try:
        xg = XGModel(db)
        n_shots, n_possessions = xg.run()
        print(f"\nDone: {n_shots:,} shots, {n_possessions:,} possessions updated")
    finally:
        db.close()
