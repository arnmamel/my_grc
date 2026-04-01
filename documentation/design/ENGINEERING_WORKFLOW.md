# Engineering Workflow

## Default delivery path

Every change should go through:

1. build
2. automated tests
3. migration validation
4. deployment packaging
5. smoke verification

## Branching and review

Recommended branching model:

- short-lived feature branches
- one topic per branch
- no direct changes to the main deployment branch

Pull request expectations:

- clear purpose and scope
- migration notes if the schema changes
- rollout notes if feature flags or dark launches are involved
- evidence of tests run
- reviewer callout for risky areas

Approval guidance:

- domain changes: governance or platform owner review
- security-sensitive changes: security-aware reviewer required
- migration changes: platform or database-aware reviewer required
- integration changes: connector owner review required

## Coding standards

- prefer boring tech
- prefer explicit data flow
- validate at the boundaries
- fail clearly and early
- avoid hidden magic and implicit mutation
- prioritize readability over cleverness

## Documentation expectations

When a change affects behavior, update:

- operator docs
- architecture or operating model docs
- deployment docs if runtime changed
- maturity assessment if the change affects enterprise readiness

## Secrets and configuration

- do not store secrets in source control
- avoid plain environment variables when a secure store is available
- use keyring or secret files for local or headless operation
- document new configuration keys in `README.md` and `.env.example`

## Migrations

- schema changes require Alembic revisions
- additive migrations are preferred
- destructive changes need explicit rollout planning

## Background jobs

Current status:

- interactive and schedule-driven execution exists
- durable workers are still a planned enterprise gap

Rule:

- do not add hidden long-running work to the UI thread
- new background behavior should come with locking, retry, and observability design
