# NHL PK API

This is the mid-layer between the Python analytics outputs and the React dashboard.

The first version intentionally reads the latest combined analytics JSON from:

```text
../Analytics/models/output/models_2_10_run_*.json
```

That keeps the frontend connected to real model output without requiring a reporting schema before the dashboard shape settles.

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
```

`/api/analytics/dashboard` is the frontend-ready endpoint. It returns metric cards, model takeaways, tactical rows, player leaders, caveats, and latest-run metadata.

## Configuration

`AnalyticsOutputPath` can be set in `appsettings.json` or through configuration/environment overrides if the analytics output folder moves.

## Next Evolution

This JSON-backed API is the right first step. Once the frontend interactions stabilize, promote the durable outputs into database tables and let the API read from Postgres for filtering by team, season, player, and strength state.
