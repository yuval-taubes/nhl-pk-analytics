# NHL PK Ingest

.NET console ingestion pipeline for the NHL penalty-kill analytics project.

This app pulls NHL play-by-play data, normalizes events into a PostgreSQL schema, tracks penalty-kill possessions, links shots back to possessions, and prepares the database for the Python analytics layer.

## Project Status

- PostgreSQL schema: implemented
- NHL schedule and play-by-play ingestion: implemented
- Coordinate normalization: implemented
- PK possession tracking: implemented, with strength-change possession boundaries
- Shot-to-possession linking: implemented
- Analytics diagnostics: lives in the sibling `Analytics/` folder for now

## Local Setup

Prerequisites:

- .NET 8 SDK
- PostgreSQL
- Python 3.10+ for the analytics project

From this folder:

```powershell
dotnet restore
dotnet build
dotnet run
```

The ingestion app reads database settings from `appsettings.json`. Use [appsettings.template.json](appsettings.template.json) as the safe starting point for local configuration.

## Database

The schema is maintained in [schema.sql](schema.sql). Re-running ingestion for an already-ingested game replaces that game's dependent rows so possession and shot-linking fixes can be applied by reprocessing games.

## Important Notes

The Git repository is currently rooted in this `NhlPkIngest/` folder, while the analytics code is one directory above it at `../Analytics/`. Git cannot track files outside its working tree, so `Analytics/` will not be included until the repository root is moved up to `Data_ingestion/` or the analytics folder is moved inside this repo.

Recommended final layout:

```text
Data_ingestion/
├── Analytics/
├── NhlPkIngest/
├── Data_ingestion.sln
├── README.md
└── .gitignore
```

## Diagnostics

After ingestion, run the analytics diagnostics from the sibling `Analytics/` directory:

```bash
cd "/d/Hockey-data project/Code/Data_ingestion/Analytics"
./venv/Scripts/python.exe -m diagnostics.join_explosion
./venv/Scripts/python.exe -m diagnostics.validate_coordinates
./venv/Scripts/python.exe -m diagnostics.validate_possessions
```

Current known diagnostic priorities:

- Forward forechecking player-level joins need deduping before modeling.
- Defenseman gap-control joins should use a deduped event-level base.
- Possession validation should be rerun after re-ingesting with the latest strength-change boundary fix.
