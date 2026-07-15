# Shift-Covered PK Exposure

Generated: 2026-07-15T01:04:44

Game limit: `3936`
Requested games: `3936`
Games with shiftcharts: `3879`
Games without shiftcharts: `57`
Games with source errors: `0`
Games not checked: `0`

## Shift-Age Buckets For PK Shot Attempts Against

| shift_age_bucket | player_shot_attempt_events_against | avg_shift_age_seconds |
| --- | --- | --- |
| 00-29 | 128738 | 16.1 |
| 30-44 | 64844 | 36.6 |
| 45-59 | 43673 | 51.3 |
| 60+ | 50364 | 82.6 |

## Player PK Exposure Sample

| player | team | games | pk_event_samples | avg_shift_age_seconds | p90_shift_age_seconds | shot_attempt_events_against | goal_events_against |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Esa Lindell | DAL | 235 | 4330 | 42.8 | 97 | 1566 | 28 |
| Adam Larsson | SEA | 231 | 3928 | 40.8 | 98 | 1555 | 40 |
| Mario Ferraro | SJS | 220 | 3476 | 35.8 | 85 | 1458 | 41 |
| Jamie Oleksiak | SEA | 227 | 3712 | 38.2 | 90 | 1445 | 39 |
| David Savard | MTL | 190 | 3519 | 34.7 | 83 | 1400 | 29 |
| Jake Sanderson | OTT | 231 | 3926 | 29.9 | 73 | 1382 | 30 |
| Gustav Forsling | FLA | 234 | 3903 | 28.5 | 68 | 1331 | 41 |
| Mike Matheson | MTL | 198 | 3426 | 38.4 | 92 | 1319 | 47 |
| Jake Evans | MTL | 212 | 3369 | 26.7 | 63 | 1315 | 29 |
| Moritz Seider | DET | 231 | 3429 | 28.8 | 72 | 1303 | 28 |
| Devon Toews | COL | 229 | 3417 | 31 | 77.4 | 1271 | 60 |
| John Carlson | WSH | 193 | 3130 | 36.3 | 88 | 1201 | 43 |
| Dylan DeMelo | WPG | 232 | 3015 | 26.7 | 65 | 1172 | 59 |
| Mikey Anderson | LAK | 219 | 2980 | 31.6 | 75 | 1142 | 50 |
| Brayden McNabb | VGK | 229 | 2852 | 33.5 | 78.9 | 1142 | 48 |
| Alex Pietrangelo | VGK | 200 | 2934 | 36.8 | 88 | 1142 | 21 |
| Brandon Tanev | SEA | 200 | 2929 | 25.5 | 63 | 1141 | 15 |
| Erik Cernak | TBL | 201 | 3299 | 32.7 | 80 | 1137 | 18 |
| Brandon Carlo | BOS | 206 | 3512 | 27.6 | 66 | 1122 | 24 |
| Rasmus Andersson | CGY | 230 | 3018 | 27.9 | 69 | 1116 | 57 |
| Cale Makar | COL | 207 | 2879 | 29.7 | 75 | 1115 | 70 |
| Mikael Backlund | CGY | 230 | 3451 | 22.1 | 57 | 1101 | 23 |
| Darnell Nurse | EDM | 226 | 3161 | 27.1 | 68 | 1099 | 36 |
| Colton Sissons | NSH | 232 | 3121 | 22 | 55 | 1099 | 19 |
| Adam Lowry | WPG | 230 | 2987 | 20.8 | 54 | 1091 | 15 |

## Interpretation

This is a source-covered descriptive exposure report, not a player-impact model. Rows only include games where NHL shiftcharts returned source rows and only count player-event exposures where a skater was shift-derived as on ice while his team was shorthanded. Shot-attempt and goal counts are therefore exposure events, not unique team shot totals.

The shift-age bucket table intentionally excludes goals. Several NHL shiftchart rows start or stop at scoring timestamps, so goal-event shift age can be reset to zero and should not be used as a fatigue proxy until that edge case is audited separately. Player rows still keep goal_events_against as an outcome exposure column.

Use these outputs to design TOI/fatigue features; keep source coverage counts attached to any downstream model or UI claim.
