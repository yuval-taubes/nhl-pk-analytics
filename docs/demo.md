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

Run the API against the latest generated local model artifact:

```powershell
.\start-api.ps1
```

Run the frontend:

```powershell
.\start-frontend.ps1
```

The published frontend uses `Frontend/public/data/dashboard.json`, which is a
committed snapshot generated from the real API/model output. That keeps the demo
interactive even when the local database and API are off.

## Current Headline Claim

The project demonstrates an end-to-end NHL penalty-kill analytics system:

- .NET ingestion from public NHL play-by-play
- PostgreSQL schema and re-ingestion support
- Python validation and modeling workflows
- xG backfill into shot and possession tables
- ASP.NET API over generated analytics artifacts
- React frontend for model-story review

The strongest current hockey finding is the defensive-zone PK faceoff result.
Entry-impact and player-event models remain exploratory and are documented with
explicit invalid-use caveats.
