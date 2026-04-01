# Enterprise GRC Phased Plan

## Scope

This document converts the existing roadmap into a 3-phase implementation plan that respects the current `my_grc` foundation, captures the new Phase 1 groundwork added in this pass, and highlights the remaining gaps for an enterprise-grade GRC platform.

Maturity scale:

- `0/5`: not started
- `1/5`: concept only
- `2/5`: foundation exists
- `3/5`: usable with material gaps
- `4/5`: strong and governable
- `5/5`: enterprise-ready

## Full assessment

### Priority findings

| Priority | Gap | Why it matters |
| --- | --- | --- |
| `P1` | No migrations or schema version strategy | The model is evolving quickly and existing deployments cannot safely adopt new fields or tables. |
| `P1` | No policy-enforced lifecycle transitions | Lifecycle data exists, but control, evidence, and assurance promotion still depends on service behavior rather than governed state machines. |
| `P1` | No RBAC or approval segregation | Enterprise GRC requires separation of duties for mappings, evidence approval, questionnaires, and assessments. |
| `P2` | Evidence engine is still mostly collector-centric | We now have `EvidenceCollectionPlan`, but execution is not yet driven by plan sufficiency, freshness, or review policy. |
| `P2` | Confluence publishing is still page-first | Attachment routing, update semantics, artifact targets, and health checks remain incomplete. |
| `P2` | AWS SSO is runtime-capable but onboarding-poor | The system can use local profiles, but it still lacks guided profile setup and diagnostics. |
| `P2` | Background execution is missing | Recurring assessments and large evidence runs still depend on interactive execution paths. |
| `P2` | AI autonomy is heuristic | Suggestions exist, but no governed review queue, provenance policy, or approval thresholds are enforced. |
| `P3` | No external API or event model | Integration with enterprise ecosystems will be limited until import/export and event hooks become first-class. |

### Current feature maturity

| Area | Current maturity | Current state |
| --- | --- | --- |
| Framework catalog and authority documents | `3/5` | Template seeding exists, custom framework shells now exist, and authority documents are modeled. |
| Unified controls and mappings | `2.5/5` | Unified controls, governed mappings, and CSV suggestion heuristics exist, but review workflow is still thin. |
| Product and flavor-aware implementations | `3.5/5` | Scoped implementations, maturity profiles, questionnaires, evidence, assessments, and schedules now work at product and flavor level. |
| Evidence-plan governance | `3/5` | `EvidenceCollectionPlan` now exists in the model and workspace, and operational readiness measures plan coverage and freshness, but runtime is not fully plan-driven yet. |
| Secure secret handling | `3/5` | Keyring-backed secret storage and hidden PAT entry exist. |
| Evidence confidentiality | `3/5` | Evidence payload encryption exists, but the broader evidence lifecycle and access policy are incomplete. |
| Lifecycle traceability | `3/5` | Lifecycle events exist across major entities, including AWS profile validation, Confluence health tests, and schedules, but governed transitions and approvals are still missing. |
| Guided user experience | `3.5/5` | The workspace now covers first-run setup, framework authoring, mappings, evidence plans, scoped operations, profile validation, Confluence testing, and schedule setup. |
| Questionnaires | `2.5/5` | Implementation-driven answers work, but answer libraries, review states, and exports are not mature. |
| Confluence publishing | `2.5/5` | Secure connections, page publishing, and connection health tests exist, but artifact routing and attachments are still open. |
| Recurring and autonomous assessments | `3/5` | Schedules, maturity heuristics, scoped assessments, and product/flavor-aware recurring schedules exist, but enterprise operating controls are not enforced yet. |

## Phase 1: Backbone And Guided Adoption

### Objective

Make the platform coherent, governable, and easy to adopt on first use. This phase is about closing the gap between a promising technical foundation and a usable governed system for humans.

### What Phase 1 now includes

- authority-document-backed framework records
- custom framework shell creation
- manual framework-control authoring
- mapping approval metadata
- evidence collection plan persistence
- AWS evidence targets across product, flavor, control, account, region, and profile scope
- offline-first runtime mode for local GRC administration and reporting
- onboarding and authoring wizards in the workspace
- default first-run navigation into guided setup

### Workstreams

