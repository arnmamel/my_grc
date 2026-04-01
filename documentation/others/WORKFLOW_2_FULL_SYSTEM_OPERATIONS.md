# Workflow 2: Full System Operations

This guide explains how to operate `my_grc` as an ongoing enterprise workflow once the first pilot is working.

## Operating Model

Use the platform in four layers:

1. govern the control model
2. scope it to organizations, products, and flavors
3. connect it to AWS, scripts, and Confluence when needed
4. run evidence, assessments, reviews, and reporting repeatedly

## A. Workspace Navigation Model

Use the workspace shell for everyday operation:

- `Workspace Home`: overall state and top priorities
- `Assistant Center`: guided next steps and AI-related review entry points
- `Asset Catalog`: create, inspect, update, and delete almost any record
- `Artifact Explorer`: evidence, assessments, questionnaires, imports, and lifecycle outputs
- `Operations Center`: readiness checks and backlog
- `Governance Center`: maturity, lifecycle, and queue posture
- `Settings & Integrations`: runtime preferences and connector health
- `Workspace Assessment`: UI/UX and platform maturity summary

The same unified navigation shell also includes specialist flows:

- `Wizards`
- `Portfolio`
- `AWS Profiles`
- `Control Framework Studio`
- `Review Queue`
- `Operations`
- `Security & Lifecycle`
- `Questionnaires`
- `Maturity Studio`

## B. Framework Management

### Built-in templates

Seed or reseed the framework catalog:

```bash
aws-local-audit framework seed
aws-local-audit framework list
aws-local-audit framework list-templates
```

### External sources

Use external sources when you want a framework from a spreadsheet or CSV:

```bash
aws-local-audit importer preview-framework ./sources/csa_ccm.xlsx --sheet-name CCM
aws-local-audit importer load-framework ./sources/csa_ccm.xlsx \
  --framework-code CSA_CCM \
  --framework-name "Cloud Controls Matrix" \
  --framework-version 4.0 \
  --sheet-name CCM \
  --mapping-mode create_baseline \
  --auto-approve
aws-local-audit importer traceability --framework CSA_CCM
```

Use the workspace:

- `Control Framework Studio`
- `Asset Catalog` -> `Framework Import Batches`
- `Asset Catalog` -> `Imported Requirements`

### Adding more frameworks

For internal frameworks or policies:

- use `Standards`
- or `Asset Catalog` -> `Frameworks`

Track:

- authority document
- version
- category
- source
- lifecycle status

## C. Control Framework Studio, Unified Controls, And Mappings

This is the backbone of the system.

Create unified controls:

```bash
aws-local-audit ucf create UCF-LOG-01 \
  --name "Centralized audit logging" \
  --domain Logging \
  --family Detection

aws-local-audit ucf list
```

Map source controls into them:

```bash
aws-local-audit ucf map \
  --unified-control UCF_LOG_01 \
  --framework ISO27001_2022 \
  --control-id A.8.15
```

Where to operate this:

- `Control Framework Studio` for the normal day-to-day mapping and wording workflow
- `Asset Catalog` -> `Unified Controls` when you want inventory-style CRUD across the whole control library
- `Asset Catalog` -> `Unified Control Mappings` when you want inventory-style CRUD across all stored mappings

### AI assistance here

Current AI help is governed, not autonomous:

- mapping suggestions from imported CSV or spreadsheet content
- review and promote suggestions only after human supervision

Find it in:

- `Assistant Center`
- `Control Framework Studio`
- `Review Queue`
- `Asset Catalog` -> `AI Suggestions`

CLI review flow:

```bash
aws-local-audit review queue
aws-local-audit review ai-suggestion 42 --action promote --actor auditor@example.com --rationale "Top match is correct"
```

## D. Products, Flavors, And Implementations

Every control can be implemented differently depending on:

- product
- flavor
- account
- region
- deployment model

Manage these in:

- `Portfolio`
- `Maturity Studio`
- `Asset Catalog`

Important asset types:

- `Organizations`
- `Products`
- `Product Flavors`
- `Framework Bindings`
- `Control Implementations`
- `Product Control Profiles`

What to capture:

- implementation narrative
- inheritance
- applicability
- maturity
- assessment mode
- autonomy recommendation

## E. AWS Configuration Profiles

Register all AWS CLI SSO profiles the platform may need:

```bash
aws-local-audit aws-profile upsert prod-audit ...
aws-local-audit aws-profile upsert sec-audit ...
aws-local-audit aws-profile list
aws-local-audit aws-profile export-config
```

For live validation:

```bash
aws sso login --profile prod-audit
aws-local-audit aws-profile validate prod-audit
```

Use:

- one profile per account/role combination when clarity matters
- validation before live evidence work
- the login plan and readiness report before every live collection cycle

## F. Ways To Test Controls

Controls can be exercised in different ways:

