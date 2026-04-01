# Release Improvements And Issues

## Current Release Highlights

- single unified workspace shell with the specialist workflows integrated into the same navigation
- workspace pages redesigned around shorter tabs and same-screen actions
- `Workspace Home` now includes direct drill-downs for records, reviews, Phase 1 details, enterprise details, and release notes
- `Asset Catalog` now uses a same-screen master/detail flow instead of forcing users to switch between selection and edit tabs
- `Artifact Explorer` now keeps artifact selection, lifecycle context, and related actions together on one screen
- `Operations Center` now separates readiness, review, and recent runs into focused tabs
- `Governance Center` now separates Phase 1 posture, enterprise posture, lifecycle activity, and release notes
- `Settings & Integrations` now includes concise run and test guidance for operators and developers
- `Help Center` now focuses on practitioner help instead of product-maturity commentary
- a one-click `Exercise SCF Pivot Backbone` path now creates a real local mapped control chain using the SCF pivot baseline and ISO/IEC 27001:2022 Annex A `A.5.1`

## Corrections In This Release

- removed the user-facing split between unified and legacy workspace modes
- reduced navigation friction by keeping selection and action together on the same screen
- updated runbooks so they no longer tell users to go into a legacy workspace mode
- improved the visual polish of the workspace with a collapsed top-left navigation entry, cleaner cards, and tighter tabs

## Known Gaps

- some deeper specialist pages still need the same level of visual simplification as the redesigned top-level pages
- broader SCF mapping coverage still needs to be exercised beyond the first seeded local path
- more scoped product implementations and control profiles should be added for richer assurance coverage
- the platform still has project-wide `datetime.utcnow()` deprecation warnings that should be normalized to timezone-aware UTC handling

## Known Bugs Or Defects

- Ubuntu WSL may still print `Failed to mount S:\` in some environments even when the workspace itself works correctly
- some runtime verification steps still depend on the target WSL virtual environment having the expected dependencies installed

## Security And Vulnerability Notes

- no new security exceptions were introduced in this UI refactor
- encrypted evidence handling, secret metadata tracking, and governed lifecycle logging remain in place
- vulnerability review should continue through the QA harness and container scan scripts before release promotion

## Recommended Next Corrections

1. complete the timezone-aware UTC cleanup across the services layer
2. extend the same master/detail interaction model into the remaining specialist screens
3. expand the SCF-pivot mapped control set beyond the initial ISO `A.5.1` path
4. add more guided evidence and assessment actions directly into the focused tabs
