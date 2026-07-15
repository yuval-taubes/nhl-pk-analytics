# MoneyPuck Shot Alignment

Generated: 2026-07-15T01:03:27

Status: **PASS**

Join convention: NHL full game IDs are mapped to MoneyPuck by `season = left 4 digits of NHL season` and `game_id = nhl_game_id % 1000000`.
MoneyPuck excludes blocked shots, so only NHL shot-on-goal, missed-shot, and goal rows are matched. Shots are matched by game, period, shooting team, and game-elapsed time within two seconds.

NHL unblocked shot rows checked: `342924`
Matched MoneyPuck shots: `340834`
Match rate: `99.39%`
Goal flag matches: `340672`

## Coordinate Candidate Summary

| matched_shots | avg_abs_x_raw | avg_abs_y_raw | avg_abs_x_adjusted | avg_abs_y_adjusted | avg_abs_x_arena_adjusted | avg_abs_y_arena_adjusted | avg_abs_x_mirrored_adjusted | avg_abs_y_flipped_adjusted | avg_abs_x_magnitude_adjusted | avg_abs_y_magnitude_adjusted | avg_abs_x_magnitude_arena | avg_abs_y_magnitude_arena |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 340834 | 61.24 | 0.56 | 65.16 | 16.68 | 61.27 | 0.90 | 58.50 | 16.49 | 0.34 | 0.54 | 1.08 | 0.88 |

## Time Delta Summary

| time_delta | shots |
| --- | --- |
| 0 | 340614 |
| 1 | 139 |
| 2 | 81 |

## Largest Adjusted-Coordinate Differences

