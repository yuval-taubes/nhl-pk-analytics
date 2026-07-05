"""Shared helpers for MoneyPuck v2 model output."""

from __future__ import annotations

import numpy as np


def records(df):
    """Return JSON-safe records from a pandas DataFrame."""
    if df.empty:
        return []
    clean = df.replace({np.nan: None})
    return clean.to_dict("records")


def top_records(df, sort_col, ascending=False, count=10):
    """Return the top rows from a DataFrame as JSON-safe records."""
    if df.empty or sort_col not in df.columns:
        return []
    return records(df.sort_values(sort_col, ascending=ascending).head(count))
