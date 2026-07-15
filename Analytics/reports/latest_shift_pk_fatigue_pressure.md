# Source-Covered PK Fatigue Pressure

Generated: 2026-07-15T01:04:51

## Oldest Active PK Shift

| bucket | pk_team_events | shot_attempts_against | shot_attempts_per_100_events | pressure_ci_low | pressure_ci_high | unblocked_shot_attempts | shots_with_xg | xg_match_rate | xg_against | xg_per_100_events | xg_trust | trust |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 00-29 | 85110 | 22674 | 26.64 | 26.34 | 26.94 | 17052 | 13747 | 80.62 | 953.274 | 1.12 | incomplete | descriptive |
| 30-44 | 34727 | 17147 | 49.38 | 48.85 | 49.9 | 12637 | 10527 | 83.3 | 759.407 | 2.187 | incomplete | descriptive |
| 45-59 | 26202 | 14864 | 56.73 | 56.13 | 57.33 | 10759 | 9391 | 87.29 | 692.769 | 2.644 | incomplete | descriptive |
| 60+ | 40913 | 25361 | 61.99 | 61.52 | 62.46 | 17978 | 16272 | 90.51 | 1323.851 | 3.236 | incomplete | descriptive |

## Shortest Rest Among Active PK Skaters

| bucket | pk_team_events | shot_attempts_against | shot_attempts_per_100_events | pressure_ci_low | pressure_ci_high | unblocked_shot_attempts | shots_with_xg | xg_match_rate | xg_against | xg_per_100_events | xg_trust | trust |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 00-14 | 26773 | 10496 | 39.2 | 38.62 | 39.79 | 7588 | 6640 | 87.51 | 508.179 | 1.898 | incomplete | descriptive |
| 15-29 | 41272 | 17572 | 42.58 | 42.1 | 43.05 | 12864 | 11062 | 85.99 | 831.32 | 2.014 | incomplete | descriptive |
| 30-44 | 47995 | 21253 | 44.28 | 43.84 | 44.73 | 15571 | 13130 | 84.32 | 979.23 | 2.04 | incomplete | descriptive |
| 45+ | 70912 | 30725 | 43.33 | 42.96 | 43.69 | 22403 | 19105 | 85.28 | 1410.572 | 1.989 | incomplete | descriptive |

## Interpretation

The unit is one source-covered PK team-event. Shift age uses the oldest active PK skater; rest uses the shortest game-clock gap among active PK skaters. Intermission duration is excluded, so rest is not wall-clock recovery. Rates describe non-goal shot-attempt pressure per 100 recorded play-by-play events. They are not possession-adjusted, opponent-adjusted, score-adjusted, or causal.

Goal events are excluded because NHL shift segments can start or stop at the scoring timestamp and reset apparent shift age. Pressure intervals are 95% Wilson intervals. Rows below 100 PK team-events are labeled `small_sample`. xG is joined from MoneyPuck for unblocked shots using the separately validated game, period, shooting-team, and elapsed-time-within-two-seconds contract. Blocked attempts remain in pressure counts but do not receive fabricated xG.

Bucket-level xG is labeled `incomplete` below a 95% unblocked-shot match rate. Incomplete xG can be used as directional audit evidence only, not as a trusted fatigue estimate.
