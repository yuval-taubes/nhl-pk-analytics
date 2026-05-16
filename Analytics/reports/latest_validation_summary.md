# Latest Validation Summary

Generated: 2026-05-16T11:13:11

## Database-Backed Checks

| Check | Status | Result |
| --- | --- | --- |
| Manpower convention | PASS | `strength` matches `away_skaters v home_skaters` for all special-teams events checked |
| Golden game regression | PASS | Game `2022020154` matched expected event, shot, goal, possession, and xG counts |
| Join inflation | PASS | Forward forechecking 1.4x, defense gap control 1.1x, shot suppression 1.0x, net-front defense 1.0x |
| xG validation | PASS | AUC 0.7783, rebound xG > non-rebound xG, distance correlation -0.4733, max xG 0.5261 |
| Coordinate bounds | PASS | 470,093 shots inside normalized 200 x 85 rink bounds |
| Possession validation sample | PASS | 50 sampled possessions, 8.0% issue rate |
| Coordinate orientation | REVIEW | Total nearest-net mismatch 50.65%; offensive-zone shots need to be separated from defensive-zone-labeled shot semantics |

## Current Interpretation

The core ingestion/model-serving path is in decent shape: manpower, xG, join
inflation, and the golden game all pass. The main unresolved trust issue is not
basic coordinate bounds; it is the relationship between event-team ownership,
team-relative zone labels, and nearest-net shot geometry. Treat nearest-net xG
as a shot-danger convention until that semantic layer is fully resolved.
