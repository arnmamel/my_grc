# Import And Extensibility Model

This document describes the two new extension surfaces added to `my_grc`:

- external framework imports with traceability
- external assessment script modules with governed bindings

## 1. Framework imports

The import path is designed for sources such as:

- Cloud Security Alliance CCM spreadsheets
- internal policy matrices
- control catalogs exported from CSV or Excel

### Import flow

1. Upload a CSV, `.xlsx`, or `.xls` source.
2. Map the source columns into the normalized fields:
   - requirement ID
   - title
   - description
   - domain
   - family
   - section
   - source reference
   - severity
   - AWS guidance
3. Select an existing framework or create a new one.
4. Choose a unified-control strategy:
   - import only
   - capture mapping suggestions
   - map to existing unified controls when confidence is high
   - create new baseline unified controls for unmatched requirements
5. Import into the local model.

### Traceability model

The import path preserves provenance with:

- `FrameworkImportBatch`
  - which file, which sheet, who imported it, and which mapping rules were used
- `ImportedRequirement`
  - which original row produced which framework control
  - domain, family, section, source reference, raw row payload, and hash
- `UnifiedControlMapping`
  - which imported requirement is met by which reusable implementation control

That gives us end-to-end traceability:

`authority source -> imported requirement -> framework control -> unified control -> implementation -> evidence -> assessment`

## 2. External assessment script modules

Existing Python assessment scripts can now be registered as governed modules instead of living outside the product model.

### Module model

`AssessmentScriptModule` stores:

- module code and name
- entrypoint type
- entrypoint path or Python module
- interpreter
- working directory
- default arguments
- output contract
- optional manifest path
- timeout and lifecycle state

### Binding model

`AssessmentScriptBinding` scopes a module to the environment where it should run:

- organization
- framework binding
- product
- product flavor
- unified control
- framework control
- evidence plan
- config file path
- inline config JSON
- argument templates

This lets a single reusable script be bound differently for different products and flavors.

## 3. Script execution contract

The recommended contract for imported Python scripts is:

- the app provides a JSON context file, usually through `--context-file`
- the script writes a JSON object to stdout

Expected stdout shape:

```json
{
  "status": "pass",
  "summary": "Validated A.5.15",
  "payload": {
    "details": "optional structured content"
  },
  "artifacts": [
    {
      "path": "/absolute/or/working-dir-relative/file.txt",
      "content_type": "text/plain",
      "label": "Optional label"
    }
  ]
}
```

The application then:

- records a governed `AssessmentScriptRun`
- encrypts the evidence payload when stored as an `EvidenceItem`
- optionally uploads the encrypted evidence envelope and returned artifacts to Confluence

## 4. Operator usage

Workspace:

- go to `Import Studio`
- use `Framework Import Wizard` for authority-source onboarding
- use `Script Modules` to register existing Python scripts and bind them to product/control scope

CLI:

- `aws-local-audit importer preview-framework ...`
- `aws-local-audit importer load-framework ...`
- `aws-local-audit importer traceability ...`
- `aws-local-audit script register ...`
- `aws-local-audit script bind ...`
- `aws-local-audit script bindings`

## 5. Current maturity

These capabilities are now at roughly `3/5`:

- the model is governed and traceable
- the workspace and CLI support the main onboarding flows
- script modules can execute through evidence plans

The main remaining gaps before a clean `4/5` are:

- runtime validation in a real Ubuntu/WSL environment
- stronger manifest/schema validation for imported script modules
- richer spreadsheet templates for major sources like CSA CCM
- review-queue surfaces dedicated to import exceptions and stale script bindings
- signed or integrity-checked external module packaging for higher-trust deployments
