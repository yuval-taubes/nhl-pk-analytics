# Analytics Model Guide

Last updated: 2026-05-21

This folder is the research layer for the penalty-kill project. It turns the ingested NHL play-by-play database into descriptive PK models, scouting tables, and JSON outputs for downstream analysis.

The most recent local run completed successfully:

```text
models/output/models_2_10_run_20260515_152705.json
```

Generated files under `models/output/` are ignored by Git because they are local run artifacts. The code and the interpretation below are the durable project documentation.

The published frontend uses a committed snapshot of this run at
`Frontend/public/data/dashboard.json`, so reviewers can inspect the model-story
site without recreating the local database.

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

## Current Findings

These findings come from the successful 2026-05-15 run.

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

1. DZ PK faceoff wins matter a lot. This is currently the cleanest tactical signal in the model suite.
2. Forcing an OZ faceoff while short-handed looks worse than keeping play alive, on average.
3. PK offensive-zone forays show positive short-window xG value with limited measured counterattack risk, but the model cannot infer skater commitment.
4. Dump-in entries against the PK were more dangerous than controlled entries in this run, though the sample is much smaller than the faceoff samples.
5. Player models should be used as event-participant scouting, not as full on-ice impact rankings.

## Recommended Next Data Upgrades

To make the project support stronger hockey claims, add:

- Shift/on-ice tables by game time.
- Player coordinates or tracking data at event timestamps.
- Official faceoff winner/loser fields if available.
- Penalty kill shift duration and fatigue features.
- Cleaner possession boundaries around special-teams transitions.

With those upgrades, the unsupported ideas in `MODEL_CAPABILITIES.md` could become real models instead of caveats.
