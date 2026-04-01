# AI Knowledge Pack Model

## Purpose

`my_grc` now treats compliance copilot behavior as governed data instead of hidden prompt logic.

The model introduces:

- `AIKnowledgePack`
- `AIKnowledgePackVersion`
- `AIKnowledgePackTask`
- `AIKnowledgePackReference`
- `AIKnowledgePackEvalCase`

This lets the platform package domain behavior into reusable, inspectable, versioned modules with explicit references, output contracts, and human-review expectations.

## Why This Matters

Before this iteration, the platform had:

- heuristic AI suggestions
- reference documents
- unified controls
- lifecycle events
- a review queue

Those were useful building blocks, but AI behavior itself was not a first-class governed asset.

Now the platform can represent:

- which pack was used
- which version was active
- which task was executed
- which references informed it
- which draft was produced
- which human still needs to review it

## Core Entities

### `AIKnowledgePack`

Top-level module definition.

Carries:

- stable `pack_code`
- domain and scope
- lifecycle and approval state
- owner
- default task

### `AIKnowledgePackVersion`

Versioned behavior for a pack.

Carries:

- system instruction
- operating principles
- prompt contract
- output contract
- model constraints
- review requirement
- approval and activation metadata

### `AIKnowledgePackTask`

Governed reusable task within a version.

Examples:

- mapping rationale
- unified control wording
- implementation narrative

Each task defines:

- workflow area
- objective
- input schema
- output schema
- task instruction
- review checklist

### `AIKnowledgePackReference`

The reference layer for a pack version.

Can point to:

- `ReferenceDocument`
- `Framework`
- `Control`
- `UnifiedControl`
- `ImportedRequirement`

This lets the pack be explicit about authoritative and guidance sources.

### `AIKnowledgePackEvalCase`

Pack-specific evaluation cases.

Carries:

- test scenario code
- task key
- structured input payload
- expected assertions

This is the basis for pack regression and future AI quality gates.

## Current First Pack

The first seeded pack is:

- `SCF_ISO27001_ANNEX_A`

It is designed to:

- use SCF as the pivot implementation backbone
- use ISO/IEC 27001:2022 Annex A as the source requirement set
- support governed drafts for mappings, unified control wording, and scoped implementations

## Execution Model

The current execution model is deliberately conservative.

The pack service builds:

- a structured prompt package
- a deterministic governed draft
- explicit citations
- assumptions
- review points

That draft can then be stored as an `AISuggestion` with pack version traceability.

This is an intentional bridge state between:

- implicit heuristics
- and a future external-model execution layer

## Governance Model

The pack layer is designed for:

- human review by default
- lifecycle traceability
- reference transparency
- reusable tasks
- versioned behavior
- evaluation-driven improvement

## Next Enterprise Steps

- signed and approval-gated pack publishing
- model-provider execution adapters with policy enforcement
- pack-specific review workflows and promotion actions
- stronger automated eval execution and scoring
- pack bindings by workflow, framework family, and customer context
