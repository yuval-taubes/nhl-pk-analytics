# NHL PK Ingest

.NET 8 console application for loading NHL play-by-play data into the penalty-kill analytics database.

This project is the data-ingestion side of the larger NHL PK Analytics repository. It is responsible for pulling games from the NHL API, normalizing event data, building penalty-kill possessions, linking shots to possessions, and keeping PostgreSQL ready for the Python analytics layer.

## Responsibilities

- Fetch NHL game IDs by season.
- Fetch play-by-play data for each game.
- Fetch NHL shiftcharts for full on-ice reconstruction.
- Upsert teams, players, games, and game-player participation.
- Normalize rink coordinates and zones.
- Store play-by-play events.
- Store event-player relationships.
- Store raw shift segments, shift-derived on-ice players, and manpower validation rows.
- Track penalty-kill possessions.
- Link shots to possessions.
- Reprocess already-ingested games when ingestion logic changes.

## Setup

From the repository root:

```powershell
Copy-Item .\NhlPkIngest\appsettings.template.json .\NhlPkIngest\appsettings.json
```

Edit `appsettings.json` with your local PostgreSQL connection string.

Then build:

```powershell
dotnet build .\Data_ingestion.sln
```

Run ingestion:

```powershell
cd .\NhlPkIngest
dotnet run
```

## Configuration

Important settings in `appsettings.json`:

```json
{
  "Seasons": [
    "20222023",
    "20232024",
    "20242025"
  ],
  "Ingest": {
    "BatchSize": 10000,
    "SkipExistingGames": false,
    "LogEveryNGames": 10,
    "SingleGameId": null,
    "GameIds": null,
    "SkipSchemaInitialization": false
  }
}
```

Use `SkipExistingGames: false` when you need to replace game-scoped data after fixing ingestion, possession tracking, shot-linking logic, or shift/on-ice derivation.

Use `SingleGameId` for targeted validation without scanning full season schedules:

```powershell
cd .\NhlPkIngest
dotnet run -- --Ingest:SingleGameId=2023020201 --Ingest:SkipExistingGames=false
```

Use `GameIds` for a focused batch reprocess. It accepts comma-, semicolon-, or space-separated game IDs and takes precedence over `SingleGameId`:

```powershell
cd .\NhlPkIngest
dotnet run -- --Ingest:GameIds=2024021312,2024021311,2024021310 --Ingest:SkipExistingGames=false
```

Use `SkipSchemaInitialization: true` only when the schema is already current and you want a faster reprocess run. This avoids startup DDL and is useful for validator batches.

## Database

The schema lives in:

```text
schema.sql
```

The app initializes the schema at startup. Game reprocessing deletes and replaces dependent rows for that game so fixes can flow through to:

- events
- event players
- possessions
- shots
- game_shifts
- event_on_ice_players
- event_manpower

## Shift/On-Ice First Pass

The first shiftcharts pass uses `https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={gameId}` as an additive source beside play-by-play. It writes:

- `game_shifts`: raw player shift segments from NHL shiftcharts.
- `event_on_ice_players`: shift-derived players active at each play-by-play event timestamp.
- `event_manpower`: shift-derived skater counts, goalie IDs, goalie-pulled flags, event-team-relative strength code, and comparison to parsed `situationCode` skater counts.

Full validation covers all `3,936` ingested games. The `3,879` games with NHL shift rows contain `2,931,003` accepted raw shifts, `14,190,396` event on-ice rows, and full manpower coverage for `1,224,084/1,224,084` events. The all-event manpower mismatch rate is `4.85%`, driven mostly by penalty timing, period/game-end rows, stoppages, goals, and goalie-pulled bookkeeping. The model-safe event gate passes at `1.05%` mismatches across shots, faceoffs, hits, giveaways, and takeaways.

A full endpoint census mapped one source-coverage boundary: games `2024021235-2024021291` return zero rows directly from `api.nhle.com`; every other ingested game returned shifts. The ingester skips event on-ice/manpower derivation when a game has no shiftchart rows, so missing source data stays visible instead of creating false zero-skater manpower rows.

