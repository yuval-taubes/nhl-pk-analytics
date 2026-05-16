# Manpower Context Validation

Generated: 2026-05-16T01:44:10

Status: **PASS**

Convention checked: `strength` is stored as `away_skaters v home_skaters`.

Mismatched special-teams events: `0`
Special-teams events with missing skater counts: `0`

## Special-Teams Strength Summary

| strength | home_skaters | away_skaters | events |
| --- | --- | --- | --- |
| 4v5 | 5 | 4 | 83293 |
| 5v4 | 4 | 5 | 77552 |
| 3v5 | 5 | 3 | 1985 |
| 5v3 | 3 | 5 | 1773 |
| 3v4 | 4 | 3 | 1489 |
| 4v3 | 3 | 4 | 1219 |

## Model Implication

PP team inference from `strength` is valid only under the away-v-home convention above. Future models should prefer a shared context view/helper over repeating string parsing.
