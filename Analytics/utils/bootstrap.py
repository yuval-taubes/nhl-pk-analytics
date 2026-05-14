"""
Clustered bootstrap helpers.

The game-level bootstrap resamples games with replacement and preserves
multiplicity. This is important because possessions within the same game are
not independent.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def cluster_bootstrap_by_game(
    data,
    game_id_column,
    statistic_func,
    n_bootstrap=1000,
    ci=95,
    random_state=42
):
    rng = np.random.RandomState(random_state)
    games = data[game_id_column].unique()
    n_games = len(games)

    if n_games == 0:
        raise ValueError("Cannot bootstrap: no games in input data")

    if n_games < 30:
        logger.warning(f"Only {n_games} games - CIs will be wide")

    game_data = {g: data[data[game_id_column] == g].copy() for g in games}

    stats = []
    nan_count = 0

    for _ in range(n_bootstrap):
        sampled_games = rng.choice(games, size=n_games, replace=True)
        sample_df = pd.concat([game_data[g] for g in sampled_games], ignore_index=True)

        try:
            stat = float(statistic_func(sample_df))
            if np.isfinite(stat):
                stats.append(stat)
            else:
                nan_count += 1
        except Exception:
            nan_count += 1

    if nan_count > n_bootstrap * 0.1:
        logger.warning(f"{nan_count}/{n_bootstrap} bootstrap iterations failed")

    if not stats:
        raise RuntimeError(
            "All bootstrap iterations failed. Check sample size, treatment/control "
            "overlap, and model convergence."
        )

    lower = (100 - ci) / 2
    upper = 100 - lower

    return {
        'value': float(statistic_func(data)),
        'ci_lower': float(np.percentile(stats, lower)),
        'ci_upper': float(np.percentile(stats, upper)),
        'n_games': int(n_games),
        'n_bootstrap': int(len(stats)),
        'n_failed': int(nan_count)
    }
