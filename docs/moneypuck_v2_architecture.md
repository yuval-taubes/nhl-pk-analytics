# MoneyPuck V2 Architecture

Last updated: 2026-07-08

This note is the working map for the MoneyPuck rebuild. It explains what each
layer owns, where new data should land, and which parts are ready for the next
frontend expansion.

## Data Sources

Local MoneyPuck downloads live outside Git under `D:\Hockey-data project` by
default. The importer resolves files from `Analytics/moneypuck/config.py`.

Current resolved layout:

- `shots_2007-2024\shots_2007-2024.csv`
- `all_teams.csv`
- `skaters_2008_to_2024\skaters_2008_to_2024.csv`
- `goalies_2008_to_2024\goalies_2008_to_2024.csv`
- `teams_2008_to_2024\teams_2008_to_2024.csv`
- `skaters_2025\skaters_2025.csv`
- `goalies_2025\goalies_2025.csv`
- `teams_2025\teams_2025.csv`

The current missing file is the 2025-2026 shot-level CSV. Place it at:

```text
shots_2025\shots_2025.csv
```

Run this before importing to confirm the exact files:

```powershell
cd .\Analytics
.\venv\Scripts\python.exe -m moneypuck.import_moneypuck --describe-sources
```

## Database Layer

`Analytics/moneypuck/schema.sql` owns the side-by-side `mp_*` tables. These
tables do not replace the older NHL API schema.

Current imported groups:

- `mp_shots`: shot-level MoneyPuck data, keyed by `(season, game_id, shot_id)`.
- `mp_team_games`: team-game aggregates from `all_teams.csv`.
- `mp_skaters_season`: skater season aggregates.
- `mp_goalies_season`: goalie season aggregates.
- `mp_teams_season`: team season aggregates.

The importer can read multiple CSVs per group, so adding a season should not
require code changes if the file lands in the documented layout. Imports use
primary-key upserts, so refreshed MoneyPuck rows replace older local values.

## Model Layer

`Analytics/run_models_v2.py` is the v2 runner. It writes one combined
`models_v2_run_*.json` artifact plus individual model JSON files.

Model modules:

- `models_v2/moneypuck_pk_models.py`: core PK movement, after-block, goalie,
  fatigue, short-handed two-way value, empirical-Bayes player evaluation, and
  rush/set diagnostics.
- `models_v2/special_teams_matchups.py`: PP attack profiles, PK leak profiles,
  matchup cards, and aggregate heat-map bins. Team attack/leak indexes are
  compared against same-season league baselines.
- `models_v2/player_tags.py`: player-passport tagging layer. It consumes
  season aggregate metrics, computes season percentiles and trust context, then
  emits tags with reasons, trigger metrics, sample notes, and caveats.
- `models_v2/common.py`: shared JSON-safe output helpers.

The model layer should stay descriptive. It can say a team creates or allows a
look in public shot data. It should not claim exact formations without film or
tracking data.

## API Layer

`NhlPkApi/Program.cs` loads the latest v2 artifact and trims it for the
frontend through:

```text
/api/analytics/v2/dashboard
/api/analytics/v2/models
/api/analytics/v2/models/{modelKey}
```

The dashboard now exposes compact matchup fields:

- `leagueAttackTypes`
- `ppAttackProfiles`
- `pkLeakProfiles`
- `matchupCards`
- `leaguePkDangerHeatmap`
- `playerTagProfiles`
- `playerTagDictionary`

These are enough for a matchup preview and heat-map story page without shipping
raw shot rows to the browser. The player tag fields are enough for a first
Player Passport surface without asking React to invent hockey labels.

## Frontend Contract

`Frontend/src/data/dashboard.ts` defines the TypeScript contract for the API
response. It includes typed rows for matchup cards, attack profiles, and
heat-map bins. It also includes typed player tags and tag definitions.

The current `#/scouting` page is organized as a professional scouting workflow:

- Matchup Lab: season, PP team, PK team, selected exploit, tactical board, and
  generated Scouting Brief. The first-pass UI includes a compact current-read
  strip and actionable matchup example cards that load a matchup into the
  selectors.
- Player Passports: selected-season player tags with sample trust and
  expandable evidence.
- Player + Goalie Discovery: broader leaderboards and similar-player tools that
  support, but do not compete with, the selected matchup.

The frontend keeps formula/debug details secondary. The main scouting output is
plain-English: where the edge is, how to attack it, what evidence supports it,
and which public-data caveats still apply.

## Validation

Current local checks:

```powershell
dotnet build .\Data_ingestion.sln --configuration Release
cd .\Analytics
python -m unittest discover -s tests
python -m compileall models_v2 moneypuck run_models_v2.py
cd ..\Frontend
npm run build
npm run lint
npm run qa:scouting
```

`npm run qa:scouting` expects the local Vite server at
`http://127.0.0.1:5173/#/scouting`. It checks the scouting controls, selected
zone updates, season switching, mobile overflow, tactical-board presence, and
browser console health.

Before trusting a fresh run, also run:

```powershell
cd .\Analytics
.\venv\Scripts\python.exe -m moneypuck.validate_moneypuck
```

## Next Work

1. Download the current-season MoneyPuck shot CSV into `shots_2025`.
2. Re-import MoneyPuck tables.
3. Run `run_models_v2.py`.
4. Verify the new `SpecialTeamsMatchupModel` output in the latest JSON.
5. Add richer export formats for the Scouting Brief once the plain-text flow is
   stable.
