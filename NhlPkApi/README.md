# NHL PK API

This is the mid-layer between the Python analytics outputs and the React site.

It reads the latest generated analytics JSON from:

```text
../Analytics/models/output/
```

The legacy endpoints use `models_2_10_run_*.json`. The MoneyPuck v2 endpoints use
`models_v2_run_*.json` and return compact dashboard rows for the frontend.

## Run

From the repository root:

Preferred PowerShell script:

```powershell
.\start-api.ps1
```

That script runs the project through `dotnet run` and avoids launching the Windows apphost executable directly.

PowerShell:

```powershell
dotnet run --project .\NhlPkApi\NhlPkApi.csproj --urls http://localhost:5080
```

Git Bash:

```bash
dotnet run --project ./NhlPkApi/NhlPkApi.csproj --urls http://localhost:5080
```

Use forward slashes in Git Bash. Backslashes are treated as escape characters and can turn the project path into `.NhlPkApiNhlPkApi.csproj`.

The frontend defaults to this API base URL:

```text
http://localhost:5080/api
```

## Endpoints

```text
GET /api/health
GET /api/analytics/latest-run
GET /api/analytics/models
GET /api/analytics/models/{modelNumber}
GET /api/analytics/dashboard
GET /api/analytics/v2/latest-run
GET /api/analytics/v2/models
GET /api/analytics/v2/models/{modelKey}
GET /api/analytics/v2/dashboard
```

`/api/analytics/v2/dashboard` is the primary frontend endpoint for 2.0. It
returns metric cards, model takeaways, movement rows, goalie/player scouting
leaders, available seasons, caveats, latest-run metadata, and optional
`shiftCoverage` evidence from `Analytics/reports/latest_shift_availability.json`.
That field describes NHL shiftchart availability only; it does not change
MoneyPuck model eligibility.

The dashboard also returns optional `shiftPressureResearch` evidence from the
adjusted source-covered next-shot model. The field is explicitly labeled as an
association and is shown on Data Honesty rather than promoted as a causal model.

`/api/analytics/dashboard` remains available for the older NHL API model pages.

## Configuration

`AnalyticsOutputPath` can be set in `appsettings.json` or through configuration/environment overrides if the analytics output folder moves.

## Next Evolution

This JSON-backed API is still the simplest fit for a portfolio/front-page
release. Once the filters stabilize, promote durable outputs into database
tables and let the API read from Postgres for team, season, player, and strength
state filtering.
