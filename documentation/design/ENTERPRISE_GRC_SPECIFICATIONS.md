# Enterprise GRC Specifications

## Objective

`my_grc` should become an enterprise-grade control operations platform, not only a framework catalog or an evidence collector. It must support:

- GRC analysts
- control owners
- product and platform teams
- assurance and audit stakeholders
- implementation teams that need to provide manual evidence or narratives when automation is incomplete

## Functional specification

### 1. Converged control baseline

The system needs one durable control backbone.

Required capability:

- import standards, regulations, internal policies, and guides from structured sources
- normalize them into framework controls
- map them into unified controls
- preserve traceability from each framework requirement into the unified control
- allow one unified control to map to many frameworks and many practical guides

Current design direction:

- SCF is the pivot baseline
- other frameworks map into that baseline
- `ReferenceDocument` extends the model beyond standards into practical guidance

### 2. Implementation-centered control management

The platform must distinguish:

- requirement
- control
- implementation
- test method
- evidence
- assurance result

Required capability:

- define how a control is implemented by organization, product, and flavor
- support different implementations for the same unified control
- attach ownership, lifecycle, blockers, priority, and testing strategy

### 3. Manual, assisted, and automated evidence

Automation will never cover every control.

Required capability:

- collectors for fully automated evidence
- script-module bindings for existing Python assessments
- manual evidence upload for human-provided artifacts
- assisted workflows for cases that need login approval, screenshots, exports, or narrative confirmation
- evidence review and approval before assurance is finalized

### 4. Guide-aware implementation support

Teams implementing controls need more than mapped requirements. They need practical help.

Required capability:

- explicit references to NIST, CCN-STIC, internal standards, hardening guides, and runbooks
- link those references to unified controls and implementation records
- surface them inside questionnaires, control design pages, and remediation work

### 5. Assessment and assurance operations

Required capability:

- run assessments by framework, product, flavor, or converged control scope
- reuse evidence across mapped controls when governance allows it
- support recurring schedules and assisted runs
- preserve run history, decisions, exceptions, and assurance state

### 6. Questionnaire response support

Required capability:

- map customer questions to unified controls and implementation records
- answer from implementation narratives, not only evidence
- highlight confidence and missing information
- route weak answers for human review

## Non-functional specification

### Security

- encrypted evidence at rest
- keyring or secret-file backed secret handling
- no default storage of sensitive tokens in environment variables
- audit logs for user and system actions
- governed lifecycle transitions for critical artifacts

### Quality

- migrations for all schema changes
- import presets and validation for major source formats
- tests for import, mapping, lifecycle, and evidence workflows
- deterministic traceability from requirement to assessment

### Reliability

- offline-first local operation
- idempotent imports where practical
- safe retry patterns for external connectors
- schedule run locking and health visibility

### Scalability

- modular collectors and script bindings
- normalized reference documents reused across many controls
- product/flavor/account/region scoping without duplicating frameworks
- container-ready runtime for Ubuntu and future hardened Docker deployment

### Integrability

- external script modules for existing assessments
- importers for CSV/XLSX framework sources
- future API and event-hook path for external systems
- Confluence publishing and attachment support

## Roles and operating model

### GRC team

- owns framework ingestion
- governs mappings
- defines evidence plans
- approves assurance outputs

### Control owner / implementation team

- maintains implementation records
- attaches manual evidence
- validates operating effectiveness
- contributes remediation and lifecycle updates

### Auditor / assurance stakeholder

- reviews traceability
- validates assessment outcomes
- inspects evidence and lifecycle history

## Recommended modular architecture

### Ingestion layer

- framework import presets
- guide import presets
- source validation and provenance capture

### Control convergence layer

- unified controls
- mappings
- reference library
- AI-assisted suggestions with human approval

### Implementation layer

- products
- flavors
- control implementations
- product control profiles

### Evidence and assessment layer

- evidence plans
- native collectors
- script-module bindings
- manual evidence intake
- assessment runs and schedules

### Experience layer

- guided wizards
- universal CRUD and asset catalog
- artifact explorer
- help center and AI assistance

## Current maturity view

Strong foundations already in place:

- offline-first workspace
- unified control model
- AWS SSO profile metadata and evidence scope targeting
- script-module model for external assessments
- framework import traceability

Main gaps still to close for a clean enterprise-grade level 4:

- curated import presets for major sources beyond SCF
- richer review workflows for imported references and mappings
- stronger RBAC and separation of duties
- background execution, retries, and job observability
- deeper UI for guide-reference authoring and manual evidence collaboration

## Practical specification for manual evidence contributors

When a team cannot automate a control today, the system should still let them succeed:

1. locate the product, flavor, and control
2. read the mapped requirement and guide references
3. understand the evidence plan and manual instructions
4. upload or link the artifact
5. explain scope, date, and rationale
6. submit it for review
7. see whether the evidence supported or blocked the assessment

That workflow is what turns the platform into a useful enterprise control operations tool instead of a GRC-only repository.
