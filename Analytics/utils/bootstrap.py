"""
Clustered bootstrap with game-level resampling.
CRITICAL: Resamples games WITH replacement INCLUDING multiplicity.
"""

import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def cluster_bootstrap_by_game(data, game_id_column, statistic_func, 
                               n_bootstrap=1000, ci=95, random_state=42):
    
    rng = np.random.RandomState(random_state)
    games = data[game_id_column].unique()
    n_games = len(games)
    
    if n_games < 30:
        logger.warning(f"Only {n_games} games — CIs will be wide")
    
    # Pre-split by game
    game_data = {}
    for g in games:
        game_data[g] = data[data[game_id_column] == g].copy()
    
    stats = []
    nan_count = 0
    
    for i in range(n_bootstrap):
        sampled = rng.choice(games, size=n_games, replace=True)
        
        # Build sample WITH multiplicity (the fix)
        frames = [game_data[g] for g in sampled]
        sample_df = pd.concat(frames, ignore_index=True)
        
        try:
            s = statistic_func(sample_df)
            if not np.isnan(s):
                stats.append(s)
            else:
                nan_count += 1
        except Exception:
            nan_count += 1
    
    if nan_count > n_bootstrap * 0.1:
        logger.warning(f"{nan_count}/{n_bootstrap} iterations failed")
    
    lower = (100 - ci) / 2
    upper = 100 - lower
    
    return {
        'value': statistic_func(data),
        'ci_lower': np.percentile(stats, lower),
        'ci_upper': np.percentile(stats, upper),
        'n_games': n_games,
        'n_bootstrap': len(stats)
    }