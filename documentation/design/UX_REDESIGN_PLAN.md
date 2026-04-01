# UX Redesign Plan

## Goal

Make `my_grc` significantly easier to use without discarding the enterprise and compliance groundwork already built. The redesign follows a unified workspace strategy:

- a calmer, inventory-first front door for daily use
- universal CRUD across the data model
- clear artifact visibility
- guided assistants and wizard-like next steps
- legacy specialist pages preserved for deep workflows until the unified shell fully absorbs them

## Wave 1: Workspace Shell

Status: implemented

Deliverables:

- add a `Unified Workspace` mode alongside `Legacy Pages`
- introduce a clean landing experience through `Workspace Home`
- introduce `Assistant Center` as a guided, action-oriented entry point
- preserve all existing deep pages behind a legacy mode so nothing is lost

Why this matters:

- users no longer need to understand the whole platform before doing useful work
- navigation becomes intentional instead of page-dense
- the redesign can ship safely without blocking existing operators

## Wave 2: Universal CRUD And Inventory

Status: implemented

Deliverables:

- create an `Asset Catalog` with family filtering and cross-model inventory
- provide create, read, update, and delete operations for all registered asset types
- surface descriptions, counts, and searchable lists for every asset family
- add safer generic form handling for nullable references and typed fields

Why this matters:

- operators can see the whole application state in one place
- editing no longer requires jumping through several specialized pages
- the data model becomes inspectable and maintainable

## Wave 3: Artifact And Operations Experience

Status: implemented

Deliverables:

- add an `Artifact Explorer` for evidence, assessments, imports, and questionnaires
- add an `Operations Center` with readiness checks and operational backlog visibility
- add a `Governance Center` for maturity, lifecycle, and review posture
- add `Settings & Integrations` for offline/runtime preferences and connector health

Why this matters:

- evidence and assurance outputs become first-class operational objects
- live AWS and Confluence activity is easier to prepare safely
- governance stakeholders get a single summary surface

## Wave 4: Assessment And Maturity Layer

Status: implemented

Deliverables:

- add `Workspace Assessment` with combined UI/UX and platform maturity scoring
- wire the redesign into existing phase and enterprise maturity services
- identify the remaining gaps to reach a more uniform level-4 operating posture

Why this matters:

- the redesign is measurable, not cosmetic
- product maturity and user maturity are assessed together
- future work can target the remaining friction instead of guessing

## Remaining Steps To Reach A Stable Level 4

The redesign materially improves usability, but a consistent level 4 still depends on the following work:

- migrate more legacy workflows directly into the unified shell instead of linking back
- add stronger record-specific validation and friendly field hints for complex schemas
- add richer artifact relationship views instead of raw JSON-first inspection
- introduce governed bulk-edit and safe archive flows for high-volume operations
- add runtime-validated UI checks on Ubuntu and inside the container image
- expand guided assistants so they can orchestrate multi-step creation and review flows end to end

## Design Principles Preserved

- offline-first operation remains the default mental model
- AWS SSO login still happens only when a live run requires it
- source traceability and lifecycle state remain visible instead of hidden behind the UI
- security and governance stay explicit even when the experience becomes simpler
