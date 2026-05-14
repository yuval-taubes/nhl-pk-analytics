# NHL PK Analytics Frontend

React + TypeScript dashboard shell for the NHL penalty kill analytics project.

This app is intentionally shaped like an analyst workstation rather than a marketing site: dense filters, quick status panels, rink visuals, model diagnostics, and sequence-mining views.

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

```powershell
cd Frontend
npm install
npm run dev
```

The default API base URL is:

```text
http://localhost:5080/api
```

Override it with:

```powershell
$env:VITE_API_BASE_URL = "http://localhost:5080/api"
npm run dev
```

## Current Screens

- Dashboard shell
- PK pressure trend
- Shot danger rink placeholder
- Goal-against sequence flow placeholder
- Breakdown cluster table

## Design Direction

The UI should feel like a hockey operations analytics room:

- Dark, high-contrast workstation theme
- Ice-blue tactical accents
- Red for goals/danger
- Green for clears/success
- Amber for penalties/warnings
- Dense but readable information hierarchy
- No generic SaaS hero pages

## Next Frontend Milestones

1. Add ASP.NET Core API project or endpoints.
2. Replace mock dashboard data with API calls.
3. Build a real rink component using normalized 200x85 coordinates.
4. Add model diagnostics pages for coordinate, possession, and xG validation.
5. Code-split heavy chart/flow routes once routing is introduced.
