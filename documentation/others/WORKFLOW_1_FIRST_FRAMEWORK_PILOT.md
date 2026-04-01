# Workflow 1: First Framework Pilot

This guide takes a new operator from a fresh environment to a first successful evidence-collection and assessment cycle for one framework.

Recommended pilot framework:

- `ISO27001_2022`

Recommended pilot approach:

- use one organization
- use one product
- use one AWS CLI SSO profile
- enable offline-first operation for modeling
- switch to live AWS only when you are ready to validate evidence collection

## 1. Prepare The Environment

From Ubuntu WSL or a compatible shell inside the project:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
cp .env.example .env
```

Minimum `.env` values for a first pilot:

- `ALA_DATABASE_URL`
- `ALA_LOG_DIR`
- `ALA_LOG_LEVEL`

If you also want Confluence publishing during the pilot, configure:

- `ALA_CONFLUENCE_BASE_URL`
- `ALA_CONFLUENCE_SPACE_KEY`
- `ALA_CONFLUENCE_PARENT_PAGE_ID`
- `ALA_CONFLUENCE_AUTH_MODE`
- `ALA_CONFLUENCE_USERNAME`

## 2. Bootstrap The Application

```bash
aws-local-audit init-db
aws-local-audit security bootstrap
aws-local-audit framework seed
aws-local-audit framework list
```

What this gives you:

- local database and schema
- evidence encryption bootstrap
- seeded framework catalog
- starter evidence plans and templates ready to use

## 3. Register Your Enterprise Scope

Create the first organization:

```bash
aws-local-audit org create "Acme Corp" --code ACME
aws-local-audit org list
```

Add a product and, optionally, a flavor from the workspace:

- open `streamlit run workspace/app.py`
- go to `Portfolio`
- create one product, for example `CUSTOMER_PORTAL`
- create one flavor if needed, for example `EU_MULTI_TENANT`

If you prefer a calmer view, use:

- `Asset Catalog`
- family `portfolio`
- asset type `Products` or `Product Flavors`

## 4. Register The AWS CLI SSO Profile

If you already have a working AWS CLI SSO profile locally:

```bash
aws-local-audit aws-profile upsert my-sso-profile \
  --sso-start-url https://example.awsapps.com/start \
  --sso-region eu-west-1 \
  --sso-account-id 123456789012 \
  --sso-role-name AuditReadOnly \
  --default-region eu-west-1
```

Inspect what the application believes the profile config should be:

```bash
aws-local-audit aws-profile show-config my-sso-profile
aws-local-audit aws-profile export-config
aws-local-audit aws-profile list
```

When you are ready to validate the profile live:

```bash
aws sso login --profile my-sso-profile
aws-local-audit aws-profile validate my-sso-profile
```

Use the workspace if you prefer:

- `AWS Profiles`
- or `Settings & Integrations`

## 5. Enable One Framework

```bash
aws-local-audit framework enable ISO27001_2022 \
  --aws-profile my-sso-profile \
  --aws-region eu-west-1

aws-local-audit framework seed-evidence-plans --framework ISO27001_2022
aws-local-audit framework controls ISO27001_2022
```

This gives you:

- an enabled framework
- starter evidence plans
- visible control IDs for later targeting

## 6. Bind The Framework To The Organization

```bash
aws-local-audit org bind-framework \
  --org ACME \
  --framework ISO27001_2022 \
  --aws-profile my-sso-profile \
  --aws-region eu-west-1

aws-local-audit org bindings --org ACME
```

The binding code returned here is important. You will reuse it for evidence collection and assessments.

## 7. Add AWS Evidence Targets

Choose one pilot control. For example:

- `A.8.15`

Register where that control is implemented:

```bash
aws-local-audit org add-aws-target \
  --org ACME \
  --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 \
  --product CUSTOMER_PORTAL \
  --framework ISO27001_2022 \
  --control-id A_8_15 \
  --name "Portal production account" \
  --aws-profile my-sso-profile \
  --regions eu-west-1 \
  --aws-account-id 123456789012

aws-local-audit org aws-targets --org ACME
```

This is the key step that tells the platform:

- which account holds the control implementation
- which region or regions matter
- which CLI profile should be used
- which product the target belongs to

## 8. Add Control Implementation Information

Use the workspace for this:

- `Portfolio`
- add a control implementation for the product
- describe how the control is implemented
- set product control maturity in `Maturity Studio`

Why this matters:

- assessments and questionnaires become useful even when offline
- the platform can explain how your organization meets a control

## 9. Check Readiness Before Live Collection

Before collecting live AWS evidence, inspect the login plan and readiness:

```bash
aws-local-audit evidence login-plan \
  --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 \
  --product CUSTOMER_PORTAL

aws-local-audit evidence readiness-report \
  --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 \
  --product CUSTOMER_PORTAL
```

Or use:

- `Operations Center`

You are ready when:

- required profiles are registered
- profile validation is passing
- evidence plans exist
- Confluence is healthy if you want publication

## 10. Collect Evidence

If the readiness report indicates a live AWS login is needed:

```bash
aws sso login --profile my-sso-profile
```

Then collect:

```bash
aws-local-audit evidence collect \
  --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 \
  --product CUSTOMER_PORTAL
```

To inspect a stored evidence item:

```bash
aws-local-audit evidence show 15
```

To add manual evidence if a control is not automated enough yet:

```bash
aws-local-audit evidence upload-manual \
  --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 \
  --control-id A.5.1 \
  --summary "Approved policy reviewed" \
  --status pass
```

## 11. Run The First Assessment

```bash
aws-local-audit assessment run \
  --binding ACME_ISO27001_2022_MY_SSO_PROFILE_EU_WEST_1 \
  --product CUSTOMER_PORTAL
```

Then find the runs:

```bash
aws-local-audit assessment list
aws-local-audit assessment list --framework ISO27001_2022
```

In the workspace you can also find them in:

- `Artifact Explorer` -> `Assessment Runs`
- `Asset Catalog` -> `Assessment Runs`
- `Operations`

## 12. Review What Happened

Use these places after the pilot run:

- `Operations Center`
- `Governance Center`
- `Review Queue`
- `aws-local-audit review queue`
- `aws-local-audit lifecycle recent`

Use the log files too:

- `logs/my_grc.log`
- `logs/my_grc-audit.log`

## 13. Success Criteria For The Pilot

You can consider the pilot successful when:

- the framework is enabled and bound
- at least one product exists
- at least one AWS profile validates successfully
- at least one AWS target exists
- evidence was collected or uploaded manually
- one assessment run exists
- you can find that run and its related evidence afterward

## 14. Best Next Step After The Pilot

After the first successful pilot:

1. add more products or flavors
2. register more AWS targets
3. mature manual controls into assisted or autonomous collection
4. bring in more frameworks and mappings
5. add Confluence publishing and recurring schedules
