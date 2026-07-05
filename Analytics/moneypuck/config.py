"""Configuration for local MoneyPuck CSV ingestion."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_MONEYPUCK_ROOT = Path(__file__).resolve().parents[4]
MONEYPUCK_ROOT = Path(os.getenv("MONEYPUCK_DATA_ROOT", str(DEFAULT_MONEYPUCK_ROOT)))


def _env_paths(name: str) -> list[Path]:
    raw = os.getenv(name)
    if not raw:
        return []
    return [Path(part.strip()) for part in raw.split(os.pathsep) if part.strip()]


def _first_existing(*paths: Path) -> list[Path]:
    for path in paths:
        if path.exists():
            return [path]
    return []


def _existing(*paths: Path) -> list[Path]:
    return [path for path in paths if path.exists()]


def _configured_paths(env_name: str, defaults: list[Path]) -> list[Path]:
    return _env_paths(env_name) or defaults


_SHOT_HISTORY = _first_existing(
    MONEYPUCK_ROOT / "shots_2007-2024" / "shots_2007-2024.csv",
    MONEYPUCK_ROOT / "shots_2018-2024" / "shots_2018-2024.csv",
)

MONEYPUCK_FILE_GROUPS = {
    "shots": _configured_paths(
        "MONEYPUCK_SHOT_FILES",
        [
            *_SHOT_HISTORY,
            *_existing(
                MONEYPUCK_ROOT / "shots_2025" / "shots_2025.csv",
                MONEYPUCK_ROOT / "shots_2025.csv",
            ),
        ],
    ),
    "team_games": _configured_paths(
        "MONEYPUCK_TEAM_GAME_FILES",
        _existing(
            MONEYPUCK_ROOT / "all_teams.csv",
            MONEYPUCK_ROOT / "team_games_2025" / "team_games_2025.csv",
            MONEYPUCK_ROOT / "all_teams_2025.csv",
        ),
    ),
    "skaters": _configured_paths(
        "MONEYPUCK_SKATER_FILES",
        _existing(
            MONEYPUCK_ROOT / "skaters_2008_to_2024" / "skaters_2008_to_2024.csv",
            MONEYPUCK_ROOT / "skaters_2025" / "skaters_2025.csv",
        ),
    ),
    "goalies": _configured_paths(
        "MONEYPUCK_GOALIE_FILES",
        _existing(
            MONEYPUCK_ROOT / "goalies_2008_to_2024" / "goalies_2008_to_2024.csv",
            MONEYPUCK_ROOT / "goalies_2025" / "goalies_2025.csv",
        ),
    ),
    "teams": _configured_paths(
        "MONEYPUCK_TEAM_FILES",
        _existing(
            MONEYPUCK_ROOT / "teams_2008_to_2024" / "teams_2008_to_2024.csv",
            MONEYPUCK_ROOT / "teams_2025" / "teams_2025.csv",
        ),
    ),
}

MONEYPUCK_FILES = {name: paths[0] for name, paths in MONEYPUCK_FILE_GROUPS.items() if paths}


def validate_moneypuck_files():
    """Return missing MoneyPuck CSV paths."""
    missing = {}
    for name, paths in MONEYPUCK_FILE_GROUPS.items():
        if not paths:
            missing[name] = "no candidate files found"
            continue
        missing_paths = [str(path) for path in paths if not path.exists()]
        if missing_paths:
            missing[name] = missing_paths
    return missing


def describe_moneypuck_sources():
    """Return the resolved local MoneyPuck source files."""
    return {
        "root": str(MONEYPUCK_ROOT),
        "files": {
            name: [str(path) for path in paths]
            for name, paths in MONEYPUCK_FILE_GROUPS.items()
        },
        "missing": validate_moneypuck_files(),
        "warnings": validate_moneypuck_freshness(),
    }


def validate_moneypuck_freshness():
    """Return non-fatal warnings about stale or incomplete local sources."""
    warnings = []
    has_current_aggregate = any(
        path.exists()
        for path in (
            MONEYPUCK_ROOT / "skaters_2025" / "skaters_2025.csv",
            MONEYPUCK_ROOT / "goalies_2025" / "goalies_2025.csv",
            MONEYPUCK_ROOT / "teams_2025" / "teams_2025.csv",
        )
    )
    has_current_shots = any(
        path.exists()
        for path in (
            MONEYPUCK_ROOT / "shots_2025" / "shots_2025.csv",
            MONEYPUCK_ROOT / "shots_2025.csv",
        )
    )
    if has_current_aggregate and not has_current_shots:
        warnings.append(
            "2025 aggregate files were found, but no 2025 shot-level file was found at shots_2025\\shots_2025.csv."
        )
    return warnings
