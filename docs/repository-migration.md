# Repository Migration Notes

## Current Problem

Git is currently rooted at:

```text
Data_ingestion/NhlPkIngest/
```

The full project is actually rooted one level higher:

```text
Data_ingestion/
├── Analytics/
├── NhlPkIngest/
└── Data_ingestion.sln
```

Because Git cannot track files outside its working tree, `Analytics/` and `Data_ingestion.sln` are invisible to the current repository.

## Do Not Plain-Move `.git`

Do not simply move `NhlPkIngest/.git` to `Data_ingestion/.git`.

The current Git index stores paths like:

```text
Services/GameIngester.cs
schema.sql
```

If `.git` is moved up one level without rewriting paths, Git will look for:

```text
Data_ingestion/Services/GameIngester.cs
Data_ingestion/schema.sql
```

Those files do not exist there, so Git will report the project as deleted.

## Recommended Options

### Option A: New Monorepo Root

Best when preserving the current commit history is less important than getting the structure clean quickly.

1. Keep a backup of the current `NhlPkIngest/.git` folder.
2. Initialize a new Git repository at `Data_ingestion/`.
3. Add `Analytics/`, `NhlPkIngest/`, `Data_ingestion.sln`, root `README.md`, and root `.gitignore`.
4. Point the remote to `https://github.com/yuval-taubes/nhl-pk-analytics.git`.
5. Force-push only if intentionally replacing the existing remote history.

### Option B: Preserve History With Path Rewrite

Best when the existing remote history matters.

Rewrite the existing repository so every tracked path gets prefixed with `NhlPkIngest/`, then move the repository root up one directory. This should be done only after committing or stashing local changes.

High-level result:

```text
Services/GameIngester.cs
```

becomes:

```text
NhlPkIngest/Services/GameIngester.cs
```

After that rewrite, the parent-level `Analytics/` folder can be added normally.

## Current Safe Cleanup Already Done

- `.gitignore` no longer ignores the C# `Models/` source directory.
- `Models/*.cs` should now appear as untracked files and can be added.
- A root-level README and `.gitignore` have been created for the future monorepo root.
- `appsettings.template.json` has been added so local secrets can eventually be removed from tracked config.
