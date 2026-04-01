# Access Governance Model

## Purpose

This model introduces the first enterprise-grade RBAC foundation for `my_grc` so the platform can evolve toward real separation of duties, approval segregation, and future SSO integration.

## Core entities

- `IdentityPrincipal`
  - A user, service account, or group known to the platform.
  - Can be local today and later synchronized from SAML, OIDC, or SCIM.
- `AccessRole`
  - A reusable role definition with explicit permissions.
  - Roles declare whether assignment approval is required.
- `RoleAssignment`
  - A scoped grant of a role to a principal.
  - Scope can target organization, business unit, product, or framework binding.

## Default roles

- `org_admin`
  - Broad administration of frameworks, mappings, portfolio data, evidence, assessments, and RBAC.
  - Requires approval.
- `bu_owner`
  - Risk, finding, and remediation ownership at business-unit scope.
- `control_owner`
  - Responsible for implementations and evidence submission at product scope.
- `auditor`
  - Read-only assurance oversight.
  - Requires approval.
- `approval_manager`
  - Approves mappings, evidence, questionnaires, and assessments.
  - Requires approval.
- `evidence_contributor`
  - Supplies manual evidence and supporting artifacts.
- `read_only`
  - General read-only visibility.

## Separation of duties

The current conflict rules intentionally flag the most dangerous combinations first:

- `org_admin` and `auditor`
- `control_owner` and `auditor`
- `evidence_contributor` and `approval_manager`

These rules are surfaced in:

- the review queue
- health checks
- CLI conflict reporting

## Current maturity

What exists now:

- a persisted role and assignment model
- default role seeding
- scoped permission evaluation
- pending-approval tracking for privileged roles
- segregation-of-duties conflict detection

What still comes later:

- user authentication and session identity
- SAML or OIDC login
- SCIM provisioning
- UI-level enforcement of permissions on every action
- approval workflow policies tied to human identities and notifications
