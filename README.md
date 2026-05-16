# NHL Penalty Kill Analytics

An analytics project for studying NHL penalty-kill performance from play-by-play data.

The project currently has four main pieces:

- `NhlPkIngest`: a .NET 8 console app that ingests NHL play-by-play data into PostgreSQL.
- `Analytics`: a Python analytics layer for data validation, xG modeling, and tactical penalty-kill model experiments.
- `NhlPkApi`: an ASP.NET minimal API that serves the latest analytics model outputs to the web app.
- `Frontend`: a React + TypeScript model-story site with a visual landing page and one page per model.

For a plain-English guide to what the current models say, see `Analytics/README.md`.

For a reviewer-friendly path through the project, see `docs/demo.md`,
`docs/model_cards.md`, and `docs/validation_status.md`.

The goal is to build toward a full penalty-kill decision-support system: clean event data, reliable possession tracking, shot quality modeling, and eventually tactical breakdown analysis for entries, clears, pressure, net-front defense, and goals against.

## Repository Layout

```text
Data_ingestion/
|-- Analytics/              Python diagnostics and modeling
|-- Frontend/               React/TypeScript model-story site
|-- NhlPkApi/               ASP.NET API over analytics outputs
|-- NhlPkIngest/            .NET ingestion console app
|-- Data_ingestion.sln      Visual Studio solution
|-- README.md               Project overview
`-- .gitignore              Repo-level ignore rules
```

## Current Status

Implemented:

- PostgreSQL schema for games, teams, players, events, shots, possessions, and event-player links.
- NHL schedule and play-by-play ingestion.
- Coordinate normalization to a 200 x 85 rink.
- Strength-state parsing for 5v5, 4v5, 3v5, and related states.
- Penalty-kill possession tracking.
- Shot-to-possession linking.
- Game reprocessing support so ingestion fixes can be applied by rerunning games.
- Analytics diagnostics for coordinate quality, join inflation, possession quality, and xG data quality.
- Early xG and blue-line denial modeling code.
- API endpoints that expose the latest Models 2-10 JSON outputs to the frontend.

In progress:

- Improving possession validation after the latest strength-change boundary fix.
- Deduping player-level analytics joins before model training.
- Hardening coordinate orientation diagnostics.
- Expanding tactical sequence mining and PK breakdown modeling.

## Architecture

Data flow:

```text
NHL API
  -> NhlPkIngest
  -> PostgreSQL schema
  -> Analytics diagnostics
  -> xG / tactical models
  -> NhlPkApi
  -> Frontend model-story site
```

The ingestion app owns database population. The Python layer assumes PostgreSQL is already populated and focuses on diagnostics, modeling, and research workflows. The API currently reads the latest generated analytics JSON from `Analytics/models/output/` and shapes it for the frontend.

## Prerequisites

- .NET 8 SDK
- Python 3.10+
- Node.js 20+ for the frontend
- PostgreSQL
- Git Bash or PowerShell on Windows

The local database used by the current configuration is:

```text
Database: nhl_pk_analytics
Host: localhost
User: postgres
```

Keep real credentials in local config only. The committed template is:

```text
NhlPkIngest/appsettings.template.json
```

The Python analytics layer reads database settings from environment variables:

```powershell
$env:NHL_DB_HOST = "localhost"
$env:NHL_DB_NAME = "nhl_pk_analytics"
$env:NHL_DB_USER = "postgres"
$env:NHL_DB_PASSWORD = "your_password"
$env:NHL_DB_PORT = "5432"
```

From Git Bash:

```bash
export NHL_DB_HOST=localhost
export NHL_DB_NAME=nhl_pk_analytics
export NHL_DB_USER=postgres
export NHL_DB_PASSWORD=your_password
export NHL_DB_PORT=5432
```

## Setup

### 1. Configure The Ingestion App

From the repository root:

```powershell
Copy-Item .\NhlPkIngest\appsettings.template.json .\NhlPkIngest\appsettings.json
```

Then edit `NhlPkIngest/appsettings.json` with your local PostgreSQL password.

`appsettings.json` is intentionally ignored by Git.

### 2. Build The .NET Project

```powershell
dotnet restore .\Data_ingestion.sln
dotnet build .\Data_ingestion.sln
```

### 3. Run Ingestion

```powershell
cd .\NhlPkIngest
dotnet run
```

The configured seasons live in `appsettings.json`:

```json
"Seasons": [
  "20222023",
  "20232024",
  "20242025"
]
```

Useful ingestion setting:

```json
"SkipExistingGames": false
```

Set this to `false` when you want to reprocess games after fixing ingestion or possession logic.

### 4. Set Up Python Analytics

From the repository root:

```powershell
cd .\Analytics
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

