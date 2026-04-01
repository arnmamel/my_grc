# Implementation Maturity Summary

This summary reflects the current state of `my_grc` after introducing the merged backend data model.

## Maturity scale

- `Implemented`: usable now in the current codebase
- `Foundation`: schema and basic plumbing exist, but the full user workflow is not complete
- `Partial`: some working behavior exists, but important parts are missing
- `Planned`: designed or documented, not yet implemented

## Requirement maturity

### 1. Manage compliance frameworks

Status: `Implemented`

Covered by:

- framework catalog model
- YAML templates
- framework seeding and listing
- CLI management commands

Notes:

- Strong for catalog management
- Import of arbitrary spreadsheet-based frameworks is still pending

### 2. Manage unified controls across multiple standards

Status: `Foundation`

Covered by:

- `UnifiedControl`
- `UnifiedControlMapping`
- CLI commands to create and map unified controls

Missing:

- automatic harmonization suggestions
- mapping UI
- importer from `grc-master`
- inheritance-aware assessment rollups

### 3. Use the user’s local AWS CLI SSO profile with `boto3`

Status: `Implemented`

Covered by:

- local session creation through `boto3.Session(profile_name=..., region_name=...)`
- framework enablement and organization framework bindings

Missing:

- evidence execution through organization bindings
- account discovery and validation helpers

### 4. Collect AWS evidence against enabled compliance controls

Status: `Partial`

Covered by:

- evidence engine
- collector registry
- persisted evidence items
- several working AWS collectors

Missing:

- most collector coverage for the expanded standards catalog
- organization-bound evidence execution
- attachment handling and richer evidence typing

### 5. Securely store evidence and assessment outputs in Confluence

Status: `Partial`

Covered by:

- Confluence page creation
- evidence page publishing
- assessment report publishing

Missing:

- update/upsert semantics
- page hierarchy management
- attachments
- richer error handling and retry logic
- organization-specific Confluence routing strategy

### 6. Run periodic assessments monthly, quarterly, yearly

Status: `Implemented`

Covered by:

- recurring schedule model
- due schedule execution
- multi-framework schedule support

Missing:

- background scheduler/worker process
- org-aware schedule scoping
- schedule lifecycle operations like pause/resume/history

### 7. Run assessments against one or more standards

Status: `Implemented`

Covered by:

- multi-framework assessment run entrypoint
- multi-framework schedules

Missing:

- unified cross-standard scoring
- program-level reporting and dashboarding

### 8. Store analyst-authored implementation guidance and control lifecycle data

Status: `Foundation`

Covered by:

- `ControlImplementation`
- fields for objective, AWS notes, on-prem notes, lifecycle, owner, priority, blockers, test plan, evidence links, Jira, ServiceNow
- CLI upsert/list support

Missing:

- UI for editing
- import from `grc-master`
- approval workflow
- history/versioning

### 9. Preserve rich framework-control metadata

Status: `Implemented`

Covered by:

- `ControlMetadata`
- template seeding of summary, AWS guidance, check type, boto3 check description, boto3 services

Missing:

- richer source references
- presentation/UI

### 10. Keep per-control assessment snapshots

Status: `Implemented`

Covered by:

- `AssessmentRunItem`
- run-time snapshot creation during assessments

Missing:

- linkage to unified controls and implementation records during assessment
- per-control trend analysis

### 11. Provide a human-friendly GRC workspace

Status: `Planned`

Covered by:

- backend schema now supports it

Missing:

- UI/workbench
- import wizard
- mapping screen
- analyst dashboard
- AI suggestion persistence and review

## Functional specifications to contemplate

These should be part of the target merged product backlog.

### Governance and modeling

- organization and tenant management
- framework catalog management
- spreadsheet and workbook ingestion
- framework versioning
- unified control management
- crosswalk and inheritance mapping
- control ownership and lifecycle management
- policy, procedure, and implementation note storage

### Assessment operations

- framework enablement by AWS scope
- assessment programs spanning multiple standards
- recurring schedules
- manual attestation steps
- applicability and exception handling
- compensating controls
- risk acceptance workflow
- weighted scoring models

### Evidence operations

- automated AWS evidence collection
- manual evidence upload and URL linking
- evidence freshness rules
- evidence approval/review state
- evidence lineage and provenance
- evidence reuse across mapped controls
- evidence retention and archival

### Integrations

- Confluence pages and attachments
- Jira links and issue sync
- ServiceNow links and ticket sync
- identity providers and SSO metadata
- notification channels
- import/export APIs

### Analyst productivity

- spreadsheet import wizard
- record-level editing UI
- focus mode for deep control work
- AI assistance for implementation text, objectives, and test plans
- audit dashboards and reporting
- search, filters, and coverage views

## Non-functional specifications to contemplate

### Security

- secure handling of AWS credentials and SSO sessions
- least-privilege AWS permissions for evidence collection
- secrets management for Confluence/API tokens
- encryption at rest for local databases and cached evidence where needed
- strong audit logging of administrative actions
- RBAC for future UI/API users
- tenant isolation if the system becomes multi-user
- input validation and safe rendering of imported files and HTML content

### Quality

- unit, integration, and end-to-end tests
- schema migration strategy
- static analysis and linting
- deterministic collectors with mockable AWS interfaces
- fixture-based tests for framework seeding and mappings

### Reliability

- retry strategy for AWS and Confluence operations
- idempotent publishing and evidence collection runs
- safe recovery from partial failures
- schedule execution resilience
- corruption-safe local persistence and backup procedures

### Scalability

- support for many frameworks, accounts, and evidence records
- pagination and batch processing for large AWS estates
- multi-account and multi-region collection strategy
- background worker model for heavier assessment runs

### Performance

- incremental evidence collection
- collector concurrency where safe
- caching of invariant AWS metadata
- efficient query paths for mappings and dashboards

### Integrability

- stable service layer and internal APIs
- external API surface for UI and automations
- import/export formats for frameworks and mappings
- webhook or event integration for external systems

### Observability

- structured logs
- collector execution metrics
- assessment timing metrics
- failure diagnostics for integrations
- evidence traceability per run and per control

### Maintainability

- modular collector architecture
- clear domain boundaries between framework catalog, unified control model, and execution engine
- migration documentation
- backward-compatible schema evolution where possible

### Usability

- guided onboarding
- good error messages for missing AWS profiles or permissions
- visible distinction between automated, hybrid, and manual checks
- clear evidence and assessment status models

### Compliance and privacy

- retention policies for evidence and reports
- PII minimization in stored evidence payloads
- secure handling of audit artifacts
- ability to trace and justify assessment decisions

## Recommended next priorities

1. Import `grc-master.db` into the merged model.
2. Build organization-aware evidence collection using `OrganizationFrameworkBinding`.
3. Port the `grc-master` Streamlit workspace onto the new `my_grc` backend.
4. Expand collector coverage for the highest-value AWS-native controls.
5. Add tests and migration tooling before broader functional expansion.
