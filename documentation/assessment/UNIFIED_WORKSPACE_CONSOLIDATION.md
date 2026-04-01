# Unified Workspace Consolidation

## What Changed

This iteration removed the split between `Unified Workspace` and `Legacy Pages` as an operator choice. The application now has one navigation shell, and all previously specialist flows remain reachable from that same entry point.

Integrated pages now reachable from the single workspace shell:

- `Workspace Home`
- `Overview`
- `Assistant Center`
- `Asset Catalog`
- `Artifact Explorer`
- `Operations Center`
- `Governance Center`
- `Settings & Integrations`
- `Help Center`
- `Wizards`
- `Standards`
- `Portfolio`
- `AWS Profiles`
- `Control Framework Studio`
- `Review Queue`
- `Operations`
- `Security & Lifecycle`
- `Questionnaires`
- `Maturity Studio`
- `Workspace Assessment`

## Workspace Home Improvements

`Workspace Home` is now actionable, not just informational.

It now provides:

- assets and artifacts counted separately
- drill-down views for assets, artifacts, review items, Phase 1 maturity, and enterprise maturity
- inline record inspection and quick edit/create/delete for inventory items
- a direct bridge back into `Asset Catalog` with the right asset type already focused
- a one-click `Exercise SCF Pivot Backbone` action

Historical page aliases such as `Unified Controls`, `Import Studio`, and `Mapping Lab` now resolve into `Control Framework Studio`. They are kept only as compatibility aliases, not as separate operator destinations.

## Phase 1 Backbone Exercise

The new uplift workflow creates a real local path that improves Phase 1 maturity without relying on fake demo abstractions.

It ensures:

- pivot framework code set to `SCF_2025_3_1`
- seeded framework catalog including `ISO27001_2022`
- exercised Annex A control path: `ISO27001_2022` `A.5.1`
- SCF-pivot aligned unified control baseline entry
- approved unified-control mapping
- one local organization
- one local product
- one local product flavor
- one control implementation
- one product control profile
- one governed evidence plan

## Maturity Impact

This pass specifically addresses the previously open foundation gaps around:

- exercising the SCF-pivot unified control backbone
- bringing ISO 27001:2022 Annex A into a real mapped path
- exercising organization and product scope in a local workspace
- adding implementation records
- adding product control profiles
- making the single workspace usable as the normal operating point

## Remaining Honest Gaps

This consolidation improves coherence and usability materially, but it does not close every enterprise gap.

Important remaining areas:

- broader SCF mapping coverage beyond the first exercised path
- more product/flavor scoped implementations across more controls
- deeper end-to-end runtime validation for Streamlit UI flows
- background job durability and notification workflows
- broader enterprise APIs and connector patterns
- project-wide cleanup of `datetime.utcnow()` deprecation warnings
