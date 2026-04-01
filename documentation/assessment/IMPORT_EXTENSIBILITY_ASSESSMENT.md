# Import Extensibility Assessment

## Scope assessed

This assessment covers:

- external framework import
- source-to-control traceability
- unified-control baseline growth during imports
- external assessment script registration and binding
- evidence-plan execution through script modules
- workspace and CLI operator flow

## Maturity snapshot

Scale:

- `0/5`: not started
- `1/5`: concept only
- `2/5`: foundation exists
- `3/5`: usable with material gaps
- `4/5`: strong, needs hardening
- `5/5`: enterprise-ready

| Capability | Maturity | Notes |
| --- | --- | --- |
| Framework import wizard | 3/5 | CSV and spreadsheet imports work through the workspace and CLI. |
| Source traceability | 3/5 | Import batches and per-row imported requirements preserve provenance into framework controls. |
| Unified-control integration | 3/5 | Imports can capture suggestions, map to existing controls, or extend the baseline. |
| Existing script onboarding | 3/5 | Python assessment scripts can be registered from form or manifest and bound to scope. |
| Script-based evidence execution | 3/5 | Evidence plans can execute script modules and capture script-run records and artifacts. |
| Ubuntu/WSL operator usability | 3/5 | CLI and workspace flows are present, but runtime validation is still pending. |
| Security posture | 3/5 | Local evidence remains encrypted; script metadata is governed, but external module trust is not yet hardened. |
| Reliability | 2.5/5 | No background jobs or retry orchestration yet for external scripts. |

## Strengths added in this pass

- Imported source rows are no longer opaque. They are first-class entities with stored provenance.
- The unified-control baseline can now be enriched directly from real authority sources instead of only manual authoring.
- Existing Python automation can be absorbed into the product model instead of living outside it.
- Evidence plans remain the execution backbone, even when the actual collection logic comes from imported scripts.

## Main gaps to reach 4/5

Functional:

- richer source-specific presets for major imports such as CSA CCM
- dedicated review-queue items for import exceptions and unresolved imported requirements
- more powerful conflict handling for repeated imports and version-to-version framework diffs
- stronger validation for script manifests, argument templates, and output schemas

Non-functional:

- signed or integrity-checked external script packaging
- real Ubuntu/WSL runtime validation
- background execution and retry policy for long-running script modules
- more explicit RBAC around import approval and external module registration
- stronger migration discipline than additive `create_all` compatibility for future schema evolution
