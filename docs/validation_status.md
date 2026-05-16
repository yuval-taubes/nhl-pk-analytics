# Validation Status

Last updated: 2026-05-16

This file is the project trust ledger. It separates checks that currently have
machine-readable support from checks that still need manual or regression-test
coverage.

## Current Checks

| Component | Status | Evidence |
| --- | --- | --- |
| CI build | Passing by workflow definition | `.github/workflows/ci.yml` builds .NET, frontend, and compiles Python |
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

## Still Needs Proof

| Component | Needed Next |
| --- | --- |
| Golden-game ingestion regression | Run after each re-ingest; current fixture is `2022020154`, NSH at EDM on 2022-11-01 |
| xG backfill | Add idempotence and possession-sum tests |
| Coordinate orientation | Investigate event-team/zone semantics; latest report is `REVIEW`, not a pass |
| Entry-attempt labels | Manually review a sample of inferred attempts |
| Player-level joins | Add event-level dedupe bases where join diagnostics still inflate rows |
| Demo assets | Add screenshots or a short demo video before outreach |

## External Reader Summary

The repo is credible as an engineering pipeline now. The safest public claim is
that it ingests, validates, models, serves, and visualizes NHL PK data. The
analytics claims should stay narrower: faceoff-window results are the strongest;
entry and player-profile models are exploratory until the validation gaps above
are closed.
