# Analytics Model Capability Review

Last reviewed: 2026-05-14

## Bottom Line

The database is strong enough for possession-level PK analytics, xG backfilling, entry outcomes, faceoff outcomes, and event-participant scouting. It is not strong enough for true on-ice player impact, forecheck formation detection, or player positioning claims because `event_players` stores tagged event participants, not every skater on the ice.

## What We Can Do Half-Well

- Team/tactical possession outcomes: entries, clears, shots, goals, xG, counterattacks, and faceoff follow-up windows.
- Descriptive entry defense: controlled versus dump-in entries against the PK, xGA after entries, and opponent entry tendencies.
- PK offensive-zone foray risk/reward: short-handed xG generated versus immediate counterattack xGA.
- Faceoff value: PK DZ faceoff wins/losses and xGA in the next 20 seconds, including circle-side breakdowns.
- Participant scouting: players tagged on blocks, takeaways, hits, giveaways, penalties, and faceoffs.

## What We Should Not Claim

- Actual forechecker count, aggressive/passive PK structure, or rush commitment level.
- Player on-ice shot suppression without shift/TOI or full on-ice skater data.
- Off-ice team comparison for individual players.
- Gap-control or net-front coverage from player locations.
- Per-60 player rates unless real time-on-ice is added.

## Model Adjustments

- Model 2 was changed from player commitment levels to PK offensive-zone foray risk/reward.
- Model 4 was changed from forechecker structure to PK entry defense outcomes.
- Models 6, 7, 8, and 10 were changed from unsupported on-ice scouting to event-participant scouting.
- Model 9 remains one of the strongest player models because faceoff participants are explicitly tagged.
- Model 5 remains a matched faceoff comparison, but it is not a full DoWhy causal model in this environment.

## Data Upgrades That Would Unlock Better Models

- Full shift/on-ice tables by game time.
- Player coordinates or tracking data at event timestamps.
- Official faceoff winner/loser fields if available.
- Penalty kill shift duration and fatigue features.
- More reliable possession boundaries around special-teams transitions.
