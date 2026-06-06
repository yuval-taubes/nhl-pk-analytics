# Demo Path

This repository is easiest to evaluate as a data product pipeline rather than a
single notebook. The full local path uses PostgreSQL, .NET, Python, the API, and
the frontend, but a reviewer should not need to recreate the whole database just
to understand the work.

## What To Look At First

1. Live frontend: https://yuval-taubes.github.io/nhl-pk-analytics/
2. Root project overview: `README.md`
3. Model capability boundaries: `Analytics/README.md`
4. Current validation status: `docs/validation_status.md`
5. Model cards: `docs/model_cards.md`
6. Frontend real-data snapshot: `Frontend/public/data/dashboard.json`

The live frontend is deployed by GitHub Actions. In repository settings, GitHub
Pages should use **GitHub Actions** as the source.

## Local Demo Commands

Build everything that does not require a live database:

```powershell
dotnet build .\Data_ingestion.sln --configuration Release
cd .\Frontend
npm ci
npm run build
cd ..
python -m compileall Analytics
python -m unittest discover -s Analytics/tests
```

Run the golden-game regression against the local database:

```powershell
cd .\Analytics
$env:NHL_DB_PASSWORD = "your_password"
.\venv\Scripts\python.exe diagnostics\golden_game_regression.py
```

Run the API against the latest generated local model file:

```powershell
.\start-api.ps1
```

Run the frontend:

```powershell
.\start-frontend.ps1
```

The published frontend uses `Frontend/public/data/dashboard.json`, a compact
snapshot generated from the real API output. That keeps the demo interactive
even when the local database and API are off.

Refresh the GitHub Pages snapshot:

```powershell
.\export-frontend-snapshot.ps1
```

The exporter calls the trimmed MoneyPuck v2 dashboard endpoint and refuses to
write snapshots larger than 1 MB.

## MoneyPuck V2 Path

The v2 rebuild adds a MoneyPuck-backed analytics path beside the original NHL
API pipeline. See:

- `Analytics/moneypuck/README.md` for local CSV import and validation.
- `Analytics/models_v2/README.md` for the new PK Decision Lab model suite.

Local v2 flow:

```powershell
cd .\Analytics
$env:NHL_DB_PASSWORD = "your_password"
.\venv\Scripts\python.exe -m moneypuck.import_moneypuck --reset
.\venv\Scripts\python.exe -m moneypuck.validate_moneypuck
.\venv\Scripts\python.exe run_models_v2.py
```

The API exposes compact v2 dashboard output at `/api/analytics/v2/dashboard`
when a `models_v2_run_*.json` artifact exists. The scouting page now includes a
season selector, empirical-Bayes PK impact estimates, uncertainty labels, and
similar-player groups. Full v2 model output remains available through
`/api/analytics/v2/models/{modelKey}` for deeper local inspection.

## 2.0 Launch Check

Before pushing the public update:

```powershell
dotnet build .\Data_ingestion.sln --configuration Release
python -m unittest discover -s Analytics\tests
python -m compileall Analytics
cd .\Frontend
npm run build
cd ..
.\export-frontend-snapshot.ps1
```

The frontend uses custom CSS breakpoints rather than Bootstrap. Check at least
desktop, tablet-ish width, and phone width before publishing.

## Current Headline Claim

The project demonstrates an end-to-end NHL penalty-kill analytics system:

- .NET ingestion from public NHL play-by-play
- PostgreSQL schema and re-ingestion support
- Python validation and modeling workflows
- xG backfill into shot and possession tables
- ASP.NET API over generated analytics output
- React frontend for model review and scouting

The current 2.0 focus is the MoneyPuck v2 penalty-kill view: shot movement,
second chances, goalie control, fatigue, and season-level scouting.
