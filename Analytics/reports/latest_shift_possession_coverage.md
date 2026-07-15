# Shift / Possession Coverage Audit

Generated: 2026-07-15T01:04:30

Status: **INSUFFICIENT**
Shift-covered games: `3879`
Games with reconstructed PP possessions: `3194`
Reconstructed PP possessions: `7380`
Reversed possession boundaries: `0`
PK team-events: `186952`
Events inside a reconstructed PP possession: `26250`
Coverage rate: `14.04%`
Events matching multiple possessions: `0`
Ambiguous rate: `0.00%`

## Lowest-Coverage Games

| game_id | pk_team_events | matched_events | ambiguous_events | coverage_pct |
| --- | --- | --- | --- | --- |
| 2022020006 | 41 | 0 | 0 | 0 |
| 2022020023 | 40 | 0 | 0 | 0 |
| 2022020039 | 37 | 0 | 0 | 0 |
| 2022020048 | 63 | 0 | 0 | 0 |
| 2022020049 | 46 | 0 | 0 | 0 |
| 2022020057 | 14 | 0 | 0 | 0 |
| 2022020064 | 46 | 0 | 0 | 0 |
| 2022020070 | 33 | 0 | 0 | 0 |
| 2022020077 | 18 | 0 | 0 | 0 |
| 2022020078 | 30 | 0 | 0 | 0 |
| 2022020079 | 47 | 0 | 0 | 0 |
| 2022020080 | 84 | 0 | 0 | 0 |
| 2022020084 | 33 | 0 | 0 | 0 |
| 2022020087 | 55 | 0 | 0 | 0 |
| 2022020089 | 36 | 0 | 0 | 0 |
| 2022020128 | 72 | 0 | 0 | 0 |
| 2022020135 | 39 | 0 | 0 | 0 |
| 2022020141 | 31 | 0 | 0 | 0 |
| 2022020143 | 41 | 0 | 0 | 0 |
| 2022020167 | 25 | 0 | 0 | 0 |

## Possession Shapes

| entry_type | end_type | possessions | avg_duration_seconds | shots |
| --- | --- | --- | --- | --- |
| FACEOFF_START | STOPPAGE | 2773 | 34.8 | 5108 |
| FACEOFF_START | STRENGTH_CHANGE | 1074 | 49.9 | 2578 |
| FACEOFF_START | CLEAR | 1047 | 46.7 | 1853 |
| FACEOFF_START | GOAL | 905 | 32 | 1863 |
| FACEOFF_START | TURNOVER | 888 | 47.1 | 1483 |
| TURNOVER | STOPPAGE | 113 | 29.4 | 193 |
| TURNOVER | STRENGTH_CHANGE | 90 | 33.3 | 166 |
| DUMP_IN | STRENGTH_CHANGE | 90 | 26.4 | 165 |
| DUMP_IN | STOPPAGE | 76 | 30.8 | 143 |
| CONTROLLED | STOPPAGE | 59 | 28.4 | 94 |
| CONTROLLED | STRENGTH_CHANGE | 50 | 34 | 91 |
| TURNOVER | GOAL | 44 | 23.3 | 71 |
| TURNOVER | TURNOVER | 42 | 42.4 | 68 |
| TURNOVER | CLEAR | 32 | 30.7 | 47 |
| DUMP_IN | GOAL | 31 | 21.5 | 50 |
| DUMP_IN | CLEAR | 17 | 36.4 | 26 |
| CONTROLLED | TURNOVER | 15 | 44.8 | 21 |
| DUMP_IN | TURNOVER | 13 | 50.5 | 19 |
| CONTROLLED | GOAL | 11 | 36.5 | 23 |
| CONTROLLED | CLEAR | 10 | 44.3 | 16 |

## Interpretation

The existing possession table contains selected offensive-zone sequences that begin with detected entries, OZ faceoffs, or turnovers and pass a meaningful-activity filter. It is not a complete puck-control timeline. `SUITABLE` requires at least 80% event coverage with at most 1% ambiguous overlap; `PARTIAL` requires at least 50% coverage with at most 3% overlap.
