# NHL PK Ingest

.NET 8 console application for loading NHL play-by-play data into the penalty-kill analytics database.

This project is the data-ingestion side of the larger NHL PK Analytics repository. It is responsible for pulling games from the NHL API, normalizing event data, building penalty-kill possessions, linking shots to possessions, and keeping PostgreSQL ready for the Python analytics layer.

## Responsibilities

- Fetch NHL game IDs by season.
- Fetch play-by-play data for each game.
- Upsert teams, players, games, and game-player participation.
- Normalize rink coordinates and zones.
- Store play-by-play events.
- Store event-player relationships.
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
    "LogEveryNGames": 10
  }
}
```

Use `SkipExistingGames: false` when you need to replace game-scoped data after fixing ingestion, possession tracking, or shot-linking logic.

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

## Current Notes

- `appsettings.json` is ignored and should stay local.
- `appsettings.template.json` is committed as the safe template.
- The analytics code lives in `../Analytics`.
- After re-ingestion, run the analytics diagnostics from `Analytics/` to validate joins, coordinates, possessions, and xG readiness.
