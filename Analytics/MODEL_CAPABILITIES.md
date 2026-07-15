# Analytics Model Capability Review

Last reviewed: 2026-07-09

## Bottom Line

The original NHL API database is strong enough for possession-level PK analytics, xG backfilling, entry outcomes, faceoff outcomes, and event-participant scouting. The MoneyPuck v2 layer adds stronger public shot-quality, goalie-outcome, rebound, fatigue, and season-scouting views. NHL shiftcharts now support raw shifts and event-level on-ice reconstruction across all `3,879` source-covered games, with `802,175` PK player-event feature rows across `1,138` players. This supports on-ice joins, TOI/rest features, and descriptive or adjusted PK pressure diagnostics, but not broad player-impact or causal fatigue claims yet. No source here supports forecheck formation detection or player positioning claims without tracking data.

## What We Can Do Half-Well

- Team/tactical possession outcomes: entries, clears, shots, goals, xG, counterattacks, and faceoff follow-up windows.
- Descriptive entry defense: controlled versus dump-in entries against the PK, xGA after entries, and opponent entry tendencies.
- PK offensive-zone foray risk/reward: short-handed xG generated versus immediate counterattack xGA.
- Faceoff value: PK DZ faceoff wins/losses and xGA in the next 20 seconds, including circle-side breakdowns.
- Participant scouting: players tagged on blocks, takeaways, hits, giveaways, penalties, and faceoffs.
- MoneyPuck v2 descriptive models: pre-shot movement buckets, blocked-shot aftershock, goalie control, fatigue timing, and season-level skater/goalie short-handed profiles.
- Source-covered shift diagnostics: raw shift rows, event-level on-ice reconstruction, manpower checks, and first-pass player-event PK exposure summaries for games where NHL shiftcharts are present.
- Exploratory source-covered fatigue pressure by oldest active shift and shortest rest, with explicit sample gates and uncertainty intervals.
- Adjusted next-shot pressure associations with penalty-time, score, zone, event-type, team, and opponent controls plus game-clustered uncertainty and horizon sensitivity.
- High-confidence PP offensive-zone control sensitivity based on event ownership and zone, used as robustness evidence rather than literal possession tracking.

## What We Should Not Claim

- Actual forechecker count, aggressive/passive PK structure, or rush commitment level.
- Broad player on-ice shot suppression rankings until shift-derived rows pass broader season validation and TOI denominators are added.
- Off-ice team comparison for individual players.
- Gap-control or net-front coverage from player locations.
- Published per-60 player rates until shift-derived TOI is validated across more games and wired into model denominators.
- Goal-event shift-age fatigue claims until scoring-timestamp shift splits are audited; keep goals as outcome exposures, not bucketed fatigue evidence.
- Causal claims from v2 public-data splits without additional validation.

## Model Adjustments

- Model 2 was changed from player commitment levels to PK offensive-zone foray risk/reward.
- Model 4 was changed from forechecker structure to PK entry defense outcomes.
- Models 6, 7, 8, and 10 were changed from unsupported on-ice scouting to event-participant scouting.
- Model 9 remains one of the strongest player models because faceoff participants are explicitly tagged.
- Model 5 remains a matched faceoff comparison, but it is not a full DoWhy causal model in this environment.
- MoneyPuck v2 is now the primary public frontend layer; the older models remain useful as legacy context and validation scaffolding.

## Data Upgrades That Would Unlock Better Models

- Broader validation of `game_shifts`, `event_on_ice_players`, and `event_manpower` tables across seasons, including penalty timing and goalie-pulled edge cases.
- Opponent-, zone-, score-, event-mix-, and possession-adjusted estimation before describing the shift-age pressure association as a fatigue effect.
- Causal fatigue, deployment-intent, or tactical-mechanism claims from the adjusted next-shot model; unmeasured possession and tracking context remain material.
- Treating the reconstructed `possessions` table as a complete event-state timeline; it covers only `14.04%` of source-covered PK team-events.
- Player coordinates or tracking data at event timestamps.
- Official faceoff winner/loser fields if available.
- Penalty kill shift duration, rest, and fatigue features from validated shift segments.
- More reliable possession boundaries around special-teams transitions.
