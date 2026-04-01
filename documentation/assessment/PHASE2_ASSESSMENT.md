# Phase 2 Assessment

## Scope of this pass

This pass starts the operational tranche of Phase 2 and focuses on reducing the main open risks left by Phase 1:

- AWS profile setup was modeled but not verifiable
- Confluence connections were stored but not health-checked
- evidence and assessment execution lacked a scoped readiness view
- recurring assessments were still too framework-centric
- operators had no direct way to see whether a binding, product, or flavor scope was actually ready to run

## What was implemented

### AWS profile operations

- AWS CLI profile validation through `sts:GetCallerIdentity`
- stored validation telemetry:
  - last validation time
  - validation status
  - detected account ID
  - detected ARN
- lifecycle events for AWS profile validation
- workspace actions to validate a selected profile
- CLI command:
  - `aws-local-audit aws-profile validate <profile>`

### Evidence readiness and operational diagnostics

- scoped readiness assessment for:
  - framework binding
  - product
  - flavor
- readiness scoring across:
  - AWS profile operations
  - evidence plan coverage
  - collection execution
  - evidence freshness
  - Confluence publishing
- readiness blockers and warnings surfaced in:
  - workspace `Operations`
  - CLI `aws-local-audit evidence readiness-report`
- login plans now include:
  - validation status
  - detected account
  - account alignment

### Confluence operations

- Confluence connection health testing
- stored connection test telemetry:
  - last tested time
  - last test status
  - last test message
- lifecycle events for both successful and failed Confluence tests
- workspace action to test a selected connection
- CLI command:
  - `aws-local-audit confluence test --name <connection>`

### Recurring assessments

- schedules can now be scoped to:
  - binding
  - product
  - flavor
- schedules now persist operational metadata:
  - execution mode
  - last run status
  - last run message
  - notes
- due schedule execution now records success and error status
- workspace schedule creation from the `Operations` page
- improved CLI schedule management for scoped runs

## Phase 2 maturity snapshot

Maturity scale:

- `0/5`: not started
- `1/5`: concept only
- `2/5`: foundation exists
- `3/5`: usable with material gaps
- `4/5`: strong and governable
- `5/5`: enterprise-ready

| Area | Current maturity | Phase 2 target | Assessment |
| --- | --- | --- | --- |
| Local AWS SSO operations | `4/5` | `4/5` | Profile metadata, config export, runtime planning, validation, and readiness diagnostics are now in place. The main gap is assisted `aws configure sso` style setup and richer host/WSL sync. |
| Evidence collection engine | `3/5` | `3.5/5` | Applicability, targets, offline deferral, readiness, plan coverage, and freshness checks now exist. Full plan-driven execution and manual evidence lifecycle workflows are still open. |
| Confluence publishing | `2.5/5` | `3.5/5` | Secure connections, page publishing, and health tests exist. Attachment routing, artifact types, updates, and idempotent publishing are still missing. |
| Questionnaires | `2.5/5` | `3.5/5` | Product/flavor-aware answer drafting exists, but approvals, answer libraries, redaction, and exports remain open. |
| Recurring assessments | `3/5` | `3.5/5` | Scoped schedules now exist, with run status telemetry and lifecycle events. Background execution, retries, and review closure logic are still missing. |
| Human workspace | `4/5` | `4/5` | Guided onboarding, scoped operations, profile validation, Confluence tests, and schedule setup are now operator-friendly. Review queues and evidence explorer still separate this from enterprise-grade. |

## Whole-project maturity snapshot

### Functional capabilities

| Capability | Maturity | Notes |
| --- | --- | --- |
| Framework catalog and versioned authority sources | `3.5/5` | Strong seeded baseline and custom shells exist; migrations and lineage governance are still missing. |
| Unified controls and mappings | `3/5` | Shared controls and approval metadata exist; review queues and AI-governed promotion remain open. |
| Product and flavor-aware implementations | `3.5/5` | Implementations, maturity profiles, questionnaires, evidence, assessments, and schedules align to product/flavor scope. |
| AWS SSO execution model | `4/5` | Runtime now follows the intended `aws sso login` model with validation and readiness. Assisted profile authoring is the main remaining gap. |
| AWS evidence targeting | `3.5/5` | Targets resolve across binding, product, flavor, control, account, and region scope. Asset discovery and inheritance logic still need work. |
| Evidence planning and assurance readiness | `3/5` | Evidence plans, freshness targets, and readiness scoring exist, but the execution engine is not yet fully driven by approved plans. |
| Confluence evidence and reporting | `2.5/5` | Secure connection handling is credible; attachment-level publishing and governed destinations are still incomplete. |
| Assessments and recurring operations | `3.5/5` | Manual and scheduled assessments work across scope. Jobs, retries, and approval closure are still missing. |
| Customer questionnaires | `2.5/5` | Answer drafting works from implementation state, but the review and export lifecycle is still shallow. |
| Offline-first GRC administration | `4/5` | Local metadata, frameworks, questionnaires, reporting, and evidence reuse are coherent without AWS connectivity. |

