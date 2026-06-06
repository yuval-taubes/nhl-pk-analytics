"""Derived features for MoneyPuck PK models."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


PK_SHOTS_AGAINST_WHERE = """
    shooting_skaters > defending_skaters
    AND defending_skaters IN (3, 4)
    AND shooting_skaters IN (4, 5, 6)
    AND COALESCE(shot_on_empty_net, false) = false
"""

PK_SHOTS_FOR_WHERE = """
    shooting_skaters < defending_skaters
    AND shooting_skaters IN (3, 4)
    AND defending_skaters IN (4, 5, 6)
    AND COALESCE(shot_on_empty_net, false) = false
"""


def safe_div(num, den):
    return float(num / den) if den else np.nan


def rate(num, den):
    value = safe_div(num, den)
    return None if pd.isna(value) else float(value)


def per60(value, seconds):
    return rate(float(value) * 3600, float(seconds)) if seconds else None


def pct_rank(values, higher_is_better=True):
    series = pd.Series(values).astype(float)
    ranks = series.rank(pct=True, method="average")
    if not higher_is_better:
        ranks = 1 - ranks
    return (ranks * 100).round().astype("Int64")


def money_puck_game_key(season, game_id):
    return f"{int(season)}-{int(game_id)}"


def assign_movement_bucket(row):
    """Classify the pre-shot movement that produced a PK shot against."""
    if truthy(row.get("shot_rebound")):
        return "rebound"

    x = finite(row.get("x_cord_adjusted"))
    y = finite(row.get("y_cord_adjusted"))
    last_x = finite(row.get("last_event_x_cord_adjusted"))
    last_y = finite(row.get("last_event_y_cord_adjusted"))
    dt = finite(row.get("time_since_last_event"))

    if any(v is None for v in (x, y, last_x, last_y, dt)):
        return "unknown"

    dx = x - last_x
    dy = y - last_y
    adx = abs(dx)
    ady = abs(dy)

    if dt > 8:
        return "slow_reset"
    if truthy(row.get("shot_angle_rebound_royal_road")) or (ady >= 30 and adx < 20):
        return "east_west"
    if dx >= 35 and ady < 18:
        return "north_south_downhill"
    if adx >= 25 and ady >= 20:
        return "diagonal"
    if dx <= -25 and ady < 18:
        return "point_reset_backtrack"
    return "small_area"


def add_movement_bucket(df):
    if df.empty:
        df["movement_bucket"] = []
        return df
    frame = df.copy()
    frame["movement_bucket"] = frame.apply(assign_movement_bucket, axis=1)
    return frame


def truthy(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    try:
        return float(value) == 1.0
    except (TypeError, ValueError):
        return str(value).strip().lower() in {"true", "t", "yes", "y"}


def finite(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def summarize_shots(group):
    n = len(group)
    xg = group["x_goal"].astype(float)
    return {
        "shots": int(n),
        "xg": float(xg.sum()),
        "avg_xg": rate(xg.sum(), n),
        "goals": int(group["goal"].astype(bool).sum()),
        "goal_rate": rate(group["goal"].astype(bool).sum(), n),
        "freeze_rate": rate(group["shot_goalie_froze"].astype(bool).sum(), n),
        "rebound_generated_rate": rate(group["shot_generated_rebound"].astype(bool).sum(), n),
        "continued_in_zone_rate": rate(group["shot_play_continued_in_zone"].astype(bool).sum(), n),
        "continued_outside_zone_rate": rate(group["shot_play_continued_outside_zone"].astype(bool).sum(), n),
        "royal_road_rate": rate(group["shot_angle_rebound_royal_road"].astype(bool).sum(), n),
    }
