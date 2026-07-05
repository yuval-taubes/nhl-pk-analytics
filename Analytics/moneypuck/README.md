# MoneyPuck V2 Data Layer

This folder imports local MoneyPuck CSV downloads into side-by-side `mp_*`
Postgres tables. It does not replace the original NHL API schema.

## Local Data

Set the MoneyPuck download folder before import:

```powershell
$env:MONEYPUCK_DATA_ROOT = "C:\path\to\moneypuck-data"
```

If `MONEYPUCK_DATA_ROOT` is not set, the importer looks a few levels above the
repository folder. That matches the local development layout, but setting the
environment variable is clearer and more portable.

Default local layout:

- `shots_2007-2024\shots_2007-2024.csv`
- `all_teams.csv`
- `skaters_2008_to_2024\skaters_2008_to_2024.csv`
- `goalies_2008_to_2024\goalies_2008_to_2024.csv`
- `teams_2008_to_2024\teams_2008_to_2024.csv`
- `skaters_2025\skaters_2025.csv`
- `goalies_2025\goalies_2025.csv`
- `teams_2025\teams_2025.csv`

The importer discovers the full historical shot file first. If that file is
not present, it falls back to the smaller `shots_2018-2024` file. Current-season
aggregate files are imported alongside the historical aggregate files when they
exist.

The organized local-only downloads also include:

- `skaters_2025_games\skaters_2025_games.csv`
- `goalies_2025_games\goalies_2025_games.csv`
- `lines_2025_games\lines_2025_games.csv`
- `lines_2025\lines_2025.csv`

Those game-log and line files are kept for future model work, but the current
schema does not import them yet.

For 2025-2026 shot-level work, download the MoneyPuck current-season shots CSV
and place it at:

```text
shots_2025\shots_2025.csv
```

That file is required before heat maps, PP attack profiles, PK leak profiles,
and matchup models can include 2025-2026 shot-level rows.

Optional overrides, using PowerShell path separators:

```powershell
$env:MONEYPUCK_SHOT_FILES = "D:\data\shots_2007-2024.csv;D:\data\shots_2025.csv"
$env:MONEYPUCK_SKATER_FILES = "D:\data\skaters_2008_to_2024.csv;D:\data\skaters_2025.csv"
```

MoneyPuck source and credit: https://www.moneypuck.com/data.htm

## Import

From `Analytics/`:

```powershell
$env:NHL_DB_HOST = "localhost"
$env:NHL_DB_NAME = "nhl_pk_analytics"
$env:NHL_DB_USER = "postgres"
$env:NHL_DB_PASSWORD = "your_password"
$env:NHL_DB_PORT = "5432"
.\venv\Scripts\python.exe -m moneypuck.import_moneypuck --reset
```

Use `--skip-shots` only when testing the smaller aggregate tables.

Before a long import, confirm the resolved files:

```powershell
.\venv\Scripts\python.exe -m moneypuck.import_moneypuck --describe-sources
```

The report prints the data root, every CSV that will be imported, and any
missing source group. It also prints non-fatal freshness warnings, such as
having current-season aggregate files without the current-season shot file.

Imports use primary-key upserts. If MoneyPuck republishes corrected rows, a
normal import updates matching rows instead of silently keeping stale values.

## Validate

```powershell
.\venv\Scripts\python.exe -m moneypuck.validate_moneypuck
```

The validator checks imported row counts, duplicate shot keys, top strength
states, PK shots against, and short-handed shots for.

## Table Notes

- `mp_shots` uses `(season, game_id, shot_id)` as the primary key because
  MoneyPuck `game_id` repeats across seasons.
- `shooting_team_code`, `defending_team_code`, `shooting_skaters`,
  `defending_skaters`, and `strength_state` are derived during import.
- V2 PK shots against are filtered from skater counts, not old NHL `events`.
