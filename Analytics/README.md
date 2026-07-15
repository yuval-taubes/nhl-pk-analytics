# Analytics Model Guide

Last updated: 2026-07-15

This folder is the modeling layer for the penalty-kill project. It turns NHL
play-by-play and MoneyPuck CSV data into validation reports, model outputs, and
scouting tables.

The current v2 launch run completed successfully:

```text
models/output/models_v2_run_20260605_152014.json
```

Legacy `models_2_10_run_*.json` files remain useful for the older NHL API model
pages. Generated files under `models/output/` are ignored by Git because they
are local runs. The code, committed snapshot, and interpretation below are the
durable project documentation.

The published frontend uses a committed compact snapshot at
`Frontend/public/data/dashboard.json`, so reviewers can inspect the site without
recreating the local database.

## MoneyPuck V2 Layer

The active expansion path lives in `moneypuck/`, `models_v2/`, and
`run_models_v2.py`. It imports MoneyPuck downloadable CSVs into `mp_*` tables
and writes `models/output/models_v2_run_*.json` for the API and frontend.

The v2 architecture is split by responsibility:

- `moneypuck/`: source discovery, CSV import, schema, and validation.
- `models_v2/moneypuck_pk_models.py`: core PK shot, goalie, fatigue, and
  player-season models.
- `models_v2/special_teams_matchups.py`: PP attack profiles, PK leak profiles,
  matchup cards, and aggregate heat-map bins.
- `models_v2/player_tags.py`: dynamic player passport tags with reasons,
  metrics, confidence, sample notes, and caveats.
- `models_v2/common.py`: shared JSON-safe DataFrame output helpers.

The v2 scouting layer now includes:

- season-specific skater and goalie views;
- empirical-Bayes PK player impact estimates with approximate uncertainty;
- trust labels such as `Strong signal`, `Useful signal`, and `Too noisy`;
- similar-player groups based on role and outcome aggregates;
- auditable player tags that separate strengths, risks, style, and trust;
- inferred PP attack and PK leak profiles from MoneyPuck shot geometry.

For commands and model definitions, see `Analytics/moneypuck/README.md` and
`Analytics/models_v2/README.md`.

## What The Data Can Support

The current database is good for:

- Possession-level PK and PP outcomes.
- Entry type outcomes, including controlled entries and dump-ins.
- xG in short windows after entries, clears, and faceoffs.
- Faceoff winner/loss effects, because faceoffs have explicit event participants.
- Tagged player-event scouting, such as blocks, hits, takeaways, giveaways, penalties, and faceoffs.

The current database should not be used for:

- True on-ice player impact.
- Forecheck shape, number of forecheckers, or aggressive/passive structure.
- Gap control or net-front coverage from player positioning.
- Per-60 player rates without shift/TOI data.
- Off-ice player comparison.

That is why several models have been reframed from "on-ice tactical impact" to "supported event and possession profiles."


## Shift And MoneyPuck Validation

The first shift/on-ice trust checks live in `diagnostics/validate_shift_and_moneypuck_alignment.py`.

Run from the repository root after reprocessing a validation batch:

```powershell
$env:NHL_DB_PASSWORD = "<local password>"
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\scan_shift_availability.py --game-limit 50
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\validate_shift_and_moneypuck_alignment.py --game-limit 50
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\shift_pk_exposure.py --game-limit 50
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\shift_pk_fatigue_pressure.py
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\shift_pk_adjusted_pressure.py
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\audit_shift_possession_coverage.py
```

The scripts write:

- `Analytics/reports/latest_shift_availability.md`
- `Analytics/reports/latest_shift_availability.csv`
- `Analytics/reports/latest_shift_on_ice_validation.md`
- `Analytics/reports/latest_moneypuck_shot_alignment.md`
- `Analytics/reports/latest_shift_pk_exposure.md`
- `Analytics/reports/latest_shift_pk_player_exposure.csv`
- `Analytics/reports/latest_shift_pk_shift_age_buckets.csv`
- `Analytics/reports/latest_shift_pk_fatigue_pressure.md`
- `Analytics/reports/latest_shift_pk_fatigue_by_shift_age.csv`
- `Analytics/reports/latest_shift_pk_fatigue_by_rest.csv`
- `Analytics/reports/latest_shift_pk_adjusted_pressure.md`
- `Analytics/reports/latest_shift_pk_adjusted_pressure.json`
- `Analytics/reports/latest_shift_pk_adjusted_pressure_estimates.csv`
- `Analytics/reports/latest_shift_pk_adjusted_pressure_sensitivity.csv`
- `Analytics/reports/latest_shift_pk_pp_control_sensitivity.csv`
- `Analytics/reports/latest_shift_possession_coverage.md`
- `Analytics/reports/latest_shift_possession_coverage_by_game.csv`

