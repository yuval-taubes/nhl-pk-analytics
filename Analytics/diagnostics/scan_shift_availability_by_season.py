"""Stratified NHL shiftchart availability scan by season.

The sample is spread evenly from the start to the end of each ingested season
so endpoint coverage is not inferred from one late-season game range.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from diagnostics.scan_shift_availability import markdown_table, persist_results, scan_games


REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORT_PATH = REPORT_DIR / "latest_shift_availability_by_season.md"
CSV_PATH = REPORT_DIR / "latest_shift_availability_by_season.csv"


def evenly_spaced_indices(size, sample_size):
    if sample_size <= 0 or size <= 0:
        return []
    if sample_size >= size:
        return list(range(size))
    if sample_size == 1:
        return [size // 2]
    return sorted({round(index * (size - 1) / (sample_size - 1)) for index in range(sample_size)})


def select_games_by_season(db, games_per_season):
    games = db.query_to_df(
        """
        SELECT game_id, season, game_date
        FROM games
        WHERE season IS NOT NULL
        ORDER BY season, game_date, game_id
        """
    )
    selected = []
    for season, season_games in games.groupby("season", sort=True):
        records = season_games.to_dict("records")
        for index in evenly_spaced_indices(len(records), games_per_season):
            row = records[index]
            selected.append({"game_id": int(row["game_id"]), "season": str(season)})
    return selected


def summarize(rows):
    seasons = sorted({row["season"] for row in rows})
    summary = []
    for season in seasons:
        season_rows = [row for row in rows if row["season"] == season]
        requested = len(season_rows)
        available = sum(row["status"] == "covered" for row in season_rows)
        missing = sum(row["status"] == "missing" for row in season_rows)
        errors = sum(row["status"] == "error" for row in season_rows)
        summary.append(
            {
                "season": season,
                "requested": requested,
                "available": available,
                "missing": missing,
                "errors": errors,
                "coverage_rate": f"{available / requested:.1%}" if requested else "0.0%",
            }
        )
    return summary


def write_report(rows):
    import pandas as pd

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(CSV_PATH, index=False)
    summary = summarize(rows)
    exceptions = [row for row in rows if row["status"] != "covered"]
    report = [
        "# Shiftchart Availability By Season",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        markdown_table(summary, ["season", "requested", "available", "missing", "errors", "coverage_rate"]),
        "",
        "## Missing Or Error Games",
        "",
        markdown_table(exceptions, ["season", "game_id", "status", "shift_rows", "error"]),
        "",
        "## Interpretation",
        "",
        "Games are sampled at evenly spaced positions from the start through the end of each ingested season. "
        "This is a stratified availability diagnostic, not a complete census. Persisted results are valid per-game evidence only; unsampled games remain `not_checked`.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Scan shiftchart availability across ingested seasons.")
    parser.add_argument("--games-per-season", type=int, default=20)
    parser.add_argument("--delay-seconds", type=float, default=0.1)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    from db import DatabaseConnection

    db = DatabaseConnection()
    db.connect()
    try:
        selected = select_games_by_season(db, args.games_per_season)
        scan_rows = scan_games([row["game_id"] for row in selected], args.delay_seconds, args.timeout_seconds)
        season_by_game = {row["game_id"]: row["season"] for row in selected}
        rows = [{**row, "season": season_by_game[row["game_id"]]} for row in scan_rows]
        if args.persist:
            persist_results(db, rows)
    finally:
        db.close()

    summary = write_report(rows)
    print(f"Scanned {len(rows)} games across {len(summary)} seasons")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {CSV_PATH}")
    if any(row["errors"] for row in summary):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
