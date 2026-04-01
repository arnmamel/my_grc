# Control Lifecycle Model

This project now treats controls as managed implementation objects, not just static framework rows.

## Why this model

The lifecycle is grounded in public control-management literature from NIST:

- NIST Risk Management Framework, especially the Prepare, Select, Implement, Assess, Authorize, and Monitor cycle:
  - <https://csrc.nist.gov/projects/risk-management/about-rmf>
- NIST SP 800-53A for assessing whether controls are implemented correctly, operating as intended, and producing the desired outcome:
  - <https://csrc.nist.gov/pubs/sp/800/53/a/final>
- NIST SP 800-137 for continuous monitoring and evidence refresh:
  - <https://csrc.nist.gov/pubs/sp/800/137/final>

We use those ideas to keep framework imports, unified controls, implementations, evidence plans, evidence items, and assessments consistent.

## Lifecycle in `my_grc`

Authoritative requirement lifecycle:

1. Source identified
2. Imported into a framework with provenance
3. Reviewed for mapping or baseline expansion
4. Traced to one or more unified controls

Unified control lifecycle:

1. Designed
2. Mapped to source requirements
3. Implemented per organization, product, and flavor
4. Assigned evidence expectations
5. Assessed
6. Monitored and improved

Implementation lifecycle:

1. `design`
2. `in_review`
3. `implemented`
4. `operating`
5. `improving`
6. `retired`

Evidence lifecycle:

1. Plan drafted
2. Plan approved and ready
3. Evidence collected or awaited
4. Reviewer approval
5. Freshness and reuse monitoring

Assurance lifecycle:

1. Evidence gathered
2. Assessment run
3. Human review
4. Accepted, rejected, or sent back for revision

## What this means for imported frameworks

Imported framework rows are requirements. They are not the implementation control by themselves.

In `my_grc`:

- `Framework` and `Control` store the imported authority requirement structure
- `FrameworkImportBatch` and `ImportedRequirement` preserve provenance to the original source file and row
- `UnifiedControl` represents the reusable implementation control baseline
- `UnifiedControlMapping` provides traceability from source requirement to implementation control
- `ControlImplementation` explains how that control is realized for an organization, product, or flavor

This separation is what allows one implementation control to satisfy multiple external requirements while still preserving exact source traceability.

## Recommended operating rule

Do not auto-approve imports blindly.

Preferred path:

1. Import the authority source
2. Review mappings or baseline additions
3. Approve unified-control mappings
4. Define product-aware implementation records
5. Define evidence plans and AWS targets
6. Run assessments and continuous monitoring
