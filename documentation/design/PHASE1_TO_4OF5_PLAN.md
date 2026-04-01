# Phase 1 To 4/5 Plan

## Objective

Phase 1 is delivered as a coherent foundation, but it is still mostly in the `3.0` to `3.5` maturity band.

The goal of this plan is to raise the delivered Phase 1 feature set to a credible `4/5` by focusing on:

- operational readiness
- governance depth
- setup repeatability
- measurable gap closure

## What was added in this pass

This pass improves the Phase 1 foundation with:

- a formal Phase 1 maturity and readiness assessment service
- CLI scoring through `aws-local-audit maturity phase1-score`
- AWS CLI profile config export through `aws-local-audit aws-profile export-config`
- collection-plan visibility that shows required profiles, accounts, regions, and whether the profiles are registered in the app
- overview and operations workspace visibility for the remaining blockers to reach `4/5`

These changes do not finish the 4/5 journey, but they make it measurable and easier to execute.

## Updated maturity direction

| Area | Previous | Current direction | 4/5 means |
| --- | --- | --- | --- |
| Framework management | `3.5/5` | stable | curated catalog, authority lineage, and governed updates are reliable |
| Unified controls and mappings | `3/5` | rising | approved mappings, review governance, and better coverage exist |
| Product and flavor scope | `3.5/5` | stable | scoped implementations and assessments are dependable |
| AWS SSO operations | `3.5/5` | rising | profile metadata, config export, login planning, and run readiness are dependable |
| AWS evidence targeting | `3/5` | rising | most important scoped controls have explicit target coverage |
| Evidence collection foundation | `3/5` | rising | plans, targets, and collected evidence align on the main control paths |
| Offline-first operations | `3.5/5` | stable | local workflows remain fully useful without AWS |
| Security foundation | `3.5/5` | stable | secure defaults are consistently used |
| Lifecycle traceability | `3/5` | rising | traceability plus transition governance exist |
| Workspace usability | `3.5/5` | rising | setup, inspection, and readiness checks are smooth |

## Path to 4/5

### Tranche A: Governed operational readiness

Target outcome:

- get AWS SSO operations, evidence targeting, and workspace usability close to `4/5`

Work:

1. finish profile setup assistance
   - guide users from stored metadata to ready-to-paste `~/.aws/config`
   - add profile validation and health checks
   - record last validation time and diagnostics

2. increase target coverage
   - register AWS evidence targets for the highest-priority controls per product and flavor
   - surface missing target coverage in the workspace and CLI
   - add target completeness reporting per binding

3. operational readiness checks
   - warn when bindings, profiles, targets, or plans are incomplete before collection
   - flag missing profile metadata or missing evidence plans as first-class findings

### Tranche B: Governance hardening

Target outcome:

- get unified controls, mappings, lifecycle traceability, and framework governance close to `4/5`

Work:

1. lifecycle transition policy
   - enforce allowed transitions for framework lifecycle, evidence plans, AWS targets, and assessment review
   - require reviewer metadata on approval transitions

2. mapping governance uplift
   - add review queues for proposed mappings
   - increase approved mapping coverage
   - track stale or low-confidence mappings

3. evidence-plan governance uplift
   - measure plan coverage against seeded controls
   - promote priority plans from `draft` to governed active states

### Tranche C: Repeatability and quality

Target outcome:

- make the current Phase 1 foundation dependable enough for a production pilot

Work:

1. migrations
   - replace implicit schema evolution with Alembic migrations

2. validation
   - validate framework YAML
   - validate imported questionnaire CSV structure
   - validate AWS profile metadata and target definitions

3. tests
   - add service tests for maturity scoring
   - add tests for login-plan generation
   - add tests for offline-mode evidence deferral

## Concrete scoring gates for 4/5

To honestly call the delivered Phase 1 feature set `4/5`, these conditions should hold:

1. framework management
   - authority document coverage is complete
   - seeded frameworks are reviewed and stable

2. unified controls and mappings
   - at least 70 percent of important mappings are approved
   - low-confidence mappings are reviewed or rejected

3. AWS SSO operations
   - active bindings have registered AWS profile metadata
   - operators can export config and inspect login plans before runs
   - profile validation exists

4. evidence targeting and evidence foundation
   - priority applicable controls have evidence plans
   - priority AWS-backed controls have explicit targets
   - at least one real collection cycle has been exercised per major product path

5. lifecycle and workspace
   - main objects use governed lifecycle progression
   - overview shows readiness gaps clearly
   - setup and run workflows are smooth without hidden manual steps

## Biggest remaining blockers

- no migration framework yet
- lifecycle transitions are still recorded more than enforced
- approved mapping coverage still depends on data maturity
- evidence-plan coverage is still partial
- AWS profile validation is still informational, not interactive
- no background jobs yet

## Recommended next build slice

The highest-value next slice to move toward `4/5` is:

1. add profile validation and readiness checks
2. add target coverage reporting per binding/product/flavor
3. enforce lifecycle transitions for evidence plans and AWS targets
4. add Alembic migrations

That set raises real maturity instead of just adding more pages or entities.
