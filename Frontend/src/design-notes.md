# Frontend Design Notes

## Product Shape

This is an operational hockey analytics workspace for PK review, not a landing page.
The first screen should answer:

- Is the PK trending better or worse?
- Which tactical patterns are driving goals against?
- Where do dangerous shots and failed clears happen?
- Which possessions need manual review?

## Visual Language

- Dark workstation base.
- Ice-blue for structure and neutral analytical state.
- Red for conceded goals, danger, and rising xGA.
- Green for clears, recoveries, and reduced danger.
- Amber for penalties, warnings, and diagnostics requiring review.

## Layout Principles

- Left rail for major work modes.
- Top filter bar for team, season, strength, and game context.
- Panels should be full-width dashboard regions, not nested cards.
- Tables must stay scannable at laptop widths.
- Rink and sequence visuals are first-class analytical objects.

## Avoid

- Marketing hero pages.
- Purple AI gradients.
- Decorative glassmorphism that reduces data contrast.
- Hiding critical filters behind modals.
- Making tactical data depend only on color.
