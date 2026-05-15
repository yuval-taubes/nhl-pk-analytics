"""Shared player-scouting helpers for Models 6-10."""

import logging

import numpy as np
import pandas as pd

from models.model_utils import bootstrap_ci_by_game, percentile_rank, replace_player_scouting_rows

logger = logging.getLogger(__name__)


def metric_ci(data, metric_func):
    return bootstrap_ci_by_game(data, "game_id", metric_func, n_bootstrap=500)


def build_metric_rows(summary, model_name, season, metric_configs):
    rows = []
    for metric_name, higher_is_better, sample_col in metric_configs:
        percentile_col = f"{metric_name}_percentile"
        summary[percentile_col] = percentile_rank(summary[metric_name], higher_is_better=higher_is_better)
        for _, row in summary.iterrows():
            rows.append(
                {
                    "player_id": int(row["player_id"]),
                    "season": season,
                    "metric_name": metric_name,
                    "metric_value": float(row[metric_name]) if pd.notna(row[metric_name]) else None,
                    "percentile": int(row[percentile_col]) if pd.notna(row[percentile_col]) else None,
                    "sample_size": int(row[sample_col]),
                }
            )
    return rows


def export_scouting(db, model_name, summary, season, metric_configs):
    rows = build_metric_rows(summary.copy(), model_name, season, metric_configs)
    replace_player_scouting_rows(db, model_name, rows)
    logger.info("Exported %s scouting metric rows for %s", len(rows), model_name)
    return rows


def safe_div(num, den):
    return float(num / den) if den else np.nan