Current full-census result: top-level shift/on-ice validation is `REVIEW` only because 57 of 3,936 games have no NHL shiftchart source rows. The `3,879` source-covered games pass: `1,224,084/1,224,084` events have manpower rows, with a `1.05%` mismatch rate on model-safe event types. The `4.85%` all-event mismatch rate is concentrated in penalty timing, period/game-end rows, stoppages, goal timestamps, and goalie-pulled bookkeeping, so those cases remain review material rather than the primary modeling gate.

The full scanner confirms one bounded source gap: games `2024021235-2024021291` return zero rows while all other ingested games are source-covered. Treat shift/on-ice models as source-covered only, and keep source coverage counts next to any TOI, on-ice, or fatigue output.

Use `--persist` to write verified scanner results to `game_shift_source_status`. The scanner also writes `latest_shift_availability.json`, which the API exposes as `shiftCoverage` and the frontend shows on the Data Honesty page. A request error remains distinct from a successful zero-row response.

```powershell
$env:NHL_DB_PASSWORD='YOUR_PASSWORD'
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\scan_shift_availability.py --game-limit 50 --persist
```

For a resumable full census, scan only unchecked games and commit in small batches. A rerun continues from the remaining `not_checked` rows. Use a dedicated report stem so the UI's latest-sample artifact is not replaced.

```powershell
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\scan_shift_availability.py --not-checked --persist --persist-batch-size 25 --report-stem shift_availability_full_census
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\scan_shift_availability.py --retry-errors --persist --persist-batch-size 25 --report-stem shift_availability_error_retry
```

The completed 2026-07-13 census covers all `3,936` ingested games: `3,879` (`98.55%`) returned shift rows and `57` (`1.45%`) returned successful zero-row responses. There are no unchecked games or request errors. The 57 unavailable games are exactly the previously mapped `2024021235-2024021291` block. Source availability is not the same as feature readiness: only backfilled and validated games enter shift-derived modeling.

MoneyPuck alignment passed on `340,834/342,924` unblocked NHL shot rows (`99.39%`). NHL full game IDs map to MoneyPuck compact IDs with `season = left 4 digits of NHL season` and `game_id = nhl_game_id % 1000000`; shot matching uses game-elapsed time, not period-elapsed time. Coordinate magnitudes align tightly (`0.34 ft` average X magnitude delta, `0.54 ft` average Y magnitude delta), while signed rink direction still needs explicit convention handling before location models make side-specific claims.

The source-covered PK exposure diagnostic remains descriptive. `latest_shift_pk_exposure.md` summarizes all `3,879` shift-covered games; the shift-age bucket table excludes goals because NHL shiftchart segments often start or stop at scoring timestamps, which can reset goal-event shift age to zero. Goal exposures remain in the player table as outcomes, not as fatigue evidence.

`pk_shift_player_event_features` is the shared database feature view. It requires `source_status = 'available'` and carries player, team, event, shift duration, shift age, rest before shift, PK state, and the source check timestamp. `rest_before_shift_seconds` is a game-clock gap between recorded shifts; it excludes the real intermission duration and must not be described as wall-clock recovery. Use this view for new NHL-shift-derived models instead of rebuilding interval joins independently.

### Season coverage and focused gaps

Run a stratified source scan across each ingested season:

```powershell
$env:NHL_DB_PASSWORD='YOUR_PASSWORD'
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\scan_shift_availability_by_season.py --games-per-season 20 --persist
```

The 2026-07-12 sample found `20/20` games available in 2022-23, `20/20` in 2023-24, and `19/20` in 2024-25. This means the source is broadly useful and the latest-50 result should not be generalized to every season. A focused scan mapped one exact 2024-25 source hole: games `2024021235` through `2024021291` returned zero rows, while `2024021230-1234` and `2024021292-1312` returned normal shift counts. See `latest_shift_availability_by_season.md` and `shift_availability_2024021230_2024021312.csv`.

Focused range scans use database-backed game IDs:

```powershell
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\scan_shift_availability.py --game-id-min 2024021230 --game-id-max 2024021312 --persist --report-stem shift_availability_2024021230_2024021312
```

### Source-covered fatigue pressure

