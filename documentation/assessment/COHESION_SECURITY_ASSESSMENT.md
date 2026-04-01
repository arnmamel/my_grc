# Cohesion and Security Assessment

## Purpose

This review checks the current `my_grc` project for:

- architectural cohesion
- feature completeness against the intended GRC operating model
- security-by-design gaps
- lifecycle-model coverage

It also records what was remediated in this pass and what still needs follow-up.

## Executive summary

The project is now materially more coherent than before this pass, but it is still in the foundation stage for enterprise GRC.

Strongest areas after this pass:

- product and flavor-aware data model
- unified-control and framework backbone
- scoped evidence and assessment execution
- encrypted evidence-at-rest foundation
- secure secret handling foundation with OS keyring-backed storage
- lifecycle-event audit trail foundation

Most important remaining gaps:

- no migration system yet
- evidence execution is still collector-centric rather than evidence-plan-centric
- control applicability and inheritance are still basic
- secure Confluence connection management is CLI-first, not yet fully surfaced in the workspace
- lifecycle states exist, but approval workflows and transition rules are still incomplete
- autonomous assessment logic is still heuristic rather than policy-driven

## Findings

### High severity

1. Plaintext evidence storage

Status: fixed in this pass.

Before:

- evidence payloads were stored directly in `EvidenceItem.payload_json`

Now:

- evidence payloads are encrypted before persistence
- integrity digests are stored alongside the encrypted payload
- storage mode is tracked on each evidence item

Relevant code:

- [evidence.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/services/evidence.py)
- [security.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/security.py)
- [models.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/models.py)

2. Secret handling through environment variables

Status: partially fixed in this pass.

Before:

- Confluence tokens were expected in `.env` or process environment

Now:

- secure path is OS keyring-backed
- Confluence connections can be registered via CLI with hidden input
- env-secret fallback exists only as an explicit legacy opt-in

Remaining gap:

- secure connection management is now available in the workspace, but broader secret administration is still CLI-first

Relevant code:

- [confluence.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/integrations/confluence.py)
- [security.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/security.py)
- [security.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/services/security.py)
- [cli.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/cli.py)

3. Missing lifecycle audit trail

Status: foundationally fixed in this pass.

Before:

- major state changes were not recorded in a normalized lifecycle log

Now:

- `LifecycleEvent` exists
- frameworks, bindings, unified controls, implementations, evidence items, assessments, and questionnaires record lifecycle events

Remaining gap:

- transition policy and approval governance are not enforced yet

Relevant code:

- [models.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/models.py)
- [lifecycle.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/services/lifecycle.py)

4. Schema initialization inconsistency

Status: improved in this pass.

Before:

- schema creation was invoked directly in multiple places with `Base.metadata.create_all`

Now:

- database initialization is centralized through `init_database()`

Remaining gap:

- there is still no migration framework, so schema evolution remains brittle

Relevant code:

- [db.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/db.py)
- [cli.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/cli.py)
- [app.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/workspace/app.py)

### Medium severity

5. Product-aware evidence and assessment scope could drift from binding scope

Status: improved in the previous pass and refined here.

Current state:

- evidence collection and assessment runs can be scoped to binding, product, and flavor
- helper queries now distinguish global binding scope from product scope

Remaining gap:

- applicability and inheritance logic is still not the source of truth for what runs

6. Confluence integration is page-centric, not artifact-centric

Status: still open.

Current state:

- page creation works
- secure connection records now exist

Missing:

- attachment upload
- idempotent updates
- target routing by artifact type
- connection health test

7. Evidence engine remains collector-centric

Status: still open.

Current state:

- collectors run directly from control `evidence_query`

Missing:

- explicit evidence plans
- evidence sufficiency rules
- normalized fact extraction
- evidence freshness policies
- human-assisted evidence tasks

8. Lifecycle states are present but not normalized enough yet

Status: still open.

Current state:

- framework lifecycle
- control lifecycle
- evidence lifecycle
- audit lifecycle
- assurance status

Missing:

- controlled transitions
- approvers
- due dates and SLAs
- exception handling
- evidence verification lifecycle
- review workflow state machines

### Low severity

9. Workspace coverage is still uneven

Status: open.

Current state:

- strong start for operations, portfolio, maturity, and questionnaires

Missing:

- secure connections page
- lifecycle explorer
- evidence viewer with decrypt-on-demand
- review queue
- jobs page

10. Framework seeding updates controls but does not prune removed controls

Status: open.

Risk:

- stale controls can remain in the database after template evolution

## What changed in this pass

### Security

- added OS keyring-backed secret handling foundation
- added encrypted evidence storage via AES-GCM
- added integrity digests for evidence payloads
- added secure Confluence connection model and CLI workflow
- disabled env-secret use by default unless explicitly opted into

### Lifecycle and governance

- added `LifecycleEvent`
- added lifecycle status fields for frameworks, unified controls, bindings, evidence items, and assurance-oriented entities
- added lifecycle-event recording in key services

### Cohesion

- centralized schema initialization
- aligned Confluence integration with the secure connection model
- aligned evidence/assessment services with the lifecycle model

## Lifecycle coverage after this pass

### Framework lifecycle

Covered:

- draft
- active
- inactive

Missing:

- version superseded
- retired
- approval workflow for promotion

### Control lifecycle

Covered:

- unified-control draft state
- implementation lifecycle field
- lifecycle-event recording

Missing:

- enforced transition rules
- design approval
- deprecation handling
- inherited-control lifecycle

### Evidence lifecycle

Covered:

- collected state
- encrypted persistence
- digest tracking
- lifecycle events

Missing:

- verified
- approved
- expired
- archived
- retention policy execution

### Audit lifecycle

Covered:

- running/completed status
- review status
- assurance status
- lifecycle events

Missing:

- scheduled
- in_review
- approved
- challenged
- reopened

### Assurance lifecycle

Covered:

- product control profile assurance status
- assessment run assurance status

Missing:

- evidence sufficiency decisioning
- sign-off workflow
- override and exception workflow
- assurance expiration dates

## Recommended next implementation tranche

1. Add migrations and a formal schema-version strategy.
2. Add `EvidenceCollectionPlan`, `ControlApplicabilityRule`, and inheritance modeling.
3. Add workspace pages for secure connections and lifecycle review.
4. Add Confluence attachment upload and connection test.
5. Add decrypt-on-demand evidence viewing with role-aware access controls.
6. Add transition rules and approval steps to lifecycle changes.
7. Add evidence freshness, retention, and archival policies.

## Overall maturity after this pass

| Area | Maturity |
| --- | --- |
| Architecture cohesion | 3/5 |
| Security foundation | 3/5 |
| Secret handling | 3/5 |
| Evidence confidentiality at rest | 3/5 |
| Lifecycle traceability | 2.5/5 |
| Lifecycle governance | 2/5 |
| Enterprise readiness | 2.5/5 |

This means the project now has the right backbone for secure and governed evolution, but it still needs the next tranche of policy-driven behavior, migrations, and operational workflows before it should be considered enterprise-ready.
