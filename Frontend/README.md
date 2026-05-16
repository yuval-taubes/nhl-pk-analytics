# NHL PK Analytics Frontend

React + TypeScript model-story site for the NHL penalty kill analytics project.

This app is intentionally shaped like an interactive hockey research publication rather than a conventional dashboard: a visual landing page, one page per model, scouting summaries, and a clear data-honesty section.

## Stack

- Vite
- React
- TypeScript
- Bootstrap 5
- React-Bootstrap
- Recharts
- React Flow
- Lucide React

## Local Development

From the repository root, use two PowerShell terminals:

```powershell
.\start-api.ps1
```

```powershell
.\start-frontend.ps1
```

Or manually from the repository root:

```powershell
dotnet run --project .\NhlPkApi\NhlPkApi.csproj --urls http://localhost:5080
```

```powershell
cd Frontend
npm install
npm run dev
```

Git Bash should use forward slashes for the API project path:

```bash
dotnet run --project ./NhlPkApi/NhlPkApi.csproj --urls http://localhost:5080
```

The default API base URL is:

```text
http://localhost:5080/api
```

If the API is not running, the site loads the committed real-data snapshot at:

```text
public/data/dashboard.json
```

Refresh that snapshot after a new model run from the repository root:

```powershell
.\export-frontend-snapshot.ps1
```

Override it with:

```powershell
$env:VITE_API_BASE_URL = "http://localhost:5080/api"
npm run dev
```

## Current Screens

- Landing page with an animated rink-trace hero
- Model index at `#/models`
- Individual model pages at `#/models/{modelNumber}`
- Scouting profiles at `#/scouting`
- Data honesty page at `#/data-honesty`
- Live model takeaways, tactical rows, and player leaders from `GET /api/analytics/dashboard`

## Design Direction

The UI should feel like a hockey operations research piece:

- Dark, high-contrast workstation theme
- Ice-blue tactical accents
- Red for goals/danger
- Green for clears/success
- Amber for penalties/warnings
- Editorial landing-page rhythm
- Animated rink-line motifs inspired by SVG path drawing
- One model story per page
- No generic SaaS hero pages

## Next Frontend Milestones

1. Replace hash routing with a formal router if the site grows.
2. Add richer graphics for each model page using the raw model JSON endpoints.
3. Add team/season filters once the API supports filtered outputs.
4. Add model diagnostics pages for coordinate, possession, and xG validation.
5. Build a real rink component using normalized 200x85 coordinates.
