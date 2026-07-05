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

Model files are split by responsibility:

- `moneypuck_pk_models.py`: core PK movement, goalie, fatigue, after-block, and
  player-season models.
- `special_teams_matchups.py`: PP attack profiles, PK leak profiles, matchup
  cards, and heat-map bins.
- `player_tags.py`: dynamic player-passport tags generated from season
  percentiles, samples, confidence, and explicit rule explanations.
- `common.py`: JSON-safe DataFrame output helpers shared by model modules.

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
- **Dynamic PK Player Tags**: turns the season scouting metrics into auditable
  tags such as low-event PK forward, counterattack pressure valve, block-and-clear
  defender, penalty risk, trusted sample, and do-not-overread.
- **Rush / Set Defense Diagnostic**: reports the MoneyPuck `shotRush` split,
  but treats it as a subview because the current local PK rush sample is sparse.
- **Special Teams Matchup Profiles**: turns shot geometry into PP attack
  profiles, PK leak profiles, matchup cards, and compact danger heat-map bins.
  Team styles are compared against season-specific league baselines. This is
  the base for future game-plan and scouting-preview pages.

## Scouting Outputs

The scouting page reads three season-filtered arrays from the empirical-Bayes
model:

- `trusted_pk_impact`: stronger sample-size-adjusted PK impact estimates.
- `high_upside_noisy`: interesting estimates with wider uncertainty.
- `similarity_groups`: top player anchors with closest role/outcome matches.
- `playerTagProfiles`: latest-season player passports with fired tags, summary
  sentence, strengths, risks, and trust level.
- `playerTagDictionary`: compact definitions for each tag rule.

Impact values are per 60 minutes. Higher is better because short-handed skaters
usually lose the xG battle.

## Trust Boundaries

- V2 uses MoneyPuck shot quality and outcome probabilities as the analytics
  source of truth.
- Movement buckets are derived from shot and last-event coordinates, not player
  tracking.
- Matchup profiles describe public-data style fit. They do not prove exact PP
  formations or PK systems.
- The models describe what happened. They should not be framed as causal claims.
- The empirical-Bayes model is a practical shrinkage layer, not a full MCMC
  Bayesian model.
- Player tags are rules over public aggregates. They explain why a player is
  worth a look, but they are not scouting grades or tracking-based roles.
- The old NHL API models remain useful background, especially for event windows,
  but they are not the v2 modeling foundation.