```powershell
$env:NHL_DB_PASSWORD='YOUR_PASSWORD'
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\shift_pk_fatigue_pressure.py
```

After the full source-certified backfill, all `3,879` available games contain shifts. The PK feature view contains roughly `800,000` player-event rows across `1,138` players. The descriptive team-event result shows non-goal shot-attempt pressure rising with the oldest active PK shift: `26.64` attempts per 100 recorded events at 0-29 seconds, `49.38` at 30-44, `56.73` at 45-59, and `61.99` at 60+. Shortest-rest results remain weaker and non-monotonic at `39.20`, `42.58`, `44.28`, and `43.33` attempts per 100 events.

This is an exploratory pressure association, not a fatigue effect estimate. It is not possession-, opponent-, score-, zone-, or event-mix-adjusted. Goals are excluded because scoring timestamps can reset shift age. MoneyPuck xG is joined with the validated game/period/team/time contract, but bucket-level match coverage is only `78-95%`, below the 95% trust gate in every bucket. The xG direction is therefore audit evidence only: `1.33`, `2.38`, `2.84`, and `3.59` xG per 100 events across increasing shift-age buckets.

### Adjusted next-shot pressure

```powershell
$env:NHL_DB_PASSWORD='YOUR_PASSWORD'
.\Analytics\venv\Scripts\python.exe .\Analytics\diagnostics\shift_pk_adjusted_pressure.py
```

The adjusted diagnostic asks whether the opponent records the next shot attempt within ten seconds of each source-covered PK event. It controls shortest rest, penalty elapsed time, period, running score differential, current zone and event type, PK team, and opponent, with standard errors clustered by game.

Across `186,951` event states from `3,878` games, adjusted next-shot risk is `15.88%`, `17.26%`, `18.80%`, and `20.18%` across increasing shift-age buckets. Relative to 0-29 seconds, odds ratios are `1.11`, `1.25`, and `1.37`; all clustered intervals exclude 1. The model converged with 3,878 game clusters, 85 parameters, and 2,199 rows per parameter.

Horizon sensitivity preserves direction and all older-shift intervals exclude the reference at 5, 10, and 15 seconds in the full sample. Treat this as a promising adjusted sustained-pressure association, not proof that fatigue itself causes the next shot. Tracking, deployment intent, exact possession state, and substitutions between recorded events remain unobserved.

The existing reconstructed `possessions` table is not suitable as a complete conditioning layer for this model. It covers only `26,250/186,952` source-covered PK team-events (`14.04%`) because it intentionally stores selected offensive-zone sequences that start with detected entries, OZ faceoffs, or turnovers and survive a meaningful-activity filter. There are no ambiguous overlaps, but conditioning on that table would select a narrow subset.

As a conservative sensitivity, the adjusted model also restricts to events explicitly owned by the PP team in its offensive zone. This high-confidence control proxy contains `50,666` rows across `3,822` games. Adjusted 10-second next-shot risk rises from `24.65%` at 0-29 seconds to `26.37%`, `27.48%`, and `29.58%`; odds ratios for all older buckets exclude 1 with game-clustered intervals. This strengthens the sustained-pressure association but still does not provide literal puck possession or tracking context.
## How To Run

From `Analytics/`:

```powershell
$env:NHL_DB_HOST = "localhost"
$env:NHL_DB_NAME = "nhl_pk_analytics"
$env:NHL_DB_USER = "postgres"
$env:NHL_DB_PASSWORD = "<local password>"
$env:NHL_DB_PORT = "5432"
.\venv\Scripts\python.exe run_models.py
```

The runner writes individual model JSON files plus one combined run file to `models/output/`.

## Legacy NHL API Findings

These findings come from the successful 2026-05-15 legacy run. They remain in
the project as background context, while the 2.0 frontend leads with MoneyPuck
shot quality and season-by-season v2 scouting.

### Model 2: PK Offensive-Zone Foray Risk-Reward

Sample: 1,224 PK offensive-zone forays.

The strongest pattern is that PK offensive-zone activity has positive immediate xG value in this dataset, while measured counterattack risk in the next 30 seconds is small.

Summary by foray type:

| Foray type | Count | PK xG | Counter xG against | Net xG |
| --- | ---: | ---: | ---: | ---: |
| Controlled foray | 31 | 0.056 | 0.003 | 0.053 |
| Dump-in foray | 19 | 0.177 | 0.001 | 0.176 |
| OZ faceoff foray | 882 | 0.073 | 0.007 | 0.066 |
| Turnover foray | 292 | 0.097 | 0.003 | 0.094 |

