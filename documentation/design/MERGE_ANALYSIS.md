# Merge Analysis: `grc-master` and `my_grc`

## Executive Summary

The two projects are complementary rather than redundant.

- `grc-master` is strongest as a compliance workbench:
  - import wizard for Excel/CSV
  - manual control authoring and editing
  - cross-standard mapping workflow
  - AI-assisted drafting
  - existing Streamlit UI
- `my_grc` is strongest as an execution engine:
  - framework templates in YAML
  - local AWS SSO profile support with `boto3`
  - evidence collection and persistence
  - assessment runs and schedules
  - Confluence publishing

The recommended direction is:

1. Keep `my_grc` as the core backend/domain model.
2. Port the useful `grc-master` workspace features into a UI layer on top of `my_grc`.
3. Extend `my_grc` with unified control mapping and imported-standard workflows.

This gives one usable tool that matches the target requirements:

- manage full compliance frameworks and unified controls
- use local AWS CLI SSO profiles
- collect AWS evidence with `boto3`
- store outputs in Confluence
- run recurring assessments across one or more standards
- provide a human-friendly workspace for mapping, authoring, and exception handling

## 1. What `grc-master` already covers

### 1.1 Working features

`grc-master` is a Streamlit application centered on analyst workflows.

- UI modules:
  - internal controls workspace in [app.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/app.py#L155)
  - external standards library in [app.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/app.py#L398)
  - mapping and crosswalk module in [app.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/app.py#L422)
  - basic reports/integrity screen in [app.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/app.py#L485)
- File import with normalization and column mapping:
  - upload logic in [app.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/app.py#L74)
  - mapping wizard in [ui_components.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/ui_components.py)
- SQLite persistence with upsert behavior:
  - schema/init in [db_manager.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/db_manager.py#L46)
  - import/upsert in [db_manager.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/db_manager.py#L110)
  - mapping persistence in [db_manager.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/db_manager.py#L215)
- Analyst editing fields already modeled:
  - objective
  - AWS implementation notes
  - on-prem implementation notes
  - test plan
  - evidence links
  - owner / lifecycle / status / priority
  - schema in [column_config.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/config/column_config.py#L10)
- AI-assisted drafting with Gemini:
  - implementation suggestions in [ai_assistant.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/ai_assistant.py#L100)
  - test plan suggestions in [ai_assistant.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/ai_assistant.py#L133)
  - objective suggestions in [ai_assistant.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/ai_assistant.py#L157)
- Existing automated tests:
  - 12 test cases in `grc-master/tests`

### 1.2 Architectural strengths

- Very useful for humans doing GRC authoring and review.
- Good import story for spreadsheets and existing matrices.
- Good fit for control harmonization and manual enrichment.
- The control editor already has fields that map well to real compliance work.

### 1.3 Gaps and limitations

The biggest issue is that `grc-master` is not yet an AWS evidence engine.

- No AWS SSO or `boto3` execution layer.
- No evidence collection model or collector abstraction.
- No recurring assessment engine.
- No Confluence API integration, only free-text evidence links.
- No real assessment scoring beyond manually edited fields.
- No separation between:
  - organizations
  - frameworks
  - framework requirements
  - unified controls
  - evidence records
  - assessment runs

There are also documented features that are not implemented yet:

- `README.md` claims dashboard/reporting and Confluence export in [README.md](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/README.md#L57)
- but the UI helpers are stubs in [ui_components.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/ui_components.py#L123)
- the "Reports" screen currently just calls `verify_database_integrity()` in [app.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/app.py#L485)

There are also placeholder repository classes that are not implemented in [repositories.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/db/repositories.py).

### 1.4 Important schema caveat

`grc-master` stores both the internal control set and external standards in the same `requirements` table, keyed by `(standard, req_id)`:

- schema in [db_manager.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/src/db_manager.py#L55)
- internal control workspace loads records using the organization name as the "standard" key in [app.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/grc-master/app.py#L156)

That makes rapid prototyping easy, but it is too flat for the target product.

## 2. What `my_grc` already covers

### 2.1 Working features

`my_grc` is a backend-oriented compliance execution tool.

- Framework catalog and control seeding:
  - template loading in [framework_loader.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/framework_loader.py#L12)
  - framework seeding and enablement in [frameworks.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/services/frameworks.py#L14)
- Explicit domain model for:
  - frameworks
  - controls
  - evidence items
  - assessment runs
  - schedules
  - models in [models.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/models.py)
- Local AWS CLI SSO profile execution:
  - `boto3.Session(profile_name=..., region_name=...)` in [aws_session.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/aws_session.py#L6)
- Evidence collection engine:
  - collection flow in [evidence.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/services/evidence.py#L20)
- Real collector implementations for several AWS controls:
  - IAM password policy
  - CloudTrail
  - AWS Config recorder
  - GuardDuty
  - Security Hub
  - S3 default encryption
  - EBS default encryption
  - collectors in [security.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/collectors/security.py)
- Assessment engine:
  - one framework or multiple frameworks in [assessments.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/services/assessments.py#L36)
- Scheduling:
  - monthly / quarterly / yearly schedules in [assessments.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/services/assessments.py#L73)
- Confluence publishing:
  - page creation in [confluence.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/integrations/confluence.py#L39)
- CLI for operations:
  - commands in [cli.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/cli.py)

### 2.2 Content already prepared

- Multiple standards/templates exist:
  - ISO/IEC 27001:2022
  - ISO/IEC 27017
  - ISO/IEC 27018
  - GSMA SAS-SM FS.18
  - CSA CCM
- ISO 27001 Annex A has been expanded to a full 93-control catalog in [iso_27001_2022.yaml](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/templates/frameworks/iso_27001_2022.yaml)

### 2.3 Architectural strengths

- Much closer to the target product requirements.
- Better domain separation than `grc-master`.
- Already shaped like an automation-capable compliance engine.
- Easier foundation for future APIs, job runners, and integrations.

### 2.4 Gaps and limitations

`my_grc` currently has the right architecture but not enough breadth yet.

- No interactive UI or workbench.
- No spreadsheet import/mapping workflow.
- No cross-standard harmonization or unified control inheritance model.
- No AI-assisted drafting layer.
- No tests yet.
- No migration tooling yet.
- Confluence integration only creates pages; it does not:
  - update existing pages
  - manage attachments
  - manage page hierarchies deeply
  - deduplicate by title or key
- Assessment scoring is currently a simple pass ratio.

Most importantly, the framework catalog is ahead of the collector implementation:

- total `evidence_query` entries across templates: 106
- unique `evidence_query` values: 96
- implemented collector keys: 7
- missing collector queries: 89

That gap is handled explicitly in [evidence.py](/C:/Users/arnmata/OneDrive/Aplicaciones/Projects/my_grc/src/aws_local_audit/services/evidence.py#L37), where unsupported checks are stored as `not_implemented`.

## 3. What is common between both projects

These capabilities overlap conceptually:

- local SQLite persistence
- multi-standard compliance management
- control-centric workflows
- evidence-oriented thinking
- support for AWS implementation details
- local/offline execution model

But they overlap at different layers:

- `grc-master` overlaps at the analyst workspace layer
- `my_grc` overlaps at the execution and assessment layer

So they should not be merged by simply copying files together. They need a deliberate new architecture.

## 4. Gap analysis against the desired final tool

Desired final requirements:

1. Manage full compliance frameworks and unified controls.
2. Use the user’s local AWS SSO profile with AWS CLI and `boto3`.
3. Collect AWS evidence against enabled frameworks.
4. Store evidence and outputs in Confluence.
5. Run periodic assessments monthly, quarterly, yearly.
6. Support one or more standards per assessment cycle.
7. Provide a practical human workflow for mapping, authoring, and reviewing controls.

### 4.1 Coverage by `grc-master`

- Requirement 1: partial
- Requirement 2: not covered
- Requirement 3: not covered
- Requirement 4: not covered
- Requirement 5: not covered
- Requirement 6: partial, only conceptually through mappings
- Requirement 7: strong

### 4.2 Coverage by `my_grc`

- Requirement 1: partial to strong for framework catalogs, weak for unified control harmonization
- Requirement 2: covered
- Requirement 3: covered in foundation, partial in breadth
- Requirement 4: covered in foundation
- Requirement 5: covered in foundation
- Requirement 6: covered
- Requirement 7: weak

## 5. Recommended merge direction

## Recommendation

Use `my_grc` as the product core and absorb the best parts of `grc-master` into it.

Reason:

- `my_grc` already models the core entities the final tool really needs.
- `grc-master` has better UX features, but its data model is too flat to serve as the long-term backbone.
- Rebuilding `my_grc`’s missing UI/workbench features is easier than forcing AWS evidence, schedules, and assessment history into the current `grc-master` schema.

## 6. Proposed unified target architecture

### 6.1 Core backend

Base this on `my_grc` and expand the schema to include:

- `organizations`
- `frameworks`
- `framework_requirements`
- `unified_controls`
- `framework_requirement_mappings`
- `control_implementations`
- `evidence_collectors`
- `evidence_items`
- `assessment_runs`
- `assessment_run_items`
- `assessment_schedules`
- `integration_links`
- `ai_suggestions`

### 6.2 UI/workbench layer

Bring over from `grc-master`:

- import wizard for Excel/CSV
- focus-mode editor
- manual cross-standard mapping screen
- matrix import for existing crosswalks
- AI drafting for:
  - objective
  - AWS implementation guidance
  - test plan

Fastest route:

- keep using Streamlit initially
- replace `grc-master`’s direct DB calls with calls into `my_grc` services

Longer-term route:

- move to API + frontend if multi-user or enterprise workflows become important

### 6.3 Execution engine

Keep and expand from `my_grc`:

- framework seeding from YAML
- local AWS SSO session handling
- collector registry
- evidence persistence
- Confluence publishing
- recurring assessments

## 7. Proposed merge phases

### Phase 1: Establish `my_grc` as the single source of truth

- Rename package/module from `aws_local_audit` to `my_grc` if desired.
- Add Alembic migrations.
- Keep the current SQLAlchemy model as the canonical persistence layer.
- Add test scaffolding.

### Phase 2: Add the GRC workbench schema and imports

- Add imported framework/requirement support.
- Add unified control tables and mapping tables.
- Write a migration/importer from `grc-master.db` into the new schema.

Migration mapping:

- `grc-master.requirements` rows used as internal controls:
  - become `unified_controls` or organization-specific control implementations
- `grc-master.requirements` rows used as external standards:
  - become imported `framework_requirements`
- `grc-master.mappings`:
  - become `framework_requirement_mappings`
- `impl_aws`, `impl_onprem`, `objective`, `test_plan`, `evidence_links`:
  - become analyst-authored implementation and audit metadata

### Phase 3: Port the `grc-master` UI

- Build a Streamlit app inside `my_grc`:
  - standards library
  - control workbench
  - mapping view
  - assessment dashboard
  - evidence browser
- Replace raw DB/DataFrame logic with service-layer calls.

### Phase 4: Expand collector coverage

Start with the most AWS-native and highest-value checks:

- cloud governance baseline
- privileged access review
- access restriction
- backup coverage
- logging and monitoring
- network security baseline
- environment separation
- vulnerability management
- DLP / public exposure
- Confluence evidence synchronization quality

### Phase 5: Improve assessment realism

- Add per-control grading:
  - automated pass/fail
  - manual attestation
  - inherited control
  - not applicable
  - accepted risk
- Add weighted scoring by severity and control type.
- Add framework-level rollups and unified control rollups.

## 8. Recommended final product shape

The final merged tool should look like this:

- one Python project: `my_grc`
- one database schema
- one service layer
- one UI/workbench
- one collector engine
- one assessment scheduler
- one Confluence publishing path

User flow:

1. Import or seed frameworks.
2. Harmonize them into unified controls.
3. Add implementation guidance and testing metadata.
4. Enable frameworks for AWS accounts/profiles.
5. Run evidence collection.
6. Review results in the UI.
7. Publish evidence and assessment reports to Confluence.
8. Run recurring monthly, quarterly, yearly assessments.

## 9. Practical recommendation for the next build step

The best next implementation step is not to start by copying UI files.

The best next step is:

1. Extend `my_grc` with unified control and mapping tables.
2. Build an importer for `grc-master.db`.
3. Then port the `grc-master` UI to use the new backend.

That order avoids locking the merged product into the old flat schema and gives a clean path to the AWS evidence and assessment capabilities you actually want.