From Git Bash, the Python executable is:

```bash
./venv/Scripts/python.exe
```

## Analytics Commands

Run these from `Analytics/`.

Join explosion diagnostic:

```bash
./venv/Scripts/python.exe -m diagnostics.join_explosion
```

Coordinate validation:

```bash
./venv/Scripts/python.exe -m diagnostics.validate_coordinates
```

Possession validation:

```bash
./venv/Scripts/python.exe -m diagnostics.validate_possessions
```

Full analytics pipeline:

```bash
./venv/Scripts/python.exe main.py
```

Generated reports and model artifacts are written to ignored local output folders such as `Analytics/runs/` and `Analytics/models/trained/`.

## Frontend Commands

Run these from `Frontend/`.

```powershell
npm install
npm run dev
npm run build
npm run lint
```

The frontend is React + TypeScript + Bootstrap. It reads the model-story payload from `http://localhost:5080/api` by default and falls back to local sample data if the API is unavailable.

## Diagnostics Notes

Recent validation results showed:

- Shot coordinates are within rink bounds.
- Shot-distance validation warns about possible fixed-net orientation assumptions; treat that as a diagnostic warning, not proof that coordinates are unusable.
- Forward forechecking joins currently inflate rows by about 3.1x, so player-level models need event-level deduping.
- Defenseman gap-control joins currently inflate rows by about 2.0x, so deduping is recommended there too.
- Shot suppression and net-front defense joins looked acceptable in the latest diagnostic run.
- Possession validation should be rerun after re-ingesting with the latest strength-change possession boundary fix.

## Database Schema

The schema is defined in:

```text
NhlPkIngest/schema.sql
```

Core tables:

- `games`
- `teams`
- `players`
- `game_players`
- `events`
- `event_players`
- `possessions`
- `shots`

The ingestion app initializes the schema automatically on startup.

## Development Notes

- Do not commit `appsettings.json`.
- Do not commit Python virtual environments, diagnostic reports, trained model files, or cache directories.
- If ingestion logic changes, reprocess games so derived tables like `possessions` and `shots` reflect the new logic.
- If analytics joins touch player-level tables, check for join inflation before trusting model results.

## Known Issues / Next Work

- Address the nullable warning in `PossessionTracker`.
- Re-ingest data after the possession-boundary fix, then rerun possession validation.
- Add event-level deduping bases for forward forechecking and defenseman gap-control models.
- Move database credentials out of Python `Analytics/config.py` before sharing beyond local development.
- Keep `docs/coordinate_conventions.md` and `Analytics/reports/latest_manpower_context.md` current after ingestion changes.
- Add tests around possession splitting, shot possession linking, and xG backfill behavior.
- Add a golden-game regression test and frontend screenshots before broad outreach.

## Roadmap

Near term:

- Stabilize ingestion and possession tracking.
- Validate PK possessions at scale.
- Harden xG training and backfill.
- Build reliable event-level tactical features.

Medium term:

- Add goal-against sequence mining.
- Cluster recurring PK breakdown patterns.
- Build model reports for entry denial, clear failures, shot suppression, and net-front defense.
- Expand the API layer beyond latest-run JSON into filterable database-backed reports.

Long term:

- Expand the web app for team, player, and tactical review.
- Support manual tactical labels from video review.
- Add richer causal and sequence modeling once the base data is stable.
