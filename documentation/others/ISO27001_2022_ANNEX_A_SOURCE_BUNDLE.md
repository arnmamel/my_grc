# ISO 27001:2022 Annex A Public Source Bundle

## Goal

Identify a public, parseable, and legally safer source bundle for ISO/IEC 27001:2022 Annex A so `my_grc` can:

- preserve full control coverage for all 93 Annex A controls
- keep provenance for every imported field
- enrich unified controls with implementation guidance
- avoid depending on copyrighted ISO text unless a licensed source is supplied by the user

## Recommendation

Use a layered public-source bundle instead of a single source:

1. A downloadable public control catalog for the 93 controls and ISO 27002 attributes.
2. A public HTML summary source for themes and transition context.
3. Public per-control guidance pages for implementation-oriented enrichment.
4. Optional licensed ISO text only when the organization provides it.

This fits the `my_grc` model well because frameworks express requirements, unified controls express how we implement them, and reference documents carry practical guide material.

## Best Public Sources

### 1. Wentz Wu PDF

- Source: `The 93 Attributes of ISO 27002:2022 Security Controls`
- URL: <https://wentzwu.com/wp-content/uploads/2022/02/ISO-27002-Controls.pdf>
- Value:
  - downloadable PDF
  - contains the full 93-control list
  - includes ISO 27002:2022 attribute taxonomy per control
  - easiest public source to use as the base enumerator
- Best fields to extract:
  - `control_id`
  - `title`
  - `iso27002_attributes.control_type`
  - `iso27002_attributes.security_properties`
  - `iso27002_attributes.cybersecurity_concepts`
  - `iso27002_attributes.operational_capabilities`
- Notes:
  - good control coverage
  - weak on practical implementation narrative
  - PDF parsing should normalize multiline rows and hashtag attributes

### 2. ISMS.online Annex A 2022 Guide

- Source: `ISO 27001:2022 Annex A Explained & Simplified`
- URL: <https://www.isms.online/iso-27001/annex-a-2022/>
- Value:
  - strong public HTML source
  - useful for grouping controls under the 4 themes
  - useful for transition context from 2013 to 2022
  - scrape-friendly compared with many PDF-only sources
- Best fields to extract:
  - `control_theme`
  - `theme_order`
  - `transition_notes`
  - `legacy_mapping_2013`
  - `public_summary`
- Notes:
  - suitable as a structural and editorial enrichment layer
  - should not be treated as the normative source

### 3. Per-Control Public Guidance Pages

Use one primary provider and one fallback provider, because some sites change paths or block scraping intermittently.

Primary candidate:

- Source family: Aviso Consultancy ISO 27001:2022 Annex A pages
- Example URL: <https://www.avisoconsultancy.co.uk/iso-27001-2022-annex-a/5-1-policies-for-information-security>
- Value:
  - explicit `Purpose` and `Implementation Guidance` sections
  - directly useful for `my_grc` guidance and manual evidence planning
- Best fields to extract:
  - `purpose_summary`
  - `implementation_guidance`
  - `manual_evidence_examples`

Fallback candidates:

- ISO27001.com reference pages
  - Example: <https://iso27001.com/annex-a/iso-27001-annex-a-5-1-policies-for-information-security/>
- Control Stack pages
  - Example: <https://controlstack.au/controls/iso-27001-a-5-1-policies-for-information-security/>

Use these for paraphrased implementation help, not as the authoritative control statement.

### 4. Transition Context

- Source: PECB transition whitepaper
- URL: <https://pecb.com/whitepaper/isoiec-270012022-transition>
- Value:
  - confirms the 2022 structure
  - useful for migration metadata
  - summarizes new, renamed, and merged controls
- Best fields to extract:
  - `transition_summary`
  - `new_control_flag`
  - `merged_from_2013`

## Sources Not Recommended As The Primary Baseline

Some public GitHub gists and TSV or CSV files appear to contain the full Annex A list, including detailed control descriptions. They are convenient, but they are not the best enterprise baseline because:

- provenance is often unclear
- licensing is often unclear
- they may reproduce normative or near-normative wording
- the maintenance model is weak

They can still be useful for validation or gap-checking, but not as the main import source for `my_grc` unless legal review approves their use.

## Copyright and Usage Rules

