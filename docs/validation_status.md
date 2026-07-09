# Validation Status

Last updated: 2026-07-08

This file is the project trust ledger. It separates checks that currently have
machine-readable support from checks that still need manual or regression-test
coverage.

## Current Checks

| Component | Status | Evidence |
| --- | --- | --- |
| CI build | Passing by workflow definition | `.github/workflows/ci.yml` builds .NET, frontend, and compiles Python |
| Published frontend | Configured | `.github/workflows/deploy-frontend.yml` deploys `Frontend/dist` to GitHub Pages |
| Real-data static demo | Added | `Frontend/public/data/dashboard.json` is committed and copied into the static build |
| MoneyPuck v2 dashboard | Added | `/api/analytics/v2/dashboard` serves compact top rows per season |
| MoneyPuck source discovery | Added | `python -m moneypuck.import_moneypuck --describe-sources` prints resolved CSV groups |
| Special teams matchup model | Added | `models_v2/special_teams_matchups.py` exports PP attack, PK leak, matchup, and heat-map aggregates |
| Scouting Lab frontend | Passing locally | Matchup Lab, Scouting Brief, Player Passports, and Discovery sections have a first-pass workflow with current-read strip and actionable matchup examples |
| MoneyPuck v2 snapshot size | Passing locally | `Frontend/public/data/dashboard.json` is about 650 KB, below the 1 MB launch ceiling |
| Frontend build | Passing locally | `npm run build` passed on 2026-07-08 |
| Frontend lint | Passing locally | `npm run lint` passed on 2026-07-08 |
| Scouting Playwright smoke QA | Added | `npm run qa:scouting` checks scouting controls, zone interaction, season switching, mobile overflow, tactical board presence, and console health when Vite is running |
| .NET build | Passing locally | `dotnet build .\Data_ingestion.sln --configuration Release` passed on 2026-07-04 |
| Lightweight Python tests | Passing locally | `python -m unittest discover -s Analytics\tests` passed on 2026-07-04 |
| Manpower convention | Checked locally | `Analytics/reports/latest_manpower_context.md` |
| Latest validation summary | Added | `Analytics/reports/latest_validation_summary.md` |
| Strength mapping | Documented | `docs/coordinate_conventions.md` |
| Event-player duplicate guard | Schema constraint added | `event_players_unique_event_player` |
| Player scouting duplicate guard | Schema constraint added | `player_scouting_unique_metric` |
| Model 1 post-treatment covariates | Fixed | matching excludes `duration_seconds` and `shot_count` |
| Model 1 matching diagnostics | Added | model output includes matched sample counts |
| API missing metrics | Hardened | missing numeric JSON values render as `N/A` instead of zero |
| Golden-game fixture | Added | `Analytics/diagnostics/golden_games/2022020154.json` |
| Golden-game regression runner | Added | `Analytics/diagnostics/golden_game_regression.py` |
| MoneyPuck source credit | Documented | `Analytics/moneypuck/README.md` and v2 API caveats credit MoneyPuck.com |

## Still Needs Proof

| Component | Needed Next |
| --- | --- |
| Golden-game ingestion regression | Run after each re-ingest; current fixture is `2022020154`, NSH at EDM on 2022-11-01 |
| xG backfill | Add idempotence and possession-sum tests |
| Coordinate orientation | Investigate event-team/zone semantics; latest report is `REVIEW`, not a pass |
| Entry-attempt labels | Manually review a sample of inferred attempts |
| Player-level joins | Add event-level dedupe bases where join diagnostics still inflate rows |
| Demo assets | Interactive GitHub Pages demo is configured; screenshots/video are optional polish |
| Rendered mobile QA | Re-run `npm run qa:scouting` and verify GitHub Pages after deployment |
| 2025-2026 shot-level MoneyPuck data | Download current-season shots to `shots_2025\shots_2025.csv`, then re-import |

## External Reader Summary

The repo is credible as an engineering pipeline and public 2.0 demo. The safest
public claim is that it ingests, validates, models, serves, and visualizes NHL
PK data. The MoneyPuck v2 layer can support descriptive shot-quality, rebound,
goalie-control, fatigue, season-scouting, inferred matchup views, generated
scouting briefs, and player passports with sample caveats. Causal claims,
tracking-style positioning claims, exact-formation claims, and full
player-impact claims should still be avoided.
