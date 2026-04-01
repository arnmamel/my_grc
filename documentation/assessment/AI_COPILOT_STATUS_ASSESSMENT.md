# AI Copilot Status Assessment

## Current Status

`my_grc` now has the first real governed compliance-copilot foundation.

What is now implemented:

- persisted AI knowledge packs
- pack versions with contracts and principles
- reusable governed tasks
- explicit reference bindings
- pack eval cases
- stored governed drafts as `AISuggestion` rows
- first pack for `SCF + ISO/IEC 27001:2022 Annex A`
- CLI and workspace integration through `Control Framework Studio`

## Maturity View

### Before This Iteration

- AI suggestions existed
- references existed
- review queue existed
- control mapping context existed

But the AI behavior itself was still mostly implicit.

Estimated maturity for controlled copilot behavior:

- `2.2/5`

### After This Iteration

The platform now has a governed packaging layer and first productive use case.

Estimated maturity for controlled copilot behavior:

- `3.4/5`

## Strongest Gains

- inspectability: packs are now assets
- governance: behavior is versioned and review-oriented
- reusability: tasks are reusable and structured
- traceability: drafts can point back to pack version and citations
- domain alignment: first pack is directly tied to the SCF pivot and ISO Annex A

## Remaining Gaps

- no external LLM execution adapter yet
- no signed publishing or approval gates for pack activation
- no automatic pack-eval execution pipeline yet
- no dedicated promotion workflow for applying governed drafts into mappings or implementations
- no pack-scoped access controls yet
- citations are structured but not yet ranked by source strength
- deterministic draft generation is a safe bridge, not the final copilot end state

## Recommended Next Steps

- add a model-provider adapter layer behind the pack service
- add pack approval workflows and activation restrictions
- add pack-specific review actions in the review queue
- add automated eval runners for `AIKnowledgePackEvalCase`
- add task-to-record promotion flows:
  - mapping rationale -> mapping notes
  - unified control wording -> unified control fields
  - implementation narrative -> implementation record fields
- add role-based control over who can activate, edit, or execute packs
