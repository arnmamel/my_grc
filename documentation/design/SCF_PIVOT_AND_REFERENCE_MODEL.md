# SCF Pivot And Reference Model

## Why SCF is the pivot

The Secure Controls Framework is a strong pivot baseline for `my_grc` because one SCF control can already point to many authoritative sources. In practice that gives us:

- one implementation-oriented control baseline
- one place to anchor evidence plans, implementation narratives, and assessment logic
- many traceable mappings back to frameworks, regulations, and guides

Inside `my_grc`, the SCF workbook is imported as framework `SCF_2025_3_1`. During import:

1. SCF controls become framework controls.
2. The same rows can create or extend the unified-control baseline.
3. The framework is marked as the pivot baseline through system setting `control_mapping.pivot_framework_code`.
4. Authoritative-source columns are converted into explicit `ReferenceDocument` records and linked both to imported source requirements and to the mapped unified controls.

## Normalized reference model

The reference layer is designed so future implementation guides are first-class objects instead of free-text notes:

- `ReferenceDocument`
  - a reusable catalog item for a framework, guide, standard, or regulatory source
- `ImportedRequirementReference`
  - a traceable link from one imported requirement row to one external reference
- `UnifiedControlReference`
  - a reusable link from a unified control to an external reference or guide

This means a unified control can now carry:

- source requirement traceability
- implementation guidance references
- assessment guidance references
- assurance or evidence guidance references

## How SCF import enrichment works

The SCF import path uses a dedicated preset:

- worksheet: `SCF 2025.3.1`
- control ID: `SCF #`
- control title: `SCF Control`
- description: `Secure Controls Framework (SCF) Control Description`
- domain: `SCF Domain`

It also harvests high-value SCF metadata:

- `Conformity Validation Cadence`
- `Evidence Request List (ERL) #`
- `SCF Control Question`
- `Relative Control Weighting`
- `Possible Solutions & Considerations ...`

That enrichment is pushed into control metadata and unified-control guidance so the imported SCF row is useful for implementation and assessment work, not just traceability.

## Guide references

The new reference model is meant to grow beyond standards into practical guides such as:

- NIST SP 800-53 / 800-53A / 800-37 / 800-137
- NIST CSF 2.0 references and implementation profiles
- CCN-STIC and related CCN implementation guides
- internal policies, standards, procedures, hardening guides, and runbooks

The current SCF importer uses heuristic classification of imported authoritative-source columns to seed:

- issuing body
- document type
- jurisdiction
- reusable reference keys

That is a foundation, not the end state. The mature path is to add curated presets for major catalogs so the reference library is governed, deduplicated, and reviewable.

## Control lifecycle in this model

The control object should be understood as the implementation of a requirement, not the requirement text itself.

Recommended lifecycle:

1. `source identified`
   - framework requirements and guide references are imported
2. `control converged`
   - one or more requirements map into a unified control
3. `design defined`
   - implementation guidance, ownership, scope, and evidence strategy are documented
4. `implementation operating`
   - product and flavor implementations exist
5. `assessment ready`
   - evidence plans and test paths are defined
6. `assured`
   - evidence and reviews support assessment outcomes
7. `improving`
   - gaps, exceptions, and control changes feed back into design

## Manual evidence in the same model

Automation should not be a prerequisite for operating the platform. When automation is not viable:

- the unified control still exists
- the implementation record still exists
- the evidence plan still exists
- the assessment can still be run in assisted or manual mode
- manual evidence can be uploaded and reviewed with the same traceability chain

That lets implementation teams outside GRC contribute evidence and narratives without needing direct collector ownership.

## Immediate next maturity steps

- add curated presets for NIST and CCN reference catalogs
- add review workflows for deduplicating imported reference documents
- allow guide references to be attached manually from the workspace
- expose reference-library pages beyond the generic asset catalog
- promote implementation guides into questionnaire-answer generation and remediation planning

## Reference basis

- Secure Controls Framework: <https://securecontrolsframework.com/>
- NIST RMF overview: <https://csrc.nist.gov/projects/risk-management/about-rmf>
- NIST SP 800-53A: <https://csrc.nist.gov/pubs/sp/800/53/a/final>
- NIST SP 800-137: <https://csrc.nist.gov/pubs/sp/800/137/final>
- CCN-CERT CCN-STIC series: <https://www.ccn-cert.cni.es/en/series-ccn-stic/guias/series-ccn-stic.html>
