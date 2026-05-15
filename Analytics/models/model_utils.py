"""Shared helpers for analytics models 2-10."""

from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal

import numpy as np
import pandas as pd


OUTPUT_DIR = os.path.join("models", "output")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def json_safe(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def export_json(payload, filename):
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(json_safe(payload), f, indent=2)
    return path


def add_timestamp(payload):
    payload["computed_at"] = datetime.now().isoformat()
    return payload


def percentile_rank(series, higher_is_better=True):
    values = pd.Series(series).astype(float)
    if values.empty:
        return values
    ranks = values.rank(pct=True, method="average")
    if not higher_is_better:
        ranks = 1 - ranks
    return (ranks * 100).round().astype(int)


def bootstrap_ci_by_game(data, game_col, metric_func, n_bootstrap=500, ci=95, random_state=42):
    if data.empty or game_col not in data.columns:
        return {"value": None, "ci_lower": None, "ci_upper": None, "n_bootstrap": 0}

    games = data[game_col].dropna().unique()
    if len(games) == 0:
        return {"value": None, "ci_lower": None, "ci_upper": None, "n_bootstrap": 0}

    rng = np.random.RandomState(random_state)
    game_data = {g: data[data[game_col] == g] for g in games}
    stats = []

    for _ in range(n_bootstrap):
        sampled = rng.choice(games, size=len(games), replace=True)
        sample = pd.concat([game_data[g] for g in sampled], ignore_index=True)
        try:
            stat = float(metric_func(sample))
            if np.isfinite(stat):
                stats.append(stat)
        except Exception:
            continue

    value = metric_func(data)
    if not stats:
        return {"value": float(value), "ci_lower": None, "ci_upper": None, "n_bootstrap": 0}

    lower = (100 - ci) / 2
    upper = 100 - lower
    return {
        "value": float(value),
        "ci_lower": float(np.percentile(stats, lower)),
        "ci_upper": float(np.percentile(stats, upper)),
        "n_bootstrap": len(stats),
    }


def ensure_player_scouting_table(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS player_scouting (
            scout_id SERIAL PRIMARY KEY,
            player_id INTEGER REFERENCES players(player_id),
            season VARCHAR(8),
            model_name VARCHAR(50),
            metric_name VARCHAR(50),
            metric_value NUMERIC(8,4),
            percentile INTEGER,
            sample_size INTEGER,
            computed_at TIMESTAMP DEFAULT NOW()
        )
        """
    )


def replace_player_scouting_rows(db, model_name, rows):
    ensure_player_scouting_table(db)
    db.execute("DELETE FROM player_scouting WHERE model_name = %s", (model_name,))

    insert_sql = """
        INSERT INTO player_scouting
            (player_id, season, model_name, metric_name, metric_value, percentile, sample_size)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    for row in rows:
        db.execute(
            insert_sql,
            (
                int(row["player_id"]),
                row.get("season"),
                model_name,
                row["metric_name"],
                float(row["metric_value"]) if row["metric_value"] is not None else None,
                int(row["percentile"]) if row.get("percentile") is not None else None,
                int(row["sample_size"]) if row.get("sample_size") is not None else 0,
            ),
        )


def first_existing_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None
