# Shift / On-Ice Validation

Generated: 2026-07-15T01:03:03

Status: **REVIEW**

Requested games: `3936`
Games with shiftcharts: `3879`
Games without shiftcharts: `57`
Games with source errors: `0`
Games not checked: `0`
Covered-games status: **PASS**
Games checked: `3879`
Events checked: `1224084`
Raw shift rows: `2931003`
Event on-ice rows: `14190396`
Manpower rows: `1224084`
Situation-code matches: `1164774`
All-event mismatch rate: `4.85%`
Model-safe events: `986028`
Model-safe manpower rows: `986028`
Model-safe mismatches: `10386`
Model-safe mismatch rate: `1.05%`

## Missing Shiftchart Source Games

| game_id |
| --- |
| 2024021291 |
| 2024021290 |
| 2024021289 |
| 2024021288 |
| 2024021287 |
| 2024021286 |
| 2024021285 |
| 2024021284 |
| 2024021283 |
| 2024021282 |
| 2024021281 |
| 2024021280 |
| 2024021279 |
| 2024021278 |
| 2024021277 |
| 2024021276 |
| 2024021275 |
| 2024021274 |
| 2024021273 |
| 2024021272 |
| 2024021271 |
| 2024021270 |
| 2024021269 |
| 2024021268 |
| 2024021267 |
| 2024021266 |
| 2024021265 |
| 2024021264 |
| 2024021263 |
| 2024021262 |

## Mismatches By Event Type

| event_type | mismatches | period_boundary | one_skater_off | goalie_pulled | model_safe_mismatches |
| --- | --- | --- | --- | --- | --- |
| penalty | 26376 | 421 | 21333 | 749 | 0 |
| period-end | 12709 | 11883 | 333 | 12709 | 0 |
| goal | 7784 | 563 | 7032 | 1183 | 7784 |
| stoppage | 5078 | 27 | 4319 | 1041 | 0 |
| game-end | 3879 | 3299 | 153 | 3879 | 0 |
| shot-on-goal | 1488 | 879 | 1296 | 961 | 1488 |
| missed-shot | 511 | 293 | 463 | 320 | 511 |
| period-start | 312 | 312 | 307 | 246 | 0 |
| delayed-penalty | 277 | 1 | 266 | 33 | 0 |
| shootout-complete | 246 | 246 | 246 | 246 | 0 |
| blocked-shot | 221 | 19 | 168 | 57 | 221 |
| faceoff | 143 | 3 | 121 | 15 | 143 |
| hit | 121 | 11 | 98 | 25 | 121 |
| giveaway | 77 | 4 | 69 | 10 | 77 |
| failed-shot-attempt | 47 | 40 | 40 | 42 | 0 |
| takeaway | 41 | 3 | 33 | 5 | 41 |

## Highest-Mismatch Games

| game_id | events | matches | mismatches | match_pct |
| --- | --- | --- | --- | --- |
| 2023020032 | 339 | 293 | 46 | 86.43 |
| 2024021193 | 342 | 297 | 45 | 86.84 |
| 2023020442 | 388 | 343 | 45 | 88.40 |
| 2023020005 | 365 | 322 | 43 | 88.22 |
| 2023020248 | 326 | 286 | 40 | 87.73 |
| 2022020472 | 365 | 325 | 40 | 89.04 |
| 2024021036 | 320 | 282 | 38 | 88.13 |
| 2023020329 | 417 | 379 | 38 | 90.89 |
| 2024020081 | 367 | 330 | 37 | 89.92 |
| 2023020473 | 324 | 288 | 36 | 88.89 |
| 2023020323 | 346 | 310 | 36 | 89.60 |
| 2022021102 | 389 | 353 | 36 | 90.75 |
| 2022020959 | 318 | 282 | 36 | 88.68 |
| 2022020297 | 364 | 328 | 36 | 90.11 |
| 2023020966 | 386 | 351 | 35 | 90.93 |
| 2023020254 | 300 | 265 | 35 | 88.33 |
| 2023020114 | 333 | 298 | 35 | 89.49 |
| 2022020629 | 277 | 242 | 35 | 87.36 |
| 2024020848 | 336 | 302 | 34 | 89.88 |
| 2023021038 | 284 | 250 | 34 | 88.03 |