1. Data and governance backbone
   - add Alembic migrations and schema version tracking
   - normalize authority document lifecycle and framework version lineage
   - add explicit lifecycle enums and transition policies for framework, control, evidence, audit, and assurance objects
   - add due dates, approvers, and review cadence fields where governance depends on time

2. Guided onboarding and creation flows
   - keep the new `Wizards` workspace as the default first-run entrypoint
   - add step completion persistence and richer onboarding diagnostics
   - expand guided creation for internal policies, custom controls, questionnaires, and scoped assessments
   - add validation helpers and safer error presentation in the workspace

3. Unified control backbone hardening
   - enforce mapping approval states and reviewer metadata in operational flows
   - add citation-level mapping details for authority sources
   - add baseline evidence-plan coverage for the most important seeded standards
   - start capturing lifecycle checkpoints for control design, implementation, evidence, and monitoring

4. Phase 1 quality bar
   - add YAML schema validation
   - add service-level tests for framework, mapping, wizard, and evidence-plan behavior
   - add seed validation for control counts and duplicate detection

### Phase 1 target maturity

| Area | Current | Phase 1 target | Notes |
| --- | --- | --- | --- |
| Framework catalog | `3/5` | `3.5/5` | Governed custom shells and authority lineage should be usable. |
| Unified controls and mappings | `2.5/5` | `3/5` | Reviewable mappings and better citation governance should exist. |
| Guided workspace | `2.5/5` | `3.5/5` | First-run and high-friction creation paths should be smooth and coherent. |
| Evidence-plan governance | `2.5/5` | `3/5` | Plans should exist for key control families even if runtime is not fully plan-driven yet. |
| Lifecycle governance | `2.5/5` | `3/5` | Traceability should mature into governed state progression. |
| Security foundation | `3/5` | `3.5/5` | Secret handling and evidence storage should be consistently applied across new workflows. |

### Phase 1 exit criteria

- migrations replace `create_all` for schema evolution
- wizard-driven onboarding can bring a fresh workspace to a usable operating baseline
- custom frameworks, controls, approved mappings, and evidence plans can be created without direct DB manipulation
- at least one seeded standard has meaningful evidence-plan coverage for priority controls
- lifecycle transitions for at least framework, mapping, evidence plan, and assessment review are governed

## Phase 2: Operational GRC And Human Workflows

### Objective

Turn the governed foundation into a strong day-to-day operating system for compliance, evidence, and assurance teams.

### Workstreams

1. AWS profile operations
   - add assisted AWS CLI IAM Identity Center profile setup
   - validate profile health through `sts:GetCallerIdentity`
   - surface account, region, and role diagnostics
   - bind validated profiles directly from the workspace

2. Evidence and Confluence operations
   - make evidence execution plan-driven
   - add evidence freshness, sufficiency, and quality scoring
   - add manual evidence upload, attestation, reviewer, and expiry workflows
   - add Confluence targets by artifact type
   - add attachment upload, rerun updates, and connection health tests

3. Review and approval surfaces
   - add review queue for mappings, questionnaire answers, autonomy recommendations, and evidence verification
   - add evidence explorer with decrypt-on-demand and governed access
   - add control lifecycle dashboard with owners, overdue reviews, and blockers
   - add jobs page for schedules, run history, retries, and failures

4. Questionnaires and assessments
   - add answer approval state, provenance, and reusable answer snippets
   - add product and flavor-aware recurring schedules
   - add manual and assisted assessment playbooks with evidence support tasks
   - add explicit evidence sufficiency decisions before assessments close

### Phase 2 target maturity

| Area | Phase 1 target | Phase 2 target | Notes |
| --- | --- | --- | --- |
| Local AWS SSO operations | `3.5/5` | `4/5` | The runtime is aligned with `aws sso login`, while guided setup and diagnostics still need Phase 2 work. |
| Evidence collection engine | `2.5/5` | `3.5/5` | Plans, freshness, normalization, and assisted collection should be operational. |
| Confluence publishing | `2/5` | `3.5/5` | Attachment-capable, target-aware publishing should exist. |
| Questionnaires | `2.5/5` | `3.5/5` | Reviewable, exportable customer responses should be practical. |
| Recurring assessments | `2/5` | `3.5/5` | Schedules should be scope-aware and operationally traceable. |
| Human workspace | `3.5/5` | `4/5` | Review, evidence, jobs, and lifecycle surfaces should be first-class. |

