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

Expected files:

- `shots_2018-2024\shots_2018-2024.csv`
- `all_teams.csv`
- `skaters_2008_to_2024\skaters_2008_to_2024.csv`
- `goalies_2008_to_2024\goalies_2008_to_2024.csv`
- `teams_2008_to_2024\teams_2008_to_2024.csv`

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
