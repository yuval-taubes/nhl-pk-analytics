# Coordinate And Manpower Conventions

Last updated: 2026-05-16

This project has two conventions that must stay explicit because many model
claims depend on them.

## Manpower

The ingested `events` table stores numeric skater counts as:

- `home_skaters`
- `away_skaters`

The compact `strength` string is stored as:

```text
away_skaters v home_skaters
```

Example from the local validation report:

| strength | home_skaters | away_skaters | Meaning |
| --- | ---: | ---: | --- |
| `4v5` | 5 | 4 | home team is on the power play |
| `5v4` | 4 | 5 | away team is on the power play |

That is why existing model SQL maps the larger left side of `strength` to the
away team and the larger right side to the home team. This is valid only if the
away-v-home convention holds.

Run the diagnostic after ingestion changes:

```powershell
cd Analytics
$env:NHL_DB_PASSWORD = "your_password"
.\venv\Scripts\python.exe diagnostics\validate_manpower_context.py
```

The latest local report is written to:

```text
Analytics/reports/latest_manpower_context.md
```

## Coordinates

The rink coordinate system uses normalized 200 x 85 rink coordinates:

- `x_norm` ranges from `0` to `200`.
- `y_norm` ranges from `0` to `85`.
- Shot and event models currently use nearest-net distance for xG features.

That nearest-net xG approach is a modeling convention, not proof that every
event is oriented correctly. A future validation pass should compare nearest-net
targeting against period/team attacking direction and document any systematic
differences.

Run the orientation diagnostic after coordinate or ingestion changes:

```powershell
cd Analytics
$env:NHL_DB_PASSWORD = "your_password"
.\venv\Scripts\python.exe diagnostics\validate_coordinate_orientation.py
```

## Current Trust Boundary

Current model pages may use:

- possession-level outcomes,
- entry type outcomes,
- faceoff short windows,
- tagged event participants,
- nearest-net shot danger features.

They should not yet claim:

- tracking-style positioning,
- true on-ice player impact,
- gap control,
- net-front coverage,
- validated entry-attempt labels.
