# MoneyPuck V2 Models

Run from `Analytics/` after importing MoneyPuck tables:

```powershell
$env:NHL_DB_PASSWORD = "your_password"
.\venv\Scripts\python.exe run_models_v2.py
```

The runner writes:

```text
models/output/models_v2_run_YYYYMMDD_HHMMSS.json
```

The ASP.NET API reads the latest v2 run through:

```text
/api/analytics/v2/dashboard
/api/analytics/v2/models
/api/analytics/v2/models/{modelKey}
```

`/api/analytics/v2/dashboard` returns top rows per season so the React app stays
fast. Use the model detail endpoint or the local JSON file for full inspection.

## Model Set

- **Puck Movement Geometry**: classifies PK shots against by pre-shot movement:
  rebound, east-west, north-south downhill, diagonal, small-area, point reset,
  and slow reset.
- **Blocked-Shot Aftershock**: measures danger after a blocked shot fails to end
  pressure and the opponent gets the next recorded PK shot.
- **Goalie Control Above Expected**: combines PK GSAx with freeze, rebound,
  play-out, and play-in outcomes versus MoneyPuck expected probabilities.
- **PK Fatigue And Penalty Timing**: buckets shot danger by defending-team TOI
  and valid defending penalty-clock phase.
- **Short-Handed Offense Without Defensive Leakage**: finds 4-on-5 skaters who
  create offense while keeping on-ice xGA down.
- **Empirical-Bayes PK Player Evaluation**: adjusts player-season PK impact for
  sample size, adds approximate uncertainty ranges and trust labels, and builds
  role/outcome similar-player groups.
- **Rush / Set Defense Diagnostic**: reports the MoneyPuck `shotRush` split,
  but treats it as a subview because the current local PK rush sample is sparse.

## Scouting Outputs

The scouting page reads three season-filtered arrays from the empirical-Bayes
model:

- `trusted_pk_impact`: stronger sample-size-adjusted PK impact estimates.
- `high_upside_noisy`: interesting estimates with wider uncertainty.
- `similarity_groups`: top player anchors with closest role/outcome matches.

Impact values are per 60 minutes. Higher is better because short-handed skaters
usually lose the xG battle.

## Trust Boundaries

- V2 uses MoneyPuck shot quality and outcome probabilities as the analytics
  source of truth.
- Movement buckets are derived from shot and last-event coordinates, not player
  tracking.
- The models describe what happened. They should not be framed as causal claims.
- The empirical-Bayes model is a practical shrinkage layer, not a full MCMC
  Bayesian model.
- The old NHL API models remain useful background, especially for event windows,
  but they are not the v2 modeling foundation.
