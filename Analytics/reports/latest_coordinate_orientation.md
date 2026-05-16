# Coordinate Orientation Validation

Generated: 2026-05-16T11:13:46

Status: **REVIEW**

Convention checked: home-team shots should usually be nearest the x=189 net; away-team shots should usually be nearest the x=11 net.

Total shots checked: `470093`
Nearest-net mismatches: `238119`
Mismatch rate: `50.65%`

## Summary

| shooting_side | home_perspective_target_net | nearest_net | shots |
| --- | --- | --- | --- |
| away | 11 | 11 | 120254 |
| away | 11 | 189 | 109666 |
| home | 189 | 11 | 128453 |
| home | 189 | 189 | 111720 |

## Zone Breakdown

| zone | shots | mismatches | mismatch_pct |
| --- | --- | --- | --- |
| DZ | 233503 | 233503 | 100.00 |
| NZ | 9312 | 4616 | 49.57 |
| OZ | 227278 | 0 | 0.00 |

## Model Implication

A high total mismatch rate means event-team target-net inference and nearest-net shot geometry are not interchangeable. If offensive-zone shots stay low-mismatch, nearest-net xG can still be useful for shot danger, but team-relative shot ownership and zone semantics need separate validation.
