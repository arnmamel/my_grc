# Merged Data Model

This document describes the first merged backend model implemented in `my_grc` to combine:

- the execution and assessment engine from `my_grc`
- the workspace, mapping, and analyst-authored metadata concepts from `grc-master`

## Design goals

The merged model is designed to support:

- framework catalogs and imported standards
- unified controls across multiple standards
- organization-specific implementation records
- AWS profile and region bindings per organization
- automated and manual evidence
- assessment run snapshots
- external work item links
- AI-generated drafting history

## Entity overview

### Existing execution entities

- `Framework`
  - a compliance framework or standard catalog
- `Control`
  - a framework-specific requirement/control
- `EvidenceItem`
  - evidence collected for a framework control
- `AssessmentRun`
  - a single assessment execution
- `AssessmentSchedule`
  - recurring assessment cadence

### New merged entities

- `ControlMetadata`
  - rich metadata from YAML templates
  - includes control summary, AWS guidance, check type, boto3 services, and the boto3 check description
- `Organization`
  - the tenant or business entity operating the controls
- `OrganizationFrameworkBinding`
  - an organization’s binding of a framework to an AWS profile/region/account scope
- `UnifiedControl`
  - a canonical control that one or more framework controls can map to
- `UnifiedControlMapping`
  - the crosswalk from a framework control to a unified control, with rationale and confidence
- `ControlImplementation`
  - organization-specific implementation detail, migrated conceptually from `grc-master`
  - includes AWS implementation notes, on-prem notes, lifecycle, owner, evidence links, test plan, blockers, and tickets
- `AssessmentRunItem`
  - per-control snapshot inside an assessment run
- `ExternalArtifactLink`
  - generic link model for Jira, ServiceNow, Confluence, design docs, and external evidence URLs
- `AISuggestion`
  - stored AI output for implementation suggestions, objectives, or test plans

## Relationship summary

- `Framework 1 -> many Control`
- `Control 1 -> 1 ControlMetadata`
- `Organization 1 -> many OrganizationFrameworkBinding`
- `Framework 1 -> many OrganizationFrameworkBinding`
- `UnifiedControl 1 -> many UnifiedControlMapping`
- `Control 1 -> many UnifiedControlMapping`
- `Organization 1 -> many ControlImplementation`
- `UnifiedControl 1 -> many ControlImplementation`
- `Control 1 -> many ControlImplementation`
- `AssessmentRun 1 -> many AssessmentRunItem`
- `EvidenceItem 1 -> many AssessmentRunItem`
- `ControlImplementation 1 -> many ExternalArtifactLink`
- `Organization 1 -> many AISuggestion`

## Why this model was chosen

The old `grc-master` schema stored internal controls and external standards in the same flat table. That was flexible for prototyping, but it is not expressive enough for:

- recurring AWS assessments
- evidence history
- unified control inheritance
- organization-scoped implementations
- automation and manual work living in the same system

The new model keeps the current execution engine working while adding the missing entities around it.

## Current integration state

Implemented now:

- SQLAlchemy model definitions
- framework seeding now persists `ControlMetadata`
- assessment runs now persist `AssessmentRunItem` records
- CLI commands now support:
  - organizations
  - framework bindings
  - unified controls
  - framework-to-unified mappings
  - implementation records

Not yet implemented:

- migration/import from `grc-master.db`
- UI port from `grc-master`
- evidence collection directly from organization framework bindings
- automated use of unified control mappings during assessments
- persistence of Gemini outputs into `AISuggestion`

## Next implementation steps

1. Build importer from `grc-master.db` into:
   - `Organization`
   - `UnifiedControl`
   - `UnifiedControlMapping`
   - `ControlImplementation`
   - `ExternalArtifactLink`
2. Add service methods to run evidence collection through `OrganizationFrameworkBinding`
3. Port the Streamlit workspace to the new service layer
4. Expand collector coverage so the richer framework catalog becomes executable
