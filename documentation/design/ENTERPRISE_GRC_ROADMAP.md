# Enterprise GRC Roadmap

## Scope of this pass

This pass moves `my_grc` closer to the operating model we want:

- product and flavor-aware implementations already existed in the data model and were tightened
- scoped evidence collection was extended to organization framework bindings, products, and product flavors
- scoped assessments were extended to organization framework bindings, products, and product flavors
- product control profiles now link back to matching implementations when possible
- implementation records now get stable generated codes when the user does not provide one
- questionnaire answering now falls back across flavor-specific, product-level, and organization-level implementations
- the Streamlit workspace now includes an `Operations` surface for scoped evidence collection and assessments

This is meaningful progress, but it is still an early enterprise foundation.

## Current maturity by requirement

Scale:

- `0/5`: not started
- `1/5`: concept only
- `2/5`: foundation exists
- `3/5`: usable with material gaps
- `4/5`: strong, needs hardening
- `5/5`: enterprise-ready

| Requirement area | Maturity | Current state | Main gap |
| --- | --- | --- | --- |
| Framework management | 3/5 | YAML-backed frameworks exist and seed into the DB. | Missing NIST CSF 2.0, ENS alto, internal policies, and richer authority-document versioning. |
| Unified controls and mappings | 2/5 | Unified controls, mappings, confidence, and CSV suggestion heuristics exist. | Missing lifecycle management, authoritative citation model, review queue, and mapping governance. |
| Product and flavor-aware control model | 3/5 | `Product`, `ProductFlavor`, `ControlImplementation`, `ProductControlProfile`, questionnaires, evidence, and assessments are now scope-aware. | Applicability inheritance and control coverage resolution are still basic. |
| Evidence collection engine | 2/5 | Collector framework exists and now supports binding/product/flavor scope. | Collector coverage is still limited, evidence plans are not normalized, and applicability-driven execution is incomplete. |
| Confluence publishing | 2/5 | Page creation works in principle and binding-specific parent pages are supported. | No interactive PAT capture, no encrypted local secret storage, no attachment upload workflow, and no connection health checks. |
| Local AWS SSO with `boto3` | 3/5 | The runtime already uses named local profiles with `boto3.Session(profile_name=...)`. | No guided profile setup assistant, validation wizard, or human-friendly diagnostics. |
| Recurring assessments | 2/5 | Monthly, quarterly, and yearly schedules exist. | Schedules are not yet scoped by product/flavor/mode, and autonomy gating is still heuristic. |
| Manual, assisted, and autonomous assessments | 2/5 | The maturity model and scoped assessment plumbing exist. | No evidence sufficiency rules, no autonomous decision policy, and no human sign-off workflow. |
| Multi-standard assessments | 3/5 | Multiple frameworks can be assessed in one run. | The unified-control backbone is not mature enough yet to make this seamless across many new standards. |
| Customer questionnaire answering | 2/5 | CSV questionnaires can be previewed and answered from implementation records without evidence. | Needs answer governance, approval state, richer matching, and reusable answer libraries. |
| Human workspace | 2/5 | Streamlit workspace now covers portfolio, unified controls, mapping lab, operations, questionnaires, and maturity. | Missing import governance, connection management, evidence explorer, jobs, and review workflows. |
| AI-assisted autonomy | 2/5 | CSV mapping suggestions and heuristic questionnaire matching exist. | No model orchestration, confidence thresholds, human review queue, or prompt provenance. |

## Improvement analysis by direction

### 1. Product and flavor-aware controls

The product dimension is now represented in code, but it needs one more layer to become operationally correct:

- A unified control must be implementable at multiple scopes:
  - organization/global
  - product
  - product flavor
  - inherited from shared platform services
- Applicability must be explicit:
  - `applicable`
  - `not_applicable`
  - `inherited`
  - `planned`
- Evidence collection must resolve scope before execution:
  - binding-global evidence
  - product evidence
  - flavor evidence
  - inherited evidence from a shared implementation

Recommended next additions:

- `ImplementationPattern` entity for reusable control patterns such as `aws-saas`, `aws-single-tenant`, `hybrid`, `internal-it`
- `ProductInheritance` or `SharedServiceDependency` entity to model controls inherited from platform services
- `ControlApplicabilityRule` entity to express when a unified control applies to a product or flavor
- `EvidenceCollectionPlan` entity to define exactly what evidence is required per control and scope

### 2. Unified controls and mappings as the backbone

This is the most strategic area.

The current model is a good start, but mature common-control systems such as the Secure Controls Framework and Unified Compliance emphasize a few things we still need:

- a normalized common-control catalog
- transparent mappings back to authority documents
- confidence and rationale for each mapping
- lifecycle tracking for controls
- objective testing criteria
- reuse across many standards

The target unified control backbone should include:

- common control taxonomy
  - code, name, objective, domain, family, control type
  - preventive, detective, corrective
  - governance, technical, operational, privacy