Interpretation: short-handed OZ chances are not showing a large immediate counterattack penalty by this measure. The model cannot tell us how many PK skaters committed up ice, only what happened after PK OZ possessions.

### Model 3: Intentional Clearance For OZ Faceoff

Sample: 18,338 PK offensive-zone situations.

Keeping play alive was slightly positive over the next 20 seconds, while inferred out-of-play/OZ-faceoff situations were negative.

| Path | Count | PK xG next 20s | PP xG next 20s | Net xG |
| --- | ---: | ---: | ---: | ---: |
| Maintain play | 17,508 | 0.025 | 0.024 | 0.001 |
| Out of play | 830 | 0.020 | 0.035 | -0.015 |

The estimated PK OZ faceoff win probability was 45.2 percent, and the estimated EV of forcing the OZ faceoff was -0.024 net xG.

Interpretation: the data does not support treating intentional out-of-play as a free reset. If the PK can safely keep play alive, that appears better on average than creating an OZ faceoff.

### Model 4: PK Entry Defense Outcomes

Sample: 385 PP entries against the PK.

Dump-in entries against the PK produced more xGA per entry than controlled entries in this run.

| Entry type | Count | Clear rate | Goal rate | xGA per entry | xGA/60 observed possession |
| --- | ---: | ---: | ---: | ---: | ---: |
| Controlled | 151 | 6.6% | 7.9% | 0.110 | 0.187 |
| Dump-in | 234 | 8.1% | 13.7% | 0.189 | 0.376 |

Interpretation: this is an outcome table, not a forecheck-structure model. It says what happened after observed entry types, but it cannot identify whether the PK was passive, aggressive, 1-1-2, wedge-plus-one, etc.

### Model 5: PK Defensive-Zone Faceoff Value

Sample: 17,665 PK DZ faceoffs.

PK faceoff wins were associated with about -0.027 xGA in the next 20 seconds relative to matched losses. The simple observed split is similar:

| Outcome | Count | Avg xGA next 20s | Shot rate next 20s |
| --- | ---: | ---: | ---: |
| Loss | 9,606 | 0.049 | 59.5% |
| Win | 8,059 | 0.021 | 25.9% |

Interpretation: this is one of the strongest tactical findings. DZ PK faceoff wins sharply reduce immediate danger.

### Model 6: PK Forward Defensive Event Profile

Sample: 15,001 tagged forward defensive events. Eligible players: 123 with at least 50 events.

This model ranks forwards by directly tagged PK events, not by all shifts played.

Top positive-event profiles:

| Player | Events | Takeaway rate | Positive event rate | Negative event rate |
| --- | ---: | ---: | ---: | ---: |
| Aleksander Barkov | 73 | 32.9% | 94.5% | 5.5% |
| Alex Tuch | 100 | 34.0% | 94.0% | 6.0% |
| Chandler Stephenson | 56 | 37.5% | 92.9% | 7.1% |
| Mark Stone | 50 | 38.0% | 92.0% | 8.0% |
| Noah Cates | 67 | 31.3% | 91.0% | 9.0% |

Interpretation: these are forwards who show up well when they are tagged on PK defensive events. This does not prove they suppress shots while on the ice.

### Model 7: PK Defenseman Disruption Events

Sample: 20,500 tagged defenseman events. Eligible players: 152 with at least 50 events.

Top disruption-event profiles:

| Player | Events | Block rate | Disruption rate | Negative event rate |
| --- | ---: | ---: | ---: | ---: |
| Chad Ruhwedel | 66 | 34.8% | 97.0% | 3.0% |
| Noah Juulsen | 80 | 62.5% | 96.3% | 3.8% |
| Alexandre Carrier | 115 | 66.1% | 93.9% | 6.1% |
| Jonas Brodin | 100 | 72.0% | 93.0% | 7.0% |
| Ryan Pulock | 99 | 71.7% | 92.9% | 7.1% |

Interpretation: this is a direct-event disruption profile. It should be used for scouting tendencies, not for full defensive impact.

### Model 8: PK Forward Discipline And Blocks

Sample: 11,792 tagged forward block/discipline events. Eligible players: 93 with at least 50 events.

Top forward block-rate profiles:

| Player | Events | Block rate | Takeaway rate | Penalty/giveaway rate |
| --- | ---: | ---: | ---: | ---: |
| Garnet Hathaway | 74 | 73.0% | 8.1% | 18.9% |
| Luke Glendening | 63 | 69.8% | 11.1% | 19.0% |
| Ryan Poehling | 67 | 68.7% | 19.4% | 11.9% |
| Noel Acciari | 102 | 68.6% | 17.6% | 13.7% |
| J.T. Compher | 58 | 67.2% | 10.3% | 22.4% |

