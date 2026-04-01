# my_grc

`my_grc` is an offline-first Python GRC workspace for managing frameworks, unified controls, mappings, scoped implementations, evidence, assessments, questionnaires, and reporting.

The operating model is:

- use the Secure Controls Framework as the pivot unified-control baseline
- map regulations and standards such as ISO/IEC 27001:2022 into that baseline
- describe how each control is implemented per organization and product
- collect evidence with local AWS CLI SSO profiles only when a live run needs it
- keep the workspace useful even without AWS connectivity
- protect the workspace itself with local authenticated access, while keeping the door open for later SSO or OIDC federation

## What the app covers

- framework and authority-document management
- SCF-pivot unified controls and regulated requirement mappings
- external framework imports from CSV and Excel with row-level traceability
- governed AI knowledge packs with versioned tasks, references, eval cases, and reviewable drafts
- product and AWS account/region/profile scoping
- implementation wording and product control profiles
- encrypted evidence storage and governed assessments
- questionnaires answered from implementation narratives
- Confluence connection management and publishing support
- operator guidance, review queues, maturity scoring, and release notes
- local workspace authentication, observability summaries, and backup/restore mechanics
- centralized `About` center with current readiness, release history, assessment history, and practitioner feedback mailbox
- isolated QA, regression, smoke, and security testing

## Project layout

- `src/`: application code
- `workspace/`: Streamlit workspace
- `scripts/`: run, validation, bootstrap, and container helper scripts
- `documentation/design/`: architecture, roadmap, and design decisions
- `documentation/assessment/`: maturity reviews, assessments, and gap analyses
- `documentation/others/`: user workflows, release notes, setup notes, and source bundles
- `testing/qa/`: isolated QA harness
- `testing/tests/`: unit and regression tests

## Built-in framework baseline

Starter templates are seeded for:

- `SCF_2025_3_1`
- `ISO27001_2022`
- `ISO27017`
- `ISO27018`
- `CSA_CCM`
- `GSMA_SAS_SM_FS_18`

The SCF shell is the intended pivot baseline. Import the official SCF workbook to land the authoritative content and source traceability in the database.

## Quick start on Ubuntu WSL

The easiest path is:

```bash
cd /mnt/c/Users/<your_local_user>/OneDrive/Aplicaciones/Projects/my_grc
./scripts/ubuntu_bootstrap.sh
./scripts/run_workspace.sh
```

If you prefer the manual path:

```bash
cd /mnt/c/Users/<your_local_user>/OneDrive/Aplicaciones/Projects/my_grc
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e .
cp .env.example .env
aws-local-audit init-db
aws-local-audit security bootstrap
aws-local-audit framework seed
./scripts/run_workspace.sh
```

Detailed environment notes are in [documentation/others/WSL_UBUNTU_SETUP.md](documentation/others/WSL_UBUNTU_SETUP.md).

## Fast operator workflow

1. Open the workspace. After onboarding, it lands in `Control Framework Studio` by default.
2. Use `Control Framework Studio` like a workbook:
   - `SCF Register`: maintain the shared SCF baseline wording and guidance
   - `Scope Implementation`: record SoA, rationale, implementation wording, owners, and maturity for one organization and product
   - `Testing & Evidence`: record testing method, evidence strategy, review cadence, and AWS targets
   - `Requirement Mappings`: manage traceability from SCF into ISO and other regulations
   - `Standards & Imports`: maintain framework shells and import Excel or CSV sources
   - `Copilot & Review`: generate governed AI draft packages when a mapped path already exists
3. Use `Portfolio` to define organizations, products, and framework bindings when the workbook guidance tells you something is missing.
4. Use `AWS Profiles` to register local AWS CLI SSO profile metadata.
5. Use `Operations` to validate readiness and run collection or assessments.
6. Use `Artifact Explorer` to review evidence and completed runs.
7. Use `About` to see the current version, release notes, live readiness scoring, and the practitioner feedback mailbox.
8. Use `Help Center` when you want guided practitioner instructions.

## Workspace access and recovery

The workspace now has its own local access gate for offline-first use.

- on the first secure start, create the first workspace user directly in the app
- after that, sign in before using the workspace shell
- use the CLI if you want to bootstrap or rotate credentials outside the UI

Helpful commands:

```bash
aws-local-audit auth status
aws-local-audit auth bootstrap grc.lead --display-name "GRC Lead"
aws-local-audit auth set-password grc.lead
aws-local-audit platform backup-create --label pre-release
aws-local-audit platform backup-list
aws-local-audit platform backup-verify <backup-name>
aws-local-audit platform observability
```

## Control mapping workflow

The main control-management surface is now `Control Framework Studio`.

From that page you can:

- work from an SCF-first workbook with separate tabs for baseline controls, scoped implementation, testing, mappings, standards, and copilot help
- compare a few organization/product scopes directly from the workbook when you need a fast gap view
- review imported requirement rows and traceability
- create or edit unified control wording
- approve or adjust framework-to-unified-control mappings
- import Excel or CSV framework sources into existing or new frameworks
- write SoA, implementation wording, and testing plans for a scoped organization/product
- maintain the product control profile for applicability, implementation status, assessment mode, and evidence strategy
- export the full workbook or individual sheets for offline editing, then import them back
- open governed copilot assistance when a mapped requirement already exists

Historical page names such as `Unified Controls`, `Import Studio`, and `Mapping Lab` are treated as compatibility aliases only. The normal operator experience is the single `Control Framework Studio` page.