| nhl_game_id | event_idx | period | period_time_seconds | event_type | shooting_team_code | mp_shot_id | mp_time_seconds | nhl_x_norm | nhl_y_norm | nhl_x_centered | nhl_y_centered | mp_x_adjusted | mp_y_adjusted | mp_x_arena_adjusted | mp_y_arena_adjusted | adjusted_x_delta | adjusted_y_delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023020354 | 83 | 1 | 870 | shot-on-goal | OTT | 150855 | 870 | 1 | 37 | -99 | -5.5 | 100.0 | -6.0 | 100.0 | -6.0 | 199.0 | 0.5 |
| 2023021053 | 86 | 1 | 1034 | goal | NJD | 212190 | 1034 | 1 | 50 | -99 | 7.5 | 100.0 | 7.0 | 100.0 | 7.0 | 199.0 | 0.5 |
| 2024021074 | 194 | 2 | 875 | shot-on-goal | TBL | 91611 | 2075 | 1 | 37 | -99 | -5.5 | 100.0 | -5.0 | 100.0 | -5.0 | 199.0 | 0.5 |
| 2022020640 | 300 | 3 | 847 | shot-on-goal | CHI | 297358 | 3247 | 1 | 25 | -99 | -17.5 | 99.0 | 17.0 | -99.0 | -17.0 | 198.0 | 34.5 |
| 2024020663 | 56 | 1 | 764 | shot-on-goal | VGK | 56214 | 764 | 1 | 60 | -99 | 17.5 | 99.0 | -17.0 | -99.0 | 17.0 | 198.0 | 34.5 |
| 2024020415 | 258 | 3 | 538 | shot-on-goal | CAR | 35264 | 2938 | 1 | 26 | -99 | -16.5 | 99.0 | 16.0 | -99.0 | -16.0 | 198.0 | 32.5 |
| 2023021151 | 172 | 2 | 632 | missed-shot | NYI | 220564 | 1832 | 1 | 58 | -99 | 15.5 | 99.0 | -15.0 | -99.0 | 15.0 | 198.0 | 30.5 |
| 2022020432 | 113 | 2 | 107 | goal | PHI | 279584 | 1307 | 1 | 28 | -99 | -14.5 | 99.0 | 14.0 | -99.0 | -14.0 | 198.0 | 28.5 |
| 2023021058 | 111 | 1 | 1011 | shot-on-goal | CHI | 212601 | 1011 | 1 | 28 | -99 | -14.5 | 99.0 | 14.0 | -99.0 | -14.0 | 198.0 | 28.5 |
| 2024020994 | 11 | 1 | 88 | shot-on-goal | DAL | 84909 | 88 | 1 | 56 | -99 | 13.5 | 99.0 | -13.0 | -99.0 | 13.0 | 198.0 | 26.5 |
| 2022021184 | 166 | 2 | 619 | shot-on-goal | EDM | 345124 | 1819 | 1 | 56 | -99 | 13.5 | 99.0 | -13.0 | -99.0 | 13.0 | 198.0 | 26.5 |
| 2022021062 | 151 | 2 | 1030 | shot-on-goal | COL | 334646 | 2230 | 1 | 54 | -99 | 11.5 | 99.0 | -11.0 | -99.0 | 11.0 | 198.0 | 22.5 |
| 2024020638 | 83 | 1 | 1063 | shot-on-goal | MTL | 54001 | 1063 | 1 | 31 | -99 | -11.5 | 99.0 | 11.0 | -99.0 | -11.0 | 198.0 | 22.5 |
| 2023020788 | 82 | 1 | 1090 | shot-on-goal | PIT | 188782 | 1090 | 1 | 52 | -99 | 9.5 | 99.0 | -9.0 | -99.0 | 9.0 | 198.0 | 18.5 |
| 2024020738 | 193 | 2 | 941 | missed-shot | NYR | 62571 | 2141 | 1 | 33 | -99 | -9.5 | 99.0 | 9.0 | -99.0 | -9.0 | 198.0 | 18.5 |
| 2023020190 | 128 | 2 | 60 | shot-on-goal | OTT | 136594 | 1260 | 1 | 33 | -99 | -9.5 | 99.0 | 9.0 | -99.0 | -9.0 | 198.0 | 18.5 |
| 2024020433 | 302 | 3 | 1174 | goal | PIT | 36855 | 3574 | 1 | 35 | -99 | -7.5 | 99.0 | 8.0 | -99.0 | -8.0 | 198.0 | 15.5 |
| 2022020635 | 211 | 3 | 184 | shot-on-goal | VGK | 296740 | 2584 | 1 | 36 | -99 | -6.5 | 99.0 | 6.0 | -99.0 | -6.0 | 198.0 | 12.5 |
| 2023020778 | 262 | 3 | 979 | shot-on-goal | DET | 188028 | 3379 | 1 | 37 | -99 | -5.5 | 99.0 | 5.0 | -99.0 | -5.0 | 198.0 | 10.5 |
| 2022020094 | 78 | 1 | 923 | shot-on-goal | EDM | 250391 | 923 | 1 | 37 | -99 | -5.5 | 99.0 | 5.0 | -99.0 | -5.0 | 198.0 | 10.5 |
| 2022021049 | 99 | 1 | 1024 | shot-on-goal | SEA | 333512 | 1024 | 1 | 42 | -99 | -0.5 | 99.0 | 0.0 | -99.0 | 0.0 | 198.0 | 0.5 |
| 2024020386 | 124 | 2 | 103 | shot-on-goal | VGK | 32812 | 1303 | 1 | 57 | -99 | 14.5 | 99.0 | 14.0 | 99.0 | 14.0 | 198.0 | 0.5 |
| 2022020911 | 204 | 2 | 873 | shot-on-goal | CAR | 321489 | 2073 | 1 | 28 | -99 | -14.5 | 99.0 | -14.0 | 99.0 | -14.0 | 198.0 | 0.5 |
| 2023021111 | 139 | 2 | 514 | shot-on-goal | COL | 217139 | 1714 | 1 | 30 | -99 | -12.5 | 99.0 | -12.0 | 99.0 | -12.0 | 198.0 | 0.5 |
| 2023020789 | 144 | 2 | 435 | missed-shot | WSH | 188875 | 1635 | 1 | 36 | -99 | -6.5 | 99.0 | -7.0 | 99.0 | -7.0 | 198.0 | 0.5 |

## Interpretation

This report is a convention finder as much as a validator. Direct signed X deltas can be large when the two sources encode attack direction differently. The magnitude columns test whether the shot geometry itself agrees independent of rink side. If all coordinate deltas are large, local coordinate normalization should be audited before using shot location models as trusted evidence.