- authoritative mapping model
  - source document
  - source version
  - citation identifier
  - mapping type
  - confidence
  - rationale
  - reviewer
  - approval status
- lifecycle model
  - designed
  - implemented
  - evidenced
  - assessed
  - monitored
  - improved
- control-operating model
  - owner
  - frequency
  - tooling
  - implementation pattern
  - expected evidence set
  - test procedure
  - failure handling

AI should help here, but not replace governance. The right pattern is:

- AI suggests new mappings
- the system records confidence and rationale
- a human approves or rejects
- the decision becomes training data and audit history

### 3. Evidence collection engine

The current evidence engine is still collector-centric. It needs to become plan-centric.

Target design:

1. Determine the applicable controls for a binding/product/flavor.
2. Resolve the implementation and maturity profile for each control.
3. Resolve the evidence plan for the control.
4. Execute automated collectors where supported.
5. Create assistance tasks where evidence needs human upload or review.
6. Store normalized evidence records and publish selected artifacts to Confluence.
7. Score evidence freshness, sufficiency, and quality before using it in assessments.

Missing capabilities to add next:

- collector capability registry:
  - supported AWS services
  - required permissions
  - expected output schema
  - confidence level
- evidence normalization:
  - resource identifiers
  - region
  - account
  - timestamps
  - raw payload
  - normalized facts
  - evidence quality score
- human-assisted evidence:
  - upload path
  - manual attestation
  - reviewer
  - expiry
- applicability-aware execution:
  - skip non-applicable controls
  - honor inherited controls
  - use flavor override when present

### 4. AWS SSO assisted configuration

The runtime already follows the right technical direction:

- AWS CLI IAM Identity Center profiles are configured via `aws configure sso`
- `boto3` supports using those shared config profiles through `Session(profile_name=...)`

What is missing is the human workflow.

The assistant should:

- guide a user through profile creation without forcing them to edit `~/.aws/config` manually
- validate that the profile can log in and call `sts:GetCallerIdentity`
- detect the configured account, role, and default region
- list existing profiles and flag broken ones
- let the user bind a profile to a framework binding from the workspace

Important design principle:

- store only profile names and diagnostics in `my_grc`
- do not copy or persist AWS session tokens

### 5. Confluence publishing and PAT handling

Current Confluence integration is only the first layer.

Enterprise-grade requirements here are:

- interactive PAT entry without echoing the token back in the UI
- encryption at rest for the stored secret
- TLS verification in transit
- connection test before first use
- configurable target spaces/pages per organization and per artifact type
- page publishing
- attachment upload
- update behavior for reruns
- labels and metadata for traceability

Recommended next design:

- `ConfluenceConnection`:
  - base URL
  - auth mode
  - username
  - verification policy
  - default space
  - status
- `SecretEnvelope`:
  - encrypted token blob
  - key identifier
  - created at
  - last rotated at
- `ConfluenceTarget`:
  - organization
  - artifact type
  - space
  - parent page
  - attachment policy

Preferred storage options:

- OS keychain/keyring first
- encrypted local secret store second

### 6. Recurring, manual, assisted, and autonomous assessments

The maturity model is now present, but it is only a heuristic starting point.

The 5 dimensions are still the right direction:

- governance
- implementation
- observability
- automation
- assurance

However, autonomous assessment should not be enabled only because a score is high. It should require:

- an approved evidence plan
- supported automated collectors
- stable normalized outputs
- control logic that can interpret the evidence deterministically
- minimum evidence freshness
- historical success rate
- explicit human approval for autonomous mode

Recommended operating modes:

- `manual`
  - humans gather evidence and decide compliance
- `assisted`
  - the system gathers some evidence and drafts the result
- `autonomous`
  - the system gathers, evaluates, and proposes outcome automatically
- `autonomous_verified`
  - the system is trusted to close a control outcome unless an exception is raised

### 7. Multi-standard assessments

To make multi-standard operation truly seamless, new standards should plug in through the unified control layer rather than through one-off code paths.

Required standard onboarding model:

- authority document
- version
- structured citations
- control records
- metadata
- mappings to unified controls
- assessment guidance
- evidence expectations

That will let us add:

- internal policies
- ISO 27001
- ISO 27017
- GSMA SAS-SM FS.18 v11.1
- CSA CCM
- NIST CSF 2.0
- ENS alto

without redesigning the engine each time.

### 8. Customer questionnaire answering

This requirement is strategically strong and should stay implementation-driven, not evidence-driven.

Target flow:

1. Load questionnaire CSV/XLSX/template.
2. Detect question structure and normalize fields.
3. Match each question to unified controls and implementation records.
4. Draft answers using the implementation narrative.
5. Include rationale, source implementation, confidence, and review status.
6. Let humans review, approve, and export.

Required improvements:

- reusable answer snippets per control and per product flavor
- answer approval workflow
- customer-specific overrides
- export formats
- redaction support
- provenance trail showing exactly which implementation the answer used

### 9. Human workspace

The current workspace is now a useful starter, not just a placeholder.

Current pages:

- `Overview`
- `Standards`
- `Portfolio`
- `Unified Controls`
- `Mapping Lab`
- `Operations`
- `Questionnaires`
- `Maturity Studio`

Next workspace increments should add:

- `AWS Profiles`
  - assisted SSO setup and validation
- `Confluence Connections`
  - secure PAT onboarding and page targets
- `Imports`
  - framework CSV import, mapping import, questionnaire import
- `Review Queue`
  - AI mapping suggestions, questionnaire answers, autonomy recommendations
- `Evidence Explorer`
  - latest evidence, diffs, attachments, freshness
- `Jobs`
  - schedules, queued runs, failures, retries
- `Control Lifecycle`
  - implementation health, gaps, owners, overdue reviews

## Functional specification checklist

The merged product should contemplate at least the following functional capabilities:

- framework catalog management
- authority document versioning
- unified control library
- authority-to-unified mappings
- product and product flavor management
- control applicability and inheritance
- organization/framework AWS bindings
- guided AWS SSO profile setup and validation
- control implementation narratives per scope
- evidence plans per control and scope
- automated AWS evidence collectors
- assisted evidence uploads and attestations
- Confluence page and attachment publishing
- manual assessments
- assisted assessments
- autonomous assessments with approval gates
- recurring schedules per scope
- questionnaire answering from implementations
- AI suggestion workflows for mappings and answers
- review and approval trails
- reporting and export

## Non-functional specification checklist

### Security

- encrypted secret handling for PATs and any future connector secrets
- no storage of AWS session credentials
- least-privilege AWS collector permissions
- RBAC for workspace actions
- audit trail for mappings, approvals, and assessment outcomes
- secure transport with TLS verification
- tamper-evident evidence and assessment history

### Quality

- migrations instead of `create_all` only
- schema validation for framework YAML and CSV imports
- unit tests for services and mapping logic
- golden tests for collectors and questionnaire answering
- seed data validation for control counts and unique IDs

### Reliability

- idempotent collector runs
- retries with backoff for AWS and Confluence calls
- partial-failure handling per control
- job status tracking
- evidence freshness and staleness policies
- deterministic assessment recomputation

### Scalability

- background job runner for collection and assessments
- pagination for evidence and questionnaire items
- normalized fact extraction to reduce repeated raw parsing
- caching for framework/mapping lookups
- separation of interactive UI from long-running jobs

### Integrability

- import/export API
- CSV/XLSX adapters
- webhook or event integration for external systems
- Jira/ServiceNow/Git links as first-class artifacts
- future connector model for non-AWS evidence sources

## Recommended phased plan

### Phase 1: Hardening the backbone

- add migrations
- add authority document versioning
- add NIST CSF 2.0 and ENS framework templates
- add mapping approval states
- add evidence plan entities

### Phase 2: Human operations

- AWS profile assistant
- Confluence connection manager with secure PAT storage
- evidence explorer
- import/review queue

### Phase 3: Autonomy

- richer AI mapping suggestions
- answer library and questionnaire review workflow
- applicability-driven evidence execution
- autonomous assessment gating

### Phase 4: Enterprise operations

- background workers
- API layer
- audit logs
- role-based permissions
- dashboards and reporting packs

## External references used for this roadmap

- AWS CLI IAM Identity Center configuration: [docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)
- Boto3 configuration and profile usage: [docs.aws.amazon.com/boto3/latest/guide/configuration.html](https://docs.aws.amazon.com/boto3/latest/guide/configuration.html)
- Boto3 IAM Identity Center credential provider: [docs.aws.amazon.com/boto3/latest/guide/credentials.html](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)
- NIST CSF 2.0: [nist.gov/publications/nist-cybersecurity-framework-csf-20](https://www.nist.gov/publications/nist-cybersecurity-framework-csf-20)
- ENS legal basis: [boe.es/diario_boe/txt.php?id=BOE-A-2022-7191](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2022-7191)
- Confluence PAT guidance: [confluence.atlassian.com/display/ENTERPRISE/Using%2BPersonal%2BAccess%2BTokens](https://confluence.atlassian.com/display/ENTERPRISE/Using%2BPersonal%2BAccess%2BTokens)
- Confluence attachment REST API: [developer.atlassian.com/server/confluence/rest/v931/api-group-attachments/](https://developer.atlassian.com/server/confluence/rest/v931/api-group-attachments/)
- Secure Controls Framework: [securecontrolsframework.com](https://securecontrolsframework.com/)
- Unified Compliance common controls: [support.unifiedcompliance.com/knowledgebase/unified-compliance](https://support.unifiedcompliance.com/knowledgebase/unified-compliance)
