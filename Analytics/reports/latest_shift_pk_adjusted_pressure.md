# Adjusted Source-Covered PK Pressure

Generated: 2026-07-15T01:07:44

Rows: `186951`
Games: `3878`
PK teams: `33`
Next-shot outcomes within 10 seconds: `32979`
Outcome rate: `17.64%`
Model converged: `True`
Game clusters: `3878`
Estimated parameters: `85`
Rows per parameter: `2199.4`

## Adjusted Shift-Age Estimates

| shift_age_bucket | adjusted_next_shot_probability | adjusted_per_100_events | odds_ratio_vs_00_29 | or_ci_low | or_ci_high | p_value |
| --- | --- | --- | --- | --- | --- | --- |
| 00-29 | 0.159 | 15.878 | 1 |  |  |  |
| 30-44 | 0.173 | 17.255 | 1.112 | 1.072 | 1.154 | 0 |
| 45-59 | 0.188 | 18.802 | 1.245 | 1.196 | 1.296 | 0 |
| 60+ | 0.202 | 20.18 | 1.369 | 1.321 | 1.419 | 0 |

## Horizon Sensitivity

| horizon_seconds | shift_age_bucket | adjusted_per_100_events | odds_ratio_vs_00_29 | or_ci_low | or_ci_high | p_value |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 00-29 | 8.117 | 1 |  |  |  |
| 5 | 30-44 | 8.85 | 1.103 | 1.05 | 1.157 | 0 |
| 5 | 45-59 | 9.708 | 1.225 | 1.162 | 1.292 | 0 |
| 5 | 60+ | 10.712 | 1.374 | 1.311 | 1.44 | 0 |
| 10 | 00-29 | 15.878 | 1 |  |  |  |
| 10 | 30-44 | 17.255 | 1.112 | 1.072 | 1.154 | 0 |
| 10 | 45-59 | 18.802 | 1.245 | 1.196 | 1.296 | 0 |
| 10 | 60+ | 20.18 | 1.369 | 1.321 | 1.419 | 0 |
| 15 | 00-29 | 21.606 | 1 |  |  |  |
| 15 | 30-44 | 23.115 | 1.1 | 1.064 | 1.138 | 0 |
| 15 | 45-59 | 25.015 | 1.234 | 1.189 | 1.281 | 0 |
| 15 | 60+ | 26.12 | 1.316 | 1.274 | 1.36 | 0 |

## PP Offensive-Zone Control Proxy

Rows: `50666`; games: `3822`; outcomes: `13554`; model converged: `True`.

| shift_age_bucket | adjusted_next_shot_probability | adjusted_per_100_events | odds_ratio_vs_00_29 | or_ci_low | or_ci_high | p_value |
| --- | --- | --- | --- | --- | --- | --- |
| 00-29 | 0.246 | 24.65 | 1 |  |  |  |
| 30-44 | 0.264 | 26.372 | 1.1 | 1.037 | 1.167 | 0.001 |
| 45-59 | 0.275 | 27.476 | 1.167 | 1.095 | 1.244 | 0 |
| 60+ | 0.296 | 29.584 | 1.302 | 1.23 | 1.379 | 0 |

This sensitivity keeps only events explicitly owned by the PP team in its offensive zone. It is a conservative high-confidence control proxy, not a complete possession definition. The reduced model controls rest, penalty elapsed time, period, score, and current event type with game-clustered uncertainty; team/opponent effects are omitted to keep the smaller fit estimable.

## Model

`next_shot_against_10 ~ C(shift_age_bucket, Treatment(reference='00-29')) + shortest_rest_seconds + penalty_elapsed_seconds + period + score_diff + C(zone) + C(current_event_type) + C(pk_team_id) + C(opponent_team_id)`

The outcome is whether the opponent records the next shot attempt within ten seconds of the current source-covered PK event. Adjusted probabilities are average model predictions after setting every row to each shift-age bucket while preserving its observed controls. Standard errors are clustered by game.

## Limits

This is an adjusted association, not a causal fatigue estimate. It controls measured penalty elapsed time, shortest game-clock shift gap, period, running score differential, current event zone/type, PK team, and opponent. The rest control excludes real intermission duration and is not wall-clock recovery. It does not observe player positioning, tactical formation, deployment intent, exact possession state, substitutions between recorded events, or unmeasured opponent quality within team fixed effects.

Model fit: AIC `155619.0`; residual degrees of freedom `186866`. The result is labeled a promising adjusted association only; causal language remains blocked.
