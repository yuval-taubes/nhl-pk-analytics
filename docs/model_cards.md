# Model Cards

These cards define what each model is allowed to claim right now. They are
intended to keep portfolio readers from over-interpreting exploratory outputs.

## Model 1: Power-Play Entry Impact

- Question: Are controlled PP entries associated with more xG against the PK
  than dump-ins?
- Unit: retained PP possession.
- Outcome: possession `xg_sum`.
- Exposure: `CONTROLLED` vs `DUMP_IN` entry type.
- Current status: exploratory.
- Main limitations: automated entry classification, possession segmentation
  dependency, no manual video validation yet.
- Invalid use: settled causal claim about entry strategy.

## Model 1B: Power-Play Entry Attempt Impact

- Question: What happens when failed entry attempts are included?
- Unit: inferred PP entry attempt.
- Outcome: PP xG in a short window.
- Exposure: inferred controlled attempt vs dump-in attempt.
- Current status: experimental.
- Current guardrail: candidates are deduped within five seconds and shot windows
  stop at the next candidate attempt.
- Invalid use: full possession value model or manually validated entry dataset.

## Models 2-5: Tactical Possession And Faceoff Models

- Question: Which possession-level PK events are associated with risk or value?
- Unit: possession, clearance, entry, or faceoff window depending on model.
- Current status: usable for descriptive model-story review.
- Strongest current finding: defensive-zone PK faceoff wins reduce immediate
  xGA in the matched short-window analysis.
- Invalid use: tracking-style claims about player spacing or pressure shape.

## Models 6-10: Player Event-Participant Profiles

- Question: Which players appear in tagged event contexts associated with PK
  actions?
- Unit: event-linked player participation row.
- Current status: descriptive scouting profile only.
- Main limitations: no shift time on ice, no tracking coordinates, no true
  on-ice player impact.
- Invalid use: per-60 rankings, RAPM-style impact, or net-front/gap-control
  claims requiring tracking data.

## xG Model

- Question: What baseline shot danger should be assigned from public shot
  location and event features?
- Unit: shot.
- Outcome: goal probability.
- Features: nearest-net distance, angle, shot type, rebound flag, strength.
- Current guardrail: exports decile and fixed-bin calibration metrics.
- Invalid use: definitive public xG benchmark or proof of coordinate orientation.