- `manual`: upload evidence or use external narratives
- `assisted`: the platform guides login plans and evidence collection
- `autonomous`: mature controls with governed evidence plans and enough automation
- `external script`: reusable Python modules bound to evidence plans or control scope

### Native evidence collection

```bash
aws-local-audit evidence login-plan --binding ...
aws-local-audit evidence readiness-report --binding ...
aws-local-audit evidence collect --binding ... --product ...
```

### Manual evidence

```bash
aws-local-audit evidence upload-manual --binding ... --control-id A.5.1 --summary "Reviewed and approved" --status pass
aws-local-audit evidence review 15 --lifecycle-status approved --actor auditor@example.com --rationale "Evidence is sufficient"
```

### External assessment scripts

Register:

```bash
aws-local-audit script register \
  --module-code IDENTITY_ACCESS \
  --name "Identity Center Access Review" \
  --entrypoint-ref scripts/identity_center_access.py \
  --entrypoint-type python_file \
  --interpreter python3 \
  --context-argument-name="--context-file"
```

Bind:

```bash
aws-local-audit script bind \
  --module-code IDENTITY_ACCESS \
  --name "Portal identity access" \
  --framework-binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 \
  --framework ISO27001_2022 \
  --control-id A.5.15 \
  --evidence-plan BINDING_ISO27001_A_5_15
```

Inspect:

```bash
aws-local-audit script list
aws-local-audit script bindings
```

## G. Assessments

### Run one framework

```bash
aws-local-audit assessment run --framework ISO27001_2022
```

### Run one scoped binding/product/flavor

```bash
aws-local-audit assessment run \
  --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 \
  --product CUSTOMER_PORTAL \
  --flavor EU_MULTI_TENANT
```

### Run multiple frameworks in one cycle

```bash
aws-local-audit assessment run \
  --framework ISO27001_2022 \
  --framework ISO27017 \
  --framework CSA_CCM
```

### Find past runs

CLI:

```bash
aws-local-audit assessment list
aws-local-audit assessment list --framework ISO27001_2022
aws-local-audit assessment list --status completed
```

Workspace:

- `Artifact Explorer` -> `Assessment Runs`
- `Asset Catalog` -> `Assessment Runs`
- `Operations`

### Review assessment outcomes

CLI:

```bash
aws-local-audit review assessment 7 --status approved --actor auditor@example.com --rationale "Evidence and scoring were validated"
```

Workspace:

- `Review Queue`
- `Operations Center`
- `Governance Center`

## H. Recurring Assessments

Create schedules:

```bash
aws-local-audit schedule create \
  --name "Quarterly cloud controls" \
  --cadence quarterly \
  --framework ISO27001_2022 \
  --framework ISO27017 \
  --framework CSA_CCM

aws-local-audit schedule create \
  --name "Portal ISO evidence run" \
  --cadence monthly \
  --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 \
  --product CUSTOMER_PORTAL \
  --flavor EU_MULTI_TENANT \
  --execution-mode assisted
```

Inspect and run:

```bash
aws-local-audit schedule list
aws-local-audit schedule run-due
aws-local-audit schedule run-one 3
```

Use the workspace:

- `Operations`
- `Operations Center`
- `Asset Catalog` -> `Assessment Schedules`

## I. Questionnaires

Questionnaires are answered from implementation information, not evidence.

Use:

- `Questionnaires`
- `Asset Catalog` -> `Customer Questionnaires`

Best practice:

- keep implementations current
- keep product control profiles current
- use questionnaire reviews to tighten assurance language

## J. Confluence Publishing

Register and test connections:

```bash
aws-local-audit confluence upsert --name MAIN --base-url https://confluence.example.com --space-key SEC
aws-local-audit confluence list
aws-local-audit confluence test --name MAIN
```

Operate in:

- `Security & Lifecycle`
- `Settings & Integrations`

Use healthy connections before:

- evidence publishing
- assessment report publication
- attachment or report workflows

## K. Logs, Audit, And Troubleshooting

Primary runtime logs:

- `logs/my_grc.log`
- `logs/my_grc-audit.log`

Use these to answer:

- who ran what
- what workspace area was opened
- what lifecycle transition occurred
- when CRUD actions happened
- whether DB session failures occurred

Also inspect:

```bash
aws-local-audit lifecycle recent
aws-local-audit review queue
aws-local-audit maturity phase1-score
aws-local-audit maturity enterprise-score
```

## L. Recommended Daily Routine

1. Open `Workspace Home`
2. Review `Assistant Center`
3. Check `Operations Center`
4. Work the `Review Queue`
5. Run live AWS work only after readiness is healthy
6. Inspect `Artifact Explorer` for produced evidence and assessments
7. Review `Governance Center` for maturity and backlog trends

## M. Recommended Expansion Order

1. Add more AWS profiles
2. Add more products and flavors
3. Add more evidence targets
4. Add more unified control mappings
5. Import more frameworks
6. Bind reusable external assessment scripts
7. Move more controls toward assisted and autonomous maturity
