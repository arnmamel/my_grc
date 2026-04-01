# Project Hygiene Iterations

## Iteration 1: Runtime vs. Context Separation

- identified runtime code, operator workspace files, test assets, and conversation-generated material
- moved non-runtime markdown into `documentation/`
- moved QA and regression assets into `testing/`

## Iteration 2: Operator Flow Consolidation

- made `Control Framework Studio` the primary control mapping surface
- removed the user-facing split between current and legacy workspace modes
- updated the main navigation and quick actions to point to the unified workflow

## Iteration 3: Repository Safety And Publishability

- expanded `.gitignore` for local databases, logs, QA reports, secrets, and generated packaging metadata
- removed generated packaging clutter where safe
- kept local runtime-only artifacts out of the intended Git history

## Iteration 4: Documentation And Runbook Alignment

- rewrote `README.md` around the current project structure and operator flow
- updated user-facing runbooks to point to `Control Framework Studio`, `Workspace Home`, and the `testing/` layout
- separated design material from assessments and day-to-day user guidance

## Iteration 5: Validation And Final Coherence Pass

- retargeted QA, regression, and helper scripts to the `testing/` layout
- validated the WSL unit suite and QA harness after the reorganization
- kept compatibility aliases for old control pages, but routed them into the single `Control Framework Studio` surface