## Example Mismatches

| game_id | event_idx | period | period_time_seconds | event_type | situation_strength | pbp_home | pbp_away | shift_home | shift_away | shift_code | home_goalie_pulled | away_goalie_pulled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024021312 | 58 | 1 | 748 | penalty | 5v5 | 5 | 5 | 4 | 5 | SH | False | False |
| 2024021312 | 92 | 1 | 1200 | period-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021312 | 211 | 2 | 1200 | period-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021312 | 290 | 3 | 1200 | period-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021312 | 291 | 3 | 1200 | game-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021311 | 91 | 1 | 1200 | period-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021311 | 124 | 2 | 379 | penalty | 5v5 | 5 | 5 | 5 | 4 | SH | False | False |
| 2024021311 | 130 | 2 | 439 | goal | 4v5 | 5 | 4 | 5 | 5 | EV | False | False |
| 2024021311 | 134 | 2 | 476 | penalty | 5v5 | 5 | 5 | 5 | 4 | SH | False | False |
| 2024021311 | 181 | 2 | 951 | penalty | 5v5 | 5 | 5 | 4 | 5 | SH | False | False |
| 2024021311 | 185 | 2 | 1016 | goal | 5v4 | 4 | 5 | 5 | 5 | EV | False | False |
| 2024021311 | 208 | 2 | 1200 | period-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021311 | 235 | 3 | 406 | penalty | 5v5 | 5 | 5 | 4 | 5 | SH | False | False |
| 2024021311 | 242 | 3 | 526 | goal | 5v4 | 4 | 5 | 5 | 5 | EV | False | False |
| 2024021311 | 313 | 3 | 1200 | period-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021311 | 314 | 3 | 1200 | game-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021310 | 23 | 1 | 347 | penalty | 5v5 | 5 | 5 | 4 | 5 | SH | False | False |
| 2024021310 | 57 | 1 | 1172 | penalty | 6v5 | 5 | 6 | 4 | 5 | SH | False | False |
| 2024021310 | 61 | 1 | 1200 | period-end | 5v4 | 4 | 5 | 0 | 0 |  | True | True |
| 2024021310 | 145 | 2 | 948 | stoppage | 5v5 | 5 | 5 | 5 | 4 |  | False | False |
| 2024021310 | 146 | 2 | 948 | penalty | 5v5 | 5 | 5 | 5 | 4 | SH | False | False |
| 2024021310 | 148 | 2 | 961 | penalty | 4v5 | 5 | 4 | 4 | 4 | EV | False | False |
| 2024021310 | 156 | 2 | 1081 | missed-shot | 5v4 | 4 | 5 | 5 | 5 | EV | False | False |
| 2024021310 | 165 | 2 | 1200 | period-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021310 | 250 | 3 | 1200 | period-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021310 | 251 | 3 | 1200 | game-end | 5v5 | 5 | 5 | 0 | 0 |  | True | True |
| 2024021309 | 7 | 1 | 107 | penalty | 5v5 | 5 | 5 | 4 | 5 | SH | False | False |
| 2024021309 | 18 | 1 | 161 | penalty | 5v4 | 4 | 5 | 4 | 4 | EV | False | False |
| 2024021309 | 61 | 1 | 745 | penalty | 5v5 | 5 | 5 | 5 | 4 | SH | False | False |
| 2024021309 | 72 | 1 | 942 | penalty | 5v6 | 6 | 5 | 5 | 4 | SH | False | False |

## Interpretation

A top-level `PASS` requires both complete shiftchart source coverage for the requested sample and low covered-game manpower mismatch rates. A `Covered-games status` of `PASS` means shift-derived manpower agrees with NHL play-by-play skater counts for games where shiftcharts exist. It does not validate player positioning or tactical shape. Missing shiftchart source games should be excluded from shift-derived models until source coverage is understood.
