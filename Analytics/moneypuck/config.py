"""Configuration for local MoneyPuck CSV ingestion."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_MONEYPUCK_ROOT = Path(__file__).resolve().parents[4]
MONEYPUCK_ROOT = Path(os.getenv("MONEYPUCK_DATA_ROOT", str(DEFAULT_MONEYPUCK_ROOT)))

MONEYPUCK_FILES = {
    "shots": MONEYPUCK_ROOT / "shots_2018-2024" / "shots_2018-2024.csv",
    "team_games": MONEYPUCK_ROOT / "all_teams.csv",
    "skaters": MONEYPUCK_ROOT / "skaters_2008_to_2024" / "skaters_2008_to_2024.csv",
    "goalies": MONEYPUCK_ROOT / "goalies_2008_to_2024" / "goalies_2008_to_2024.csv",
    "teams": MONEYPUCK_ROOT / "teams_2008_to_2024" / "teams_2008_to_2024.csv",
}


def validate_moneypuck_files():
    """Return missing MoneyPuck CSV paths."""
    return {name: str(path) for name, path in MONEYPUCK_FILES.items() if not path.exists()}
