# NHL Penalty Kill Analytics

Analytics system for studying NHL penalty-kill possessions, goals against, shot quality, and tactical breakdown patterns.

## Repository Layout

```text
Data_ingestion/
├── Analytics/              # Python diagnostics and modeling
├── NhlPkIngest/            # .NET 8 ingestion console app
├── Data_ingestion.sln      # Visual Studio solution
├── README.md
└── .gitignore
```

At the moment, Git is rooted inside `NhlPkIngest/`, so this top-level README and the `Analytics/` folder are local project files until the repo root is migrated up one level.

## Components

### NhlPkIngest

The ingestion pipeline pulls NHL play-by-play data, normalizes coordinates and zones, stores events/shots/players/teams/games, and builds penalty-kill possessions.

Useful commands:

```powershell
cd NhlPkIngest
dotnet restore
dotnet build
dotnet run
```

### Analytics

The Python layer contains database helpers, diagnostics, xG modeling code, and tactical model experiments.

Useful commands from Git Bash:

```bash
cd "/d/Hockey-data project/Code/Data_ingestion/Analytics"
./venv/Scripts/python.exe -m diagnostics.join_explosion
./venv/Scripts/python.exe -m diagnostics.validate_coordinates
./venv/Scripts/python.exe -m diagnostics.validate_possessions
```

## Current Validation Notes

- Shot coordinates are within rink bounds.
- Fixed-net shot-distance diagnostics currently flag possible orientation issues and should be interpreted as a diagnostic warning, not proof that coordinates are unusable.
- Forward-forechecking and defenseman-gap-control joins show row inflation and need deduped event-level bases before player-level modeling.
- Possession validation should be rerun after re-ingesting with the latest strength-change possession boundary fix.

## Git Structure

The clean long-term structure is a monorepo rooted at `Data_ingestion/`, not inside `NhlPkIngest/`. That lets Git track:

- the .NET ingestion app,
- the Python analytics app,
- the Visual Studio solution,
- shared docs and project-level configuration.

Do not move the `.git` folder by itself. The existing index paths are relative to `NhlPkIngest/`, so a plain move would make Git think the tracked files were deleted.