### Non-functional qualities

| Quality area | Maturity | Notes |
| --- | --- | --- |
| Security | `3.5/5` | Evidence encryption, keyring-backed secrets, hidden token entry, and connection/profile health telemetry are in place. RBAC, separation of duties, and decrypt-on-demand policy are still missing. |
| Quality engineering | `2/5` | The design is becoming more structured, but migrations, automated tests, and schema validation are still major gaps. |
| Reliability | `2.5/5` | The app now records run/test status and lifecycle events, but durable jobs, retries, concurrency control, and recovery semantics are still absent. |
| Scalability | `2/5` | The architecture is still largely interactive and local-process oriented. Worker execution, pagination, and caching remain future work. |
| Integrability | `2.5/5` | AWS and Confluence integrations are meaningful, but APIs, events, and broader enterprise connectors are not yet present. |
| Operability | `3.5/5` | Readiness reporting, validation, and scoped run planning materially improve day-to-day operation. |
| Usability | `3.5/5` | Wizards and workspace surfaces are strong for early operators. Advanced review and evidence exploration still need dedicated UX. |

## Risks reduced in this pass

### Reduced from Phase 1

- The AWS runtime is no longer a trust-based assumption.
  - Profiles can now be validated against live AWS and tied to detected account identity.
- Confluence publishing is no longer opaque.
  - Connections can now be health-checked and tracked operationally.
- Scoped operation readiness is no longer implicit.
  - The app can now explain why a run is blocked, partial, or ready.
- Recurring assessments are no longer only framework-level in practice.
  - Schedules now support the product and flavor operating model.

### Reduced inside Phase 2

- readiness blockers are surfaced before execution instead of only after failed runs
- account/profile mismatches can now be identified before evidence collection
- stale or missing local evidence is visible at the selected operating scope
- failed schedule runs now persist error state instead of silently disappearing into the due loop

## Priority gaps still open

### `P1`

- no migration framework or schema-version strategy
- no RBAC or separation of duties
- no policy-enforced lifecycle transitions
- no durable job runner for evidence or scheduled assessments

### `P2`

- evidence engine is still only partially plan-driven
- no manual evidence upload, attestation, reviewer assignment, or expiry workflow
- no Confluence attachment publishing or artifact-type routing
- no review queue for mappings, evidence verification, questionnaire answers, or autonomy suggestions
- no evidence explorer with governed decrypt-on-demand access

### `P3`

- no external API or event model
- no connector model beyond AWS and Confluence
- no large-scale reporting layer or portfolio analytics pack

## Requirements to keep visible

### Functional requirements

- guided AWS SSO profile setup for host and Ubuntu WSL environments
- profile validation and account/region diagnostics before evidence runs
- evidence collection driven by approved evidence plans, not only collectors
- manual evidence upload and attestation workflow
- artifact-aware Confluence publishing:
  - evidence attachments
  - assessment reports
  - controlled target destinations
- review queue covering mappings, evidence, questionnaires, and maturity/autonomy recommendations
- recurring assessments at framework, binding, product, and flavor scope
- explicit evidence sufficiency decisions before assessment closure
- enterprise-grade questionnaire lifecycle:
  - reusable answers
  - reviewer approval
  - exports
  - redaction support

### Non-functional requirements

- Alembic or equivalent migration strategy
- automated tests for service and workspace critical paths
- role-based access control and separation of duties
- secure decrypt-on-demand policy for evidence access
- retryable background execution for collectors and schedules
- concurrency protection and run locking
- pagination and filtering for evidence, schedules, questionnaires, and lifecycle history
- import/export APIs and event hooks for enterprise integration

## Recommended next Phase 2 tranche

1. add migrations before the schema grows further
2. make evidence execution explicitly plan-driven for approved plans
3. add manual evidence intake and reviewer workflow
4. add Confluence attachment publishing and artifact routing
5. add a review queue and evidence explorer

## Conclusion

Phase 2 is now meaningfully underway rather than only planned. The project has moved from a good Phase 1 foundation into a stronger operational posture: AWS and Confluence are now testable, scope readiness is explicit, and recurring assessments finally reflect the product/flavor operating model.

The system is not enterprise-ready yet. The largest remaining risks are still governance and reliability risks: migrations, RBAC, lifecycle policy enforcement, plan-driven execution, and durable background jobs.
