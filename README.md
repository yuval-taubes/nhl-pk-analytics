# NHL Penalty Kill Analytics

An end-to-end NHL penalty-kill analytics system: .NET ingestion, PostgreSQL
storage, Python modeling, an ASP.NET API, and a React site built for readable
hockey answers.

**Live frontend:** https://yuval-taubes.github.io/nhl-pk-analytics/

The current 2.0 version combines NHL play-by-play, NHL shiftcharts, and
MoneyPuck shot quality. It focuses on why penalty kills break down: puck
movement before the shot, rebounds, failed recoveries after blocks, goalie
control, sustained pressure as shifts age, and season-by-season player profiles.
The preview site centers that work in a Special Teams Scouting Lab: PP attack
tendencies, PK leak profiles, a tactical matchup board, generated scouting
briefs, and player passports with explicit sample and trust caveats.

## What This Demonstrates

- Ingesting public NHL play-by-play with a .NET pipeline.
- Reconstructing player shifts, event-level on-ice personnel, goalie state, and manpower from NHL shiftcharts.
- Designing a PostgreSQL schema for games, events, shots, possessions, and players.
- Validating coordinate, manpower, source coverage, possession, and join assumptions against independent evidence.
- Producing descriptive penalty-kill model outputs in Python.
- Importing MoneyPuck CSV data for richer v2 shot-quality and scouting models.
- Serving model outputs through an ASP.NET API.
- Publishing an interactive React frontend with a committed real-data snapshot.

The frontend does not use Bootstrap. Responsive behavior is handled in the app's
CSS breakpoints so the MoneyPuck v2 cards can stay custom, visual, and compact.

The project has four main pieces:

- `NhlPkIngest`: a .NET 8 console app that ingests NHL play-by-play data into PostgreSQL.
- `Analytics`: a Python analytics layer for data validation, xG modeling, and tactical penalty-kill model experiments.
- `NhlPkApi`: an ASP.NET minimal API that serves the latest analytics model outputs to the web app.
- `Frontend`: a React + TypeScript site for model explanations and scouting views.

For a plain-English guide to what the current models say, see `Analytics/README.md`.

For a reviewer-friendly path through the project, see `docs/demo.md`,
`docs/model_cards.md`, `docs/validation_status.md`, and
`docs/moneypuck_v2_architecture.md`.

The goal is not to claim every hockey question is solved. It is to make the
pipeline, strongest findings, and trust boundaries easy to inspect.

## Validated Data Foundation

The current PostgreSQL build contains `3,936` NHL games from 2022-23 through
2024-25. Every game has play-by-play. The NHL shiftcharts endpoint provides
usable shift rows for `3,879` games (`98.55%`), and all `3,879` have been
backfilled into raw shifts, event-level on-ice players, and derived manpower.
The remaining 57 games form one verified contiguous source gap,
`2024021235-2024021291`; they remain available for play-by-play and MoneyPuck
analysis but are excluded from shift-derived claims.

Current trust checks:

- `1,224,084/1,224,084` events in source-covered games have derived manpower rows.
- Model-safe shift-derived manpower disagrees with NHL play-by-play skater counts on `1.05%` of events.
- `340,834/342,924` eligible NHL shots match MoneyPuck by game, period, team, and time (`99.39%`).
- Coordinate magnitudes agree tightly across NHL and MoneyPuck; signed rink direction remains an explicit modeling convention.
- The PK shift feature layer contains `802,175` player-event rows across `3,878` games and `1,138` players.

The full adjusted pressure diagnostic uses `186,951` PK event states across
`3,878` games. Estimated probability of the opponent recording the next shot
attempt within ten seconds rises from `15.88%` for a 0-29 second oldest active
PK shift to `17.26%`, `18.80%`, and `20.18%` in the 30-44, 45-59, and 60+
second buckets. This is a stable adjusted association, not a causal fatigue
claim: positioning, deployment intent, substitutions between events, and exact
possession remain unobserved.

See `docs/validation_status.md` for the trust ledger and
`Analytics/reports/latest_shift_on_ice_validation.md` for the all-game report.

## Repository Layout