If you want a first working local path immediately, use the `Bootstrap SCF pivot path` action there or the `Exercise SCF Pivot Backbone` action from `Workspace Home`.

## AWS evidence workflow

`my_grc` does not store AWS session credentials.

It stores only local profile metadata and target scoping. When evidence collection is required:

1. register the needed AWS CLI SSO profiles in the app
2. inspect the login plan
3. run `aws sso login --profile <profile>` for each required profile
4. return to the app and run the evidence or assessment workflow

Typical commands:

```bash
aws-local-audit aws-profile list
aws-local-audit aws-profile validate my-sso-profile
aws-local-audit evidence login-plan --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 --product CUSTOMER_PORTAL
aws-local-audit evidence readiness-report --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 --product CUSTOMER_PORTAL
```

## Helpful commands

Launch the workspace:

```bash
./scripts/run_workspace.sh
```

Run focused validation:

```bash
./scripts/ubuntu_validate.sh
```

Run the regression suite and isolated QA harness:

```bash
./scripts/run_e2e_tests.sh
```

Run the full local release gates:

```bash
./scripts/run_release_gates.sh
```

Run the QA harness directly:

```bash
bash testing/qa/run_wsl.sh
```

Import the Secure Controls Framework workbook:

```bash
aws-local-audit importer load-scf /path/to/secure-controls-framework-scf-2025-3-1.xlsx
```

Seed and inspect governed AI knowledge packs:

```bash
aws-local-audit copilot seed
aws-local-audit copilot list
aws-local-audit copilot tasks --pack SCF_ISO27001_ANNEX_A
```

Generate a governed draft for SCF-pivot mapping work:

```bash
aws-local-audit copilot draft \
  --pack SCF_ISO27001_ANNEX_A \
  --task mapping_rationale \
  --framework ISO27001_2022 \
  --control-id A.5.1 \
  --unified-control SCF_POL_001
```

Inspect maturity and health:

```bash
aws-local-audit maturity phase1-score
aws-local-audit maturity enterprise-score
aws-local-audit platform health
```

Open the unified About center in the workspace when you want:

- the current version and release notes
- the live 5-dimension delivery-readiness score
- the historical maturity snapshots collected so far
- a mailbox to send improvement suggestions from day-to-day GRC work

## Practitioner guides

Start here:

- [documentation/others/WORKFLOW_1_FIRST_FRAMEWORK_PILOT.md](documentation/others/WORKFLOW_1_FIRST_FRAMEWORK_PILOT.md)
- [documentation/others/WORKFLOW_2_FULL_SYSTEM_OPERATIONS.md](documentation/others/WORKFLOW_2_FULL_SYSTEM_OPERATIONS.md)
- [documentation/others/WORKSPACE_ACCESS_AND_RECOVERY.md](documentation/others/WORKSPACE_ACCESS_AND_RECOVERY.md)
- [documentation/others/RELEASE_IMPROVEMENTS_AND_ISSUES.md](documentation/others/RELEASE_IMPROVEMENTS_AND_ISSUES.md)
- [testing/qa/README.md](testing/qa/README.md)
- [documentation/assessment/PROJECT_HYGIENE_ITERATIONS.md](documentation/assessment/PROJECT_HYGIENE_ITERATIONS.md)
- [documentation/assessment/CURRENT_DELIVERY_READINESS_ASSESSMENT.md](documentation/assessment/CURRENT_DELIVERY_READINESS_ASSESSMENT.md)
- [documentation/assessment/MATURITY_HISTORY.yaml](documentation/assessment/MATURITY_HISTORY.yaml)

Deeper references:

- [documentation/design/SCF_PIVOT_AND_REFERENCE_MODEL.md](documentation/design/SCF_PIVOT_AND_REFERENCE_MODEL.md)
- [documentation/design/AI_KNOWLEDGE_PACK_MODEL.md](documentation/design/AI_KNOWLEDGE_PACK_MODEL.md)
- [documentation/design/ENTERPRISE_GRC_SPECIFICATIONS.md](documentation/design/ENTERPRISE_GRC_SPECIFICATIONS.md)
- [documentation/design/ARCHITECTURE_BOUNDARIES.md](documentation/design/ARCHITECTURE_BOUNDARIES.md)
- [documentation/design/OPERATIONS_EXCELLENCE_BASELINE.md](documentation/design/OPERATIONS_EXCELLENCE_BASELINE.md)
- [documentation/design/ENGINEERING_WORKFLOW.md](documentation/design/ENGINEERING_WORKFLOW.md)
- [documentation/assessment/AI_COPILOT_STATUS_ASSESSMENT.md](documentation/assessment/AI_COPILOT_STATUS_ASSESSMENT.md)

## Tips to become a stronger GRC operator in this workspace

- Start with one real mapped path instead of trying to model every framework at once.
- Keep the unified control wording implementation-focused; keep framework wording traceable, not duplicated.
- Treat organization and product scope as first-class, because implementation and evidence often differ there.
- Use the review queue aggressively; it is the fastest way to close governance gaps.
- Use imported references and guide documents to explain how a control should be implemented, not just what requirement it covers.
- Prefer readiness checks before live evidence collection.
- Keep offline mode enabled when you are doing modeling, mapping, questionnaires, or report preparation without needing AWS.

## GitHub hygiene

The root now keeps runtime-critical files only. Generated or local-only artifacts are ignored, including:

- local virtual environments
- database files
- logs
- QA reports
- generated package metadata
- Streamlit local secrets

Before publishing, review `.env`, `audit_manager.db`, and any local files under `logs/` or `data/`.
