# Repository Migration Notes

Last updated: 2026-06-05

This note is historical. The working repository is now rooted at the full project
folder:

```text
Data_ingestion/
|-- Analytics/
|-- Frontend/
|-- NhlPkApi/
|-- NhlPkIngest/
`-- Data_ingestion.sln
```

The old risk was that Git was rooted inside `NhlPkIngest/`, which made the
analytics, API, frontend, and solution files invisible to version control. That
has been resolved by using the project root as the repository root.

Current safeguards:

- Root `.gitignore` excludes local secrets, virtual environments, build output,
  generated model output, and frontend dependencies.
- `NhlPkIngest/appsettings.template.json` is committed as the safe template.
- `NhlPkIngest/appsettings.json` is ignored and should stay local.
- The public frontend uses a committed compact snapshot at
  `Frontend/public/data/dashboard.json` rather than local database output.