```text
Data_ingestion/
|-- Analytics/              Python diagnostics and modeling
|-- Frontend/               React/TypeScript analytics site
|-- NhlPkApi/               ASP.NET API over analytics outputs
|-- NhlPkIngest/            .NET ingestion console app
|-- Data_ingestion.sln      Visual Studio solution
|-- README.md               Project overview
`-- .gitignore              Repo-level ignore rules
```

## 2.0 Status

Implemented:

- PostgreSQL schema for games, teams, players, events, shots, possessions, and event-player links.
- NHL schedule and play-by-play ingestion.
- NHL shiftchart ingestion with source-state auditing and resumable certified-source backfill.
- Event-level on-ice reconstruction, goalie state, and manpower comparison against play-by-play.
- Coordinate normalization to a 200 x 85 rink.
- Strength-state parsing for 5v5, 4v5, 3v5, and related states.
- Penalty-kill possession tracking.
- Shot-to-possession linking.
- Game reprocessing support so ingestion fixes can be applied by rerunning games.
- Analytics diagnostics for coordinate quality, join inflation, possession quality, and xG data quality.
- Early xG and blue-line denial modeling code.
- API endpoints that expose the latest legacy and MoneyPuck v2 outputs.
- MoneyPuck v2 model runner with puck-movement, goalie-control, fatigue,
  after-block, rush/set, empirical-Bayes player impact, and similar-player
  scouting outputs.
- Special-teams matchup model with PP attack profiles, PK leak profiles,
  matchup cards, and compact rink heat-map bins.
- React scouting workflow for selected PP-vs-PK matchups, generated scouting
  briefs, dynamic player passports, and secondary player/goalie discovery. The
  first-pass workflow now includes a compact current-read strip, actionable
  matchup example cards, and repo-local Playwright smoke QA.
- GitHub Actions CI for .NET, frontend, and Python compile checks.
- GitHub Pages deployment for the interactive frontend.
- Static real-data frontend snapshot at `Frontend/public/data/dashboard.json`.
  The export script writes the trimmed MoneyPuck v2 dashboard and refuses
  snapshots over 1 MB so the GitHub Pages front page remains fast.

Still in progress:

- Replacing the selected offensive-zone possession table with a more complete puck-control representation; current PK-state coverage is only `14.04%`.
- Deduping player-level analytics joins before model training.
- Documenting signed coordinate orientation before side-specific rink claims.
- Expanding tactical sequence mining and PK breakdown modeling.

## Architecture

Data flow:

```text
NHL play-by-play + shiftcharts
  -> NhlPkIngest
  -> PostgreSQL schema
  -> Analytics diagnostics
  -> xG / tactical models
  -> NhlPkApi
  -> Frontend analytics site
```

The ingestion app owns database loading. The Python layer assumes PostgreSQL
already has the source tables and focuses on diagnostics, modeling, and research
workflows. The API reads the latest generated analytics JSON from
`Analytics/models/output/` and shapes it for the frontend.

The MoneyPuck v2 path imports downloadable CSV files into `mp_*` tables and
writes `models_v2_run_*.json` files. The live API serves compact dashboard rows
for each season and keeps full model output behind detail endpoints and local
files. The older NHL API models remain as background context.

Current local MoneyPuck data is expected outside Git under
`D:\Hockey-data project` by default. The importer now prefers the full
`shots_2007-2024` historical shot file, adds 2025 season aggregate skater,
goalie, and team files when present, and can pick up a current-season shot file
from `shots_2025\shots_2025.csv`. The current-season shot file is the missing
piece for 2025-2026 heat maps and matchup models.

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

MoneyPuck v2 pipeline:

```bash
export NHL_DB_PASSWORD=your_password
./venv/Scripts/python.exe -m moneypuck.import_moneypuck --reset
./venv/Scripts/python.exe -m moneypuck.validate_moneypuck
./venv/Scripts/python.exe run_models_v2.py
```

To point the MoneyPuck importer at another download folder:

```powershell
$env:MONEYPUCK_DATA_ROOT = "D:\Hockey-data project"
```

The expected local CSV layout is documented in `Analytics/moneypuck/README.md`.

Generated reports and model artifacts are written to ignored local output folders such as `Analytics/runs/` and `Analytics/models/trained/`.

## Frontend Commands

Run these from `Frontend/`.

```powershell
npm install
npm run dev
npm run build
npm run lint
npm run qa:scouting
```

The frontend is React + TypeScript. It reads the dashboard data from
`http://localhost:5080/api` by default. If the API is unavailable, it loads the
committed real-data snapshot from `Frontend/public/data/dashboard.json`; only if
both fail does it use the small built-in fallback sample. The snapshot is
generated by `export-frontend-snapshot.ps1`, which calls the trimmed
`/api/analytics/v2/dashboard` endpoint and enforces a 1 MB size ceiling.

`npm run qa:scouting` expects the Vite dev server to be available at
`http://127.0.0.1:5173/#/scouting`. It uses the local Playwright dependency and
Microsoft Edge by default, checks the matchup controls, zone interaction,
season switching, mobile overflow, and browser console health. Set
`QA_BASE_URL` or `QA_BROWSER_CHANNEL` to override those defaults.

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

## Trust Gaps / Next Work

- Address the nullable warning in `PossessionTracker`.
- Re-ingest data after the possession-boundary fix, then rerun possession validation.
- Add event-level deduping bases for forward forechecking and defenseman gap-control models.
- Keep database credentials in local environment variables or ignored local config.
- Keep `docs/coordinate_conventions.md` and `Analytics/reports/latest_manpower_context.md` current after ingestion changes.
- Add deeper tests around possession splitting, shot possession linking, and xG backfill behavior.
- Re-check the GitHub Pages deployment after each frontend upload.

## Roadmap

Near term:

- Stabilize ingestion and possession tracking.
- Validate PK possessions at scale.
- Harden xG training and backfill.
- Build reliable event-level tactical features.

Medium term:

- Add goal-against sequence mining.
- Cluster recurring PK breakdown patterns.
- Build model reports for entry denial, clear failures, shot suppression, and
  net-front defense.
- Expand special-teams matchup previews into exportable scouting-report
  workflows.
- Expand the API layer beyond latest-run JSON into filterable database-backed reports.

Long term:

- Expand the web app for team, player, and tactical review.
- Support manual tactical labels from video review.
- Add richer causal and sequence modeling once the base data is stable.
