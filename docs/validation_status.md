# Validation Status

Last updated: 2026-07-15

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
| Shift/on-ice reconstruction | Passing on all source-covered games | `Analytics/reports/latest_shift_on_ice_validation.md` checks `3,879` shift-covered games, `1,224,084/1,224,084` events with manpower rows, and a `1.05%` model-safe mismatch rate; top-level status remains `REVIEW` only because 57 games lack source rows |
| MoneyPuck shot alignment | Passing locally | `Analytics/reports/latest_moneypuck_shot_alignment.md` matched `340,834/342,924` unblocked NHL shot rows (`99.39%`) with tight coordinate-magnitude alignment |
| Shift-covered PK exposure | Added with caveat | `Analytics/reports/latest_shift_pk_exposure.md` summarizes all `3,879` source-covered games; shift-age buckets exclude goals because scoring timestamps can reset shift age |

## Still Needs Proof

| Component | Needed Next |
| --- | --- |
| Golden-game ingestion regression | Run after each re-ingest; current fixture is `2022020154`, NSH at EDM on 2022-11-01 |
| xG backfill | Add idempotence and possession-sum tests |
| Coordinate orientation | MoneyPuck shot magnitude alignment passes locally; signed rink direction still needs explicit convention docs before side-specific model claims |
| Entry-attempt labels | Manually review a sample of inferred attempts |
| Player-level joins | Add event-level dedupe bases where join diagnostics still inflate rows |
| Shiftchart source coverage | Full census complete | `3,879/3,936` games (`98.55%`) return shift rows; the 57-game `2024021235-2024021291` block returns successful zero-row responses |
| Shift source audit state | Added and migrated | `game_shift_source_status` distinguishes available, empty response, request error, and not checked; every ingested game now has persisted endpoint evidence |
| Shift player/event feature layer | Added | `pk_shift_player_event_features` gates on available source state and exposes shift age, duration, rest, PK state, and provenance |
| Shift coverage UI | Added | The v2 API returns `shiftCoverage`; the Data Honesty page displays latest checked coverage and eligibility |
| Season-stratified shift coverage | Passing sample | Evenly spaced 20-game samples returned `20/20` in 2022-23, `20/20` in 2023-24, and `19/20` in 2024-25 |
| Focused 2024-25 source gap | Confirmed | `2024021235-2024021291` returned zero rows; adjacent `1230-1234` and `1292-1312` returned normal shiftcards with no request errors |
| Full shift-source census | Passing with bounded gap | All `3,936` ingested games checked on 2026-07-13: `3,879` available (`98.55%`), 57 successful zero-row responses (`1.45%`), no unchecked games, and no request errors; source availability does not imply feature backfill |
| Shift-age pressure diagnostic | Exploratory | Pressure rises materially after 30 seconds, but event mix, zone, opponent, score, and possession context are not controlled |
| Verified-source shift backfill | Passing with one filtered malformed row | All `3,879` source-available games now contain shifts; `2022020160` required null-safe parsing for one source row with `playerId: null`, which is discarded while valid rows ingest |
| All-covered manpower validation | Passing covered subset | `1,224,084/1,224,084` events have manpower rows across 3,879 games; model-safe mismatch rate is `1.05%` |
| Rest pressure diagnostic | Exploratory weak/non-monotonic | Shortest-rest buckets range from `39.20` to `44.28` non-goal attempts per 100 recorded events without a monotonic pattern; rest is a game-clock shift gap and excludes real intermission duration |
| Shift-covered MoneyPuck xG | Incomplete by bucket | Validated time/team matching populates xG, but shift-age bucket coverage is `80.62-90.51%`, below the 95% gate in every bucket; directional audit only |
| Adjusted next-shot pressure | Promising full-sample association | 3,878-game clustered model on 186,951 states estimates `15.88%`, `17.26%`, `18.80%`, and `20.18%`; every older bucket excludes the reference at the 10-second horizon |
| Pressure horizon sensitivity | Stable across horizons | Older-shift estimates are higher with intervals excluding the reference at 5, 10, and 15 seconds in the full sample |
| Causal fatigue claim | Blocked | Exact possession state, deployment intent, substitutions between events, and tracking context remain unobserved |
| Adjusted pressure API/UI evidence | Passing locally | Live v2 API exposes `shiftPressureResearch`; Data Honesty renders all four adjusted buckets, sample size, and non-causal caveat on desktop/mobile with no console errors or horizontal overflow |
| Existing possession-table conditioning | Rejected | Selected PP possessions cover only `26,250/186,952` shift-covered PK team-events (`14.04%`); no overlap inflation, but severe selection makes it unsuitable as a complete risk set |
| PP offensive-zone control sensitivity | Passing robustness check | `50,666` PP-owned OZ states across 3,822 games rise from `24.65%` fresh-shift risk to `26.37%`, `27.48%`, and `29.58%`; all older-bucket clustered intervals exclude the reference |
| Shift audit-only mode | Fixed and tested | `migrate_shift_source_status.py --audit-only` now skips schema/backfill execution and starts a read-only transaction; the previous ignored flag could contend with live ingestion DDL |
| Shift/on-ice edge cases | Keep auditing all-event mismatches, especially penalty timing, period/game-end rows, stoppages, goalie-pulled states, and goal-timestamp shift splits; do not use those rows as silent proof for player impact |
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