### Phase 2 exit criteria

- a user can configure, validate, and bind AWS SSO profiles entirely from guided flows
- evidence collection is driven by applicability plus evidence plans for priority controls
- Confluence can store evidence artifacts and assessment outputs with governed destinations
- review queues exist for mappings, answers, and evidence verification
- recurring assessments can run at framework, binding, product, and flavor scope with job tracking

## Phase 3: Enterprise Autonomy, Scale, And Integration

### Objective

Make `my_grc` enterprise-ready by adding governed autonomy, integration capabilities, and operational scale.

### Workstreams

1. Governed AI and autonomous assurance
   - add model orchestration and prompt provenance
   - add review thresholds and fallback rules
   - add learning loops from approved and rejected mappings or answers
   - add autonomous assessment gating based on evidence-plan approval, collector stability, and historical confidence

2. Enterprise security and operating controls
   - add RBAC and separation of duties
   - add stronger lifecycle state machines and approval workflows
   - add retention, archival, and tamper-evident policies for evidence and assessments
   - add audit packs and sign-off bundles

3. Scale and integration
   - add background workers for evidence and assessment execution
   - add import/export APIs and event hooks
   - add connectors for external systems such as Jira, ServiceNow, Git, and non-AWS evidence sources
   - add performance features such as pagination, caching, and normalized fact stores

4. Analytics and enterprise reporting
   - add portfolio dashboards across products, flavors, frameworks, and control families
   - add coverage, freshness, assurance, and maturity reporting packs
   - add exception and remediation tracking

### Phase 3 target maturity

| Area | Phase 2 target | Phase 3 target | Notes |
| --- | --- | --- | --- |
| Unified controls backbone | `3/5` | `4/5` | Common controls should become a true cross-standard operating layer. |
| Autonomous assessments | `2.5/5` | `4/5` | Autonomy should be gated, reviewable, and policy-driven. |
| Security and governance | `3.5/5` | `4.5/5` | RBAC, approvals, retention, and traceability should be enterprise-credible. |
| Reliability and scale | `2.5/5` | `4/5` | Background jobs, retries, caching, and deterministic recomputation should be in place. |
| Integrability | `2/5` | `4/5` | APIs and connector patterns should support enterprise ecosystem fit. |
| Overall enterprise readiness | `2.5/5` | `4/5` | The system should be strong enough for production pilot and controlled rollout. |

### Phase 3 exit criteria

- autonomous assessments are enabled only for approved control families with stable evidence logic
- APIs and event integrations exist for imports, exports, and connector orchestration
- RBAC and approval segregation are enforced across high-risk workflows
- background workers execute evidence and assessment workloads reliably
- dashboards and reporting packs support auditors, operators, and leadership

## Functional gaps to keep visible

- full internal-policy authoring workflow with bulk control import
- applicability and inheritance rules as a first-class engine
- evidence-plan-driven execution across all collectors
- artifact-centric Confluence publishing
- questionnaire export, override, redaction, and approval
- recurring schedules at product and flavor scope
- full multi-standard onboarding for NIST CSF 2.0 and ENS alto
- enterprise review queue and exception workflow

## Non-functional gaps to keep visible

### Security

- RBAC is missing
- approval segregation is missing
- decrypt-on-demand access policy is missing
- rotation policy for secrets is still shallow

### Quality

- migration framework is missing
- automated tests are missing for new governance and wizard flows
- validation for imports and templates is incomplete

### Reliability

- no retry orchestration or durable jobs
- no run locking or concurrency protection
- evidence freshness and sufficiency are not enforced globally

### Scalability

- long-running operations are still interactive
- no worker topology exists
- evidence and questionnaire views need pagination and filtering

### Integrability

- no external API surface exists
- no webhook or event model exists
- external artifact systems are only modeled lightly today

## Recommended immediate next slice

The best next build slice inside Phase 1 is:

1. add Alembic migrations
2. add lifecycle transition rules for mappings, evidence plans, and assessment review
3. extend the new wizard flow with validation and onboarding completion tracking
4. start evidence-plan coverage for ISO 27001 Annex A priority controls

That sequence keeps the current foundation coherent while raising the real maturity of the system instead of only expanding surface area.