The official ISO/IEC 27001 and ISO/IEC 27002 texts are copyrighted. For the `my_grc` baseline:

- keep the official control identifier
- keep the control title where publicly available
- store the requirement body as a paraphrased summary unless the customer provides licensed source text
- preserve all source URLs and source types in provenance metadata
- mark each field with whether it came from public guidance or licensed authority text

Recommended rule:

- `summary` in framework YAML: paraphrased
- `source_reference`: original control id such as `A.5.1`
- `notes`: provenance and parsing notes
- `reference_documents`: public guidance pages and transition material

## Mapping Into `my_grc`

### Framework-Level Fields

- `code`: `ISO27001_2022`
- `name`: `ISO/IEC 27001:2022`
- `version`: `2022`
- `category`: `framework`
- `issuing_body`: `International Organization for Standardization`
- `jurisdiction`: `global`
- `authority_document_key`: `ISO27001_2022`

### Control-Level Fields

- `control_id`: `A.5.1`
- `title`: `Policies for information security`
- `summary`: short paraphrase of the requirement
- `source_reference`: same as `control_id`
- `notes`: source bundle notes and parsing confidence

### ControlMetadata / Enrichment Fields

- `aws_guidance`: AWS-oriented implementation approach
- `check_type`: `manual`, `hybrid`, or `automated`
- `boto3_services`: AWS services needed for evidence
- `boto3_check`: collector intent or validation logic

### Reference Library Fields

- `reference_document.code`: stable source key such as `WENTZWU_ISO27002_2022_ATTRIBUTES`
- `reference_document.name`: source title
- `reference_document.category`: `guidance`, `transition_guide`, or `implementation_guide`
- `source_url`: public source URL
- `jurisdiction`: `global`

## Recommended Normalized Shape

```json
{
  "control_id": "A.5.1",
  "title": "Policies for information security",
  "summary": "Define, approve, communicate, and periodically review information security and topic-specific policies.",
  "control_theme": "organizational",
  "iso27002_attributes": {
    "control_type": ["preventive"],
    "security_properties": ["confidentiality", "integrity", "availability"],
    "cybersecurity_concepts": ["identify"],
    "operational_capabilities": ["governance_and_ecosystem", "resilience"]
  },
  "legacy_mapping_2013": ["A.5.1.1", "A.5.1.2"],
  "implementation_guidance": [
    {
      "source_code": "AVISO_ANNEX_A_GUIDES",
      "summary": "Use approved policy documents, communicate them to personnel, and maintain review evidence."
    }
  ],
  "provenance": [
    {
      "field": "title",
      "source_code": "WENTZWU_ISO27002_2022_ATTRIBUTES"
    },
    {
      "field": "control_theme",
      "source_code": "ISMS_ONLINE_ANNEX_A_2022"
    }
  ]
}
```

## Parser Strategy

### Step 1. Base Catalog

Use the Wentz Wu PDF as the base enumerator:

- parse rows that start with numeric order plus Annex A numeric control id
- normalize numeric ids like `5.1` into framework ids like `A.5.1`
- split hashtag tokens into attribute arrays

### Step 2. Structural Enrichment

Use ISMS.online to enrich:

- theme
- transition notes
- old-to-new mapping hints

### Step 3. Practical Guidance Enrichment

Use per-control HTML pages to enrich:

- purpose
- plain-language implementation hints
- examples of documentary or manual evidence

### Step 4. `my_grc` Projection

Project the normalized records into:

- framework controls
- control metadata
- reference documents
- imported requirement references
- unified control mapping candidates

## Integration Recommendation

The best next implementation step is not replacing the existing ISO YAML. It is adding a curated import preset for `ISO27001_2022` that can:

- read a downloaded Wentz Wu PDF plus HTML enrichment sources
- produce a normalized JSON staging file
- optionally update `src/aws_local_audit/templates/frameworks/iso_27001_2022.yaml`
- register the public guidance sources in the reference library

## Practical Recommendation

For immediate use in `my_grc`:

1. Keep the existing `iso_27001_2022.yaml` as the working baseline.
2. Treat the Wentz Wu PDF as the preferred public base list.
3. Treat ISMS.online plus per-control guide pages as guidance enrichments.
4. Only ingest verbatim control text if the user provides a licensed ISO source file.
