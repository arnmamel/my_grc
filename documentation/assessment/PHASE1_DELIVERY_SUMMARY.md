# Phase 1 Delivery Summary

## Decision

Phase 1 can now be considered delivered as the foundation and guided-adoption tranche of `my_grc`.

This does not mean the platform is enterprise-complete. It means the backbone, first-run experience, offline-first local operation, and AWS SSO targeting model are now coherent enough to move into Phase 2 operational hardening.

## What is now in place

### Backbone and governance

- authority documents for frameworks
- custom framework shell creation
- manual control authoring for frameworks
- unified controls and governed mappings with approval metadata
- evidence collection plans
- lifecycle event tracking across major entities
- secure secret handling and encrypted evidence payloads

### AWS operating model

- AWS runtime is based on local AWS CLI IAM Identity Center profiles
- AWS CLI profile metadata can be stored locally in the app for host or Ubuntu WSL usage
- the expected login flow is `aws sso login --profile <profile>`
- the system stores profile names, account IDs, regions, and target metadata, but not AWS session credentials
- product, flavor, and control-aware AWS evidence targets can now be registered
- evidence collection resolves the most specific target set for a control when AWS is available
- collection planning can now show which profiles, accounts, and regions are needed before a run starts

### Offline-first operation

- the workspace can run in offline-first mode
- local metadata work remains available without AWS connectivity
- frameworks, controls, mappings, questionnaires, assessments, and reporting can still be managed locally
- assessments reuse existing local evidence while offline
- evidence collection requests are deferred cleanly when offline mode is enabled

### Guided user experience

- the workspace now defaults to the `Wizards` section during onboarding
- the workspace now includes an `AWS Profiles` section
- first-run, framework, control, AWS target, questionnaire, and assessment wizards exist
- the operations page shows runtime mode and target context
- the workspace now avoids `st.rerun()` inside transactional flows, reducing commit-cohesion risk

### Runtime and deployment posture

- Ubuntu WSL plus a Python virtual environment is now the recommended runtime path
- WSL installation and run commands are documented
- a future-ready distroless Docker artifact is included for offline-first and non-interactive use
- container execution is intentionally secondary to host-driven AWS SSO login

## Phase 1 maturity after consolidation

| Area | Maturity | Notes |
| --- | --- | --- |
| Framework management | `3.5/5` | Strong starter catalog and custom framework authoring exist. |
| Unified controls and mappings | `3/5` | Governed mappings exist, but review workflow is still lightweight. |
| Product and flavor-aware operating model | `3.5/5` | Scope-aware implementations, profiles, questionnaires, and assessments are coherent. |
| AWS SSO operating model | `3.5/5` | Runtime is aligned with `aws sso login`, but guided profile setup is still a Phase 2 item. |
| AWS evidence targeting | `3/5` | Product/flavor/control-aware targets now exist, but richer inheritance and asset discovery are still ahead. |
| Evidence collection foundation | `3/5` | Target-aware aggregation and offline deferral exist, but plan-driven sufficiency is still Phase 2. |
| Offline-first local GRC operations | `3.5/5` | Local administration and reporting are coherent without AWS. |
| Security foundation | `3.5/5` | Evidence encryption and secret handling are in place. |
| Lifecycle traceability | `3/5` | Auditability exists, though transition policies remain incomplete. |
| Workspace usability | `3.5/5` | Guided onboarding and core workflows are usable. |

## Residual risks accepted at Phase 1 close

- no migration framework yet
- no RBAC or separation of duties yet
- lifecycle transitions are recorded but not policy-enforced
- evidence plans are modeled but not yet the full execution source of truth
- Confluence publishing is still page-centric and not attachment-complete
- AWS profile setup assistance is still limited to operating guidance rather than full automation
- no background job runner yet

## Recommended Phase 2 starting line

Phase 2 should start from these concrete priorities:

1. migrations and schema versioning
2. AWS profile assistant and validation workflow
3. plan-driven evidence execution with freshness and sufficiency logic
4. Confluence attachment targets and health checks
5. review queue and evidence explorer

That sequencing preserves the foundations delivered in Phase 1 while moving the system toward enterprise operational maturity.
