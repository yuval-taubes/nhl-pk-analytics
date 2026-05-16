"""Model 5: PK defensive-zone faceoff play selection."""

import logging
from types import SimpleNamespace

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from db import DatabaseConnection
from models.model_utils import add_timestamp, bootstrap_ci_by_game, export_json

logger = logging.getLogger(__name__)


class PkFaceoffModel:
    """Matched comparison of PK DZ faceoff wins versus losses."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.data = None
        self.estimate = None
        self.bootstrap_result = None

    def fetch_data(self):
        query = """
        WITH faceoffs AS (
            SELECT
                e.event_id,
                e.game_id,
                e.event_idx,
                e.period,
                e.period_time_seconds,
                e.event_team_id AS faceoff_winner_team_id,
                e.x_norm,
                e.y_norm,
                e.strength,
                g.home_team_id,
                g.away_team_id,
                g.home_score,
                g.away_score,
                CASE
                    WHEN split_part(e.strength, 'v', 1)::int < split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(e.strength, 'v', 2)::int < split_part(e.strength, 'v', 1)::int THEN g.home_team_id
                END AS pk_team_id,
                CASE
                    WHEN split_part(e.strength, 'v', 1)::int > split_part(e.strength, 'v', 2)::int THEN g.away_team_id
                    WHEN split_part(e.strength, 'v', 2)::int > split_part(e.strength, 'v', 1)::int THEN g.home_team_id
                END AS pp_team_id
            FROM events e
            JOIN games g ON e.game_id = g.game_id
            WHERE e.event_type = 'faceoff'
              AND e.zone = 'DZ'
              AND e.strength IN ('4v5', '3v5', '3v4', '5v4', '5v3', '4v3')
        ),
        outcomes AS (
            SELECT
                f.*,
                CASE WHEN f.faceoff_winner_team_id = f.pk_team_id THEN 1 ELSE 0 END AS treatment,
                CASE
                    WHEN f.y_norm < 37 THEN 'left'
                    WHEN f.y_norm > 48 THEN 'right'
                    ELSE 'center_unknown'
                END AS circle_side,
                CASE
                    WHEN f.pk_team_id = f.home_team_id THEN f.home_score - f.away_score
                    ELSE f.away_score - f.home_score
                END AS pk_score_diff,
                COALESCE(SUM(s.xg), 0) AS xga_20,
                COUNT(s.shot_id) AS shots_against_20
            FROM faceoffs f
            LEFT JOIN events se
              ON se.game_id = f.game_id
             AND se.period = f.period
             AND se.event_team_id = f.pp_team_id
             AND se.period_time_seconds BETWEEN f.period_time_seconds AND f.period_time_seconds + 20
            LEFT JOIN shots s ON s.event_id = se.event_id
            GROUP BY
                f.event_id, f.game_id, f.event_idx, f.period, f.period_time_seconds,
                f.faceoff_winner_team_id, f.x_norm, f.y_norm, f.strength,
                f.home_team_id, f.away_team_id, f.home_score, f.away_score,
                f.pk_team_id, f.pp_team_id
        )
        SELECT * FROM outcomes
        """
        logger.info("Fetching PK DZ faceoff data...")
        self.data = self.db.query_to_df(query)
        logger.info("Model 5 sample: %s PK DZ faceoffs", len(self.data))
        return self.data

    def _prepare_frame(self, data):
        frame = data.copy()
        frame["xga_20"] = frame["xga_20"].fillna(0).astype(float)
        frame["pk_score_diff"] = frame["pk_score_diff"].fillna(0).astype(float)
        frame["period"] = frame["period"].fillna(0).astype(int)
        frame["game_seconds"] = (frame["period"] - 1) * 1200 + frame["period_time_seconds"].astype(float)
        frame = pd.get_dummies(frame, columns=["strength", "circle_side"], dtype=int, dummy_na=True)
        causes = ["pk_score_diff", "period", "game_seconds"]
        causes.extend([c for c in frame.columns if c.startswith("strength_") or c.startswith("circle_side_")])
        return frame, causes

    def _estimate_att(self, data):
        frame, causes = self._prepare_frame(data)
        treated = frame[frame["treatment"] == 1]
        controls = frame[frame["treatment"] == 0]
        if treated.empty or controls.empty:
            return np.nan
        X = frame[causes].astype(float)
        y = frame["treatment"].astype(int)
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=42))
        model.fit(X, y)
        frame = frame.copy()
        frame["propensity"] = model.predict_proba(X)[:, 1]
        treated = frame[frame["treatment"] == 1].reset_index(drop=True)
        controls = frame[frame["treatment"] == 0].reset_index(drop=True)
        nn = NearestNeighbors(n_neighbors=1)
        nn.fit(controls[["propensity"]])
        _, idx = nn.kneighbors(treated[["propensity"]])
        matched = controls.iloc[idx.flatten()].reset_index(drop=True)
        return float(treated["xga_20"].mean() - matched["xga_20"].mean())

    def run(self):
        logger.info("=" * 60)
        logger.info("MODEL 5: PK Faceoff Play Selection")
        logger.info("=" * 60)
        data = self.fetch_data()

        att = self._estimate_att(data)
        self.estimate = SimpleNamespace(value=att)

        def simple_win_loss_diff(df):
            wins = df[df["treatment"] == 1]["xga_20"].astype(float)
            losses = df[df["treatment"] == 0]["xga_20"].astype(float)
            if wins.empty or losses.empty:
                return np.nan
            return wins.mean() - losses.mean()

        self.bootstrap_result = bootstrap_ci_by_game(data, "game_id", simple_win_loss_diff, n_bootstrap=200)

        outcome_rows = []
        for outcome, group in data.assign(outcome=lambda x: np.where(x["treatment"] == 1, "WIN", "LOSS")).groupby("outcome"):
            outcome_rows.append(
                {
                    "outcome": outcome,
                    "n": int(len(group)),
                    "avg_xga_20": float(group["xga_20"].astype(float).mean()),
                    "shot_rate_20": float((group["shots_against_20"].astype(float) > 0).mean()),
                }
            )

        side_rows = []
        for keys, group in data.groupby(["circle_side", "treatment"]):
            side, treatment = keys
            side_rows.append(
                {
                    "circle_side": side,
                    "outcome": "WIN" if treatment == 1 else "LOSS",
                    "n": int(len(group)),
                    "avg_xga_20": float(group["xga_20"].astype(float).mean()),
                }
            )

        results = add_timestamp(
            {
                "model": "PK Faceoff Play Selection",
                "estimated_effect": {
                    "att_win_vs_loss_xga_20": float(att) if np.isfinite(att) else None,
                    "ci": self.bootstrap_result,
                    "interpretation": (
                        f"PK faceoff wins were associated with {att:.4f} xGA in the next 20 seconds "
                        "relative to matched losses."
                    )
                    if np.isfinite(att)
                    else "Insufficient overlap for matched faceoff estimate.",
                },
                "outcome_summary": outcome_rows,
                "circle_side_summary": side_rows,
                "sample": {"n_faceoffs": int(len(data))},
                "caveats": [
                    "Faceoff winner is inferred from event_team_id on the faceoff event",
                    "DoWhy is not used because the installed networkx/DoWhy versions are incompatible; this uses matched propensity scores",
                    "DZ faceoff circle side is approximated from y_norm",
                    "Handedness data is unavailable from the NHL API",
                    "This is the only tactical model here framed as a matched treatment comparison",
                ],
            }
        )
        results["output_file"] = export_json(results, "model5_pk_faceoff.json")
        logger.info("Model 5 output: %s", results["output_file"])
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    db = DatabaseConnection()
    db.connect()
    try:
        PkFaceoffModel(db).run()
    finally:
        db.close()