After reprocessing shift data, run:

```powershell
$env:NHL_DB_PASSWORD = "<local password>"
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\scan_shift_availability.py --game-limit 50
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\validate_shift_and_moneypuck_alignment.py --game-limit 50
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\shift_pk_exposure.py --game-limit 50
```

The generated reports in `Analytics/reports/` are the source of truth for whether the source-covered batch is trusted enough for model work. `latest_shift_pk_exposure.md` is the first descriptive PK exposure report from shift-covered rows; it keeps goal exposures separate from shift-age fatigue buckets because scoring timestamps can split NHL shiftchart segments and reset goal-event shift age.

Shift source state is persisted in `game_shift_source_status`. Each game is one of `available`, `missing_empty_response`, `request_error`, or `not_checked`, with the endpoint, check time, row count, HTTP status when known, and error text. Empty successful responses and failed requests are intentionally different states. Re-ingestion fails closed on request errors and preserves last-known-good shifts when the source unexpectedly returns no rows. `pk_shift_player_event_features` is the reusable source-covered view for player/event modeling; it includes shift duration, shift age, rest before shift, PK state, and source provenance. Its rest value is a game-clock shift gap, not wall-clock recovery, so intermission duration is excluded.

Apply the additive schema and conservative historical backfill with:

```powershell
$env:NHL_DB_PASSWORD='YOUR_PASSWORD'
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\migrate_shift_source_status.py
```

The migration marks games with stored shift rows as `available` and all other historical games as `not_checked`. It never infers that an unchecked game is missing. Verify and persist a current sample with:

```powershell
$env:NHL_DB_PASSWORD='YOUR_PASSWORD'
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\scan_shift_availability.py --game-limit 50 --persist
```

For a full resumable census, use `--not-checked --persist --persist-batch-size 25`. Results commit after every batch, so rerunning the same command resumes from the remaining unchecked games. Use `--retry-errors` in a separate pass so transient request failures are never confused with successful empty responses. The 2026-07-13 completed census found shift rows for `3,879/3,936` games (`98.55%`), with the remaining 57 games all in the known `2024021235-2024021291` zero-row block and no request errors.

The source-certified backfill completed for all `3,879` available games. Structural validation found `1,224,084/1,224,084` covered-game events with manpower rows and a `1.05%` model-safe mismatch rate. Shift DTO identifiers accept source `null` values as zero so malformed rows can be filtered without discarding an otherwise valid game; game `2022020160` exercised this case. `migrate_shift_source_status.py --audit-only` is genuinely read-only and should be used for progress/final summaries without taking schema locks.

The season-stratified scan indicates the endpoint is broadly populated: sampled coverage was `100%`, `100%`, and `95%` across the three ingested seasons. The major verified exception is a contiguous 2024-25 source gap from game `2024021235` through `2024021291`. Keep those games in the play-by-play and MoneyPuck lanes, but exclude them from shift-derived TOI, on-ice, rest, and fatigue features.

After persisting scanner evidence, ingest only verified available games that do not yet have shift rows:

```powershell
dotnet run --project .\NhlPkIngest\NhlPkIngest.csproj -- `
  --Ingest:ShiftSourceAvailableOnly=true `
  --Ingest:SkipExistingGames=false `
  --Ingest:SkipSchemaInitialization=true
```

This mode never retries games marked empty, errored, or not checked. Reprocessing replaces all game-scoped NHL rows transactionally, including events and possessions, so run the normal validation suite afterward.

The `possessions` table remains a selected offensive-zone sequence table, not a complete puck-control timeline. Across the full shift-covered database it overlaps only `14.04%` of PK team-events. Do not use possession membership as a universal adjustment variable without reporting that selection boundary.
## Current Notes

- `appsettings.json` is ignored and should stay local.
- `appsettings.template.json` is committed as the safe template.
- The analytics code lives in `../Analytics`.
- After re-ingestion, run the analytics diagnostics from `Analytics/` to validate joins, coordinates, possessions, and xG readiness.