Lowest penalty/giveaway profiles:

| Player | Events | Block rate | Takeaway rate | Penalty/giveaway rate |
| --- | ---: | ---: | ---: | ---: |
| Aleksander Barkov | 58 | 51.7% | 41.4% | 6.9% |
| Alex Tuch | 77 | 48.1% | 44.2% | 7.8% |
| Alexander Wennberg | 71 | 47.9% | 42.3% | 9.9% |
| Noah Cates | 58 | 53.4% | 36.2% | 10.3% |
| Adam Henrique | 77 | 62.3% | 27.3% | 10.4% |

Interpretation: this separates forwards who are block-heavy from forwards who are low-risk and takeaway-heavy.

### Model 9: PK Center Faceoff Value

Sample: 15,454 player-faceoff rows. Eligible players: 117 with at least 50 faceoffs in a season.

Top center seasons by estimated faceoff value added:

| Player | Season | Faceoffs | Win rate | Faceoff value added |
| --- | ---: | ---: | ---: | ---: |
| Kevin Stenlund | 20242025 | 154 | 62.3% | 0.0128 |
| Colton Sissons | 20222023 | 215 | 53.5% | 0.0087 |
| Patrice Bergeron | 20222023 | 148 | 56.1% | 0.0078 |
| Michael McLeod | 20222023 | 103 | 58.3% | 0.0065 |
| Jean-Gabriel Pageau | 20242025 | 92 | 58.7% | 0.0060 |

Interpretation: center faceoff value is one of the more reliable player-level models because faceoff participants are explicitly tagged.

### Model 10: PK Defenseman Shot Blocks

Sample: 10,781 PK defenseman blocked-shot rows. Eligible players: 47 with at least 75 blocked shots.

Top average blocked-xG profiles:

| Player | Blocks | Avg blocked xG | High-danger block rate | Avg block distance |
| --- | ---: | ---: | ---: | ---: |
| Brayden McNabb | 122 | 0.026 | 91.8% | 17.2 ft |
| Ian Cole | 119 | 0.026 | 90.8% | 18.0 ft |
| Travis Sanheim | 82 | 0.025 | 91.5% | 17.0 ft |
| Mike Matheson | 106 | 0.024 | 91.5% | 18.2 ft |
| Alexandre Carrier | 76 | 0.024 | 93.4% | 17.9 ft |

Top high-danger block-rate profiles:

| Player | Blocks | Avg blocked xG | High-danger block rate | Avg block distance |
| --- | ---: | ---: | ---: | ---: |
| Ryan McDonagh | 99 | 0.020 | 98.0% | 18.4 ft |
| MacKenzie Weegar | 99 | 0.020 | 97.0% | 18.9 ft |
| Rasmus Andersson | 79 | 0.019 | 96.2% | 19.7 ft |
| Chris Tanev | 131 | 0.021 | 95.4% | 19.4 ft |
| J.J. Moser | 83 | 0.021 | 95.2% | 18.5 ft |

Interpretation: this is a shot-block profile, not a net-front coverage model. It identifies defensemen tagged on valuable blocked shots.

## Practical Takeaways

1. MoneyPuck v2 is the active public layer because it gives richer shot quality,
   goalie outcome, rebound, fatigue, and season-scouting context.
2. DZ PK faceoff wins remain the cleanest legacy tactical signal.
3. Forcing an OZ faceoff while short-handed looks worse than keeping play alive, on average.
4. PK offensive-zone forays show positive short-window xG value with limited measured counterattack risk, but the model cannot infer skater commitment.
5. Matchup profiles should be read as style-fit clues, not proof of exact PP or
   PK formations.
6. Player tags are rule-based scouting prompts, not complete grades. Clickable
   tag details should always show the metric, sample, percentile, and caveat.
7. Legacy player models should be used as event-participant scouting, not as full on-ice impact rankings.

## Recommended Next Data Upgrades

To make the project support stronger hockey claims, add:

- Shift/on-ice tables by game time.
- Player coordinates or tracking data at event timestamps.
- Official faceoff winner/loser fields if available.
- Penalty kill shift duration and fatigue features.
- Cleaner possession boundaries around special-teams transitions.

With those upgrades, the unsupported ideas in `MODEL_CAPABILITIES.md` could become real models instead of caveats.
