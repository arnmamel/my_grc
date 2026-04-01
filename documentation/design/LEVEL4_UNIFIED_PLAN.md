# Level-4 Unified Plan

## Objective

This plan unifies Phase 1, Phase 2, and Phase 3 into one maturity path that drives `my_grc` to a strong `4/5` operating posture across functional and non-functional areas.

For the latest implementation reassessment after the most recent uplift pass, see `LEVEL4_REASSESSMENT.md`.

Maturity scale:

- `1/5`: concept only
- `2/5`: foundation exists
- `3/5`: usable with material gaps
- `4/5`: strong, governable, deployable
- `5/5`: enterprise-optimized

## Current consolidated assessment

### Phase maturity

| Area | Estimated maturity | Assessment |
| --- | --- | --- |
| Phase 1 foundation | `3.4/5` | The backbone exists: frameworks, unified controls, products, flavors, evidence targets, onboarding wizards, and scoped operations are all usable. |
| Phase 2 operations | `3.1/5` | AWS SSO validation, readiness scoring, recurring scoped schedules, review queues, and Confluence health checks exist, but evidence execution is still only partially plan-driven. |
| Phase 3 enterprise readiness | `2.8/5` | Governance traceability exists and the product can support a controlled pilot, but RBAC, background jobs, and integration surfaces are still open. |

### Non-functional maturity

| Quality area | Estimated maturity | Assessment |
| --- | --- | --- |
| Security | `3.5/5` | Encrypted evidence-at-rest, secure secret backends, and protected PAT capture are in place. Access policy, RBAC, and retention controls are still open. |
| Quality | `3.3/5` | Migration scaffolding, smoke tests, and regression tests now exist. Broader service coverage and CI enforcement still need to be added. |
| Reliability | `3.0/5` | The platform now fails more gracefully when Confluence is unavailable, but there are still no durable workers, retries, or run locking. |
| Scalability | `2.5/5` | The data model is ready for scale, but long-running work is still interactive and views still need pagination/search depth. |
| Integrability | `2.8/5` | AWS and Confluence are integrated well enough for guided use, but external APIs, eventing, and broader connectors are not first-class yet. |
| Deployment | `3.6/5` | Ubuntu bootstrap, Alpine-based Docker, Compose, smoke scripts, and scan scripts now form a credible deployment baseline. |
| UI and UX | `3.4/5` | The workspace is coherent and action-oriented, but it still needs deeper end-to-end playbooks, evidence browsing, and less form density in some flows. |

## Unified level-4 target

The product should be considered `4/5` when the following are all true:

- a fresh Ubuntu operator can install, initialize, validate, and run the workspace from documented commands
- Docker deployment is reproducible, scanned, and smoke-tested before promotion
- framework, mapping, questionnaire, evidence plan, and assessment review states are governed rather than ad hoc
- live AWS runs are always preceded by a validated profile plan and remain optional because offline-first workflows still work
- evidence collection is mostly driven by approved plans and scoped targets instead of raw collector availability
- Confluence publishing can store evidence artifacts and assessment outputs without making local collection brittle
- review queues and maturity scoring expose the next best actions to operators

## Unified work plan to reach 4/5

### Slice 1: Governance hardening

- enforce lifecycle transitions for mappings, evidence plans, questionnaire items, and assessment reviews
- keep migrations as the default schema path instead of relying on implicit `create_all`
- add policy documentation for who can approve what and when
- introduce explicit owner, reviewer, due-date, and cadence fields in the next schema pass

### Slice 2: Operational execution

- increase evidence-plan coverage for seeded frameworks, starting with ISO 27001 and AWS-heavy controls
- attach encrypted evidence envelopes to Confluence pages while keeping local encrypted storage as the source of truth
- add manual evidence upload and reviewer decisions
- make readiness reports the pre-flight contract for evidence and assessment runs

### Slice 3: Deployment and quality

- use Ubuntu bootstrap plus validation scripts as the standard host path
- use Alpine-based container builds with smoke tests and vulnerability scans before promotion
- expand regression tests across security, lifecycle, review queue, readiness, and questionnaire logic
- add CI gates for tests, image scan, and migration health

### Slice 4: UI and operator experience

- make the overview page the default operating cockpit for queue, maturity, and deployment readiness
- add decrypt-on-demand evidence explorer with governed access
- add job history, retry, and run diagnostics
- keep offline mode explicit in every operational surface

## Main gaps still open after this pass

- RBAC and separation of duties
- evidence explorer and decrypt-on-demand access control
- plan-driven collection coverage across more controls
- durable job execution and retries
- API and event hooks for integrations
- richer Confluence artifact routing by type and destination
- CI enforcement of scans, tests, and migrations

## Recommendation

The next implementation tranche should focus on one narrow goal: make a real ISO 27001 product-scoped assessment cycle feel governed end to end. That means approved mappings, approved evidence plans, validated AWS profiles, successful evidence collection, reviewed assessment results, and optional Confluence publishing with attachments. Achieving that flow cleanly is the most credible path to a repeatable `4/5` product.
