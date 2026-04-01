# Level-4 Reassessment

## Scope of this pass

This pass focused on the most leverage-heavy gaps left across Phase 1, Phase 2, and Phase 3:

- make evidence execution more governable and plan-driven
- reduce false automation by distinguishing manual, assisted, and automated collection
- tighten review and assurance closure rules
- improve operator UX for evidence, schedules, and suggestion review
- move the autonomy layer from preview-only into governed review artifacts
- raise regression coverage around the new rules

Runtime verification is still incomplete in this environment because no working `python`, `python3`, `py`, or `pytest` executable is currently available in the shell.

## What changed

### Operational evidence and assurance

- evidence collection now respects approved evidence plans as the execution contract
- controls without a plan now produce explicit `plan_missing` work items instead of silently attempting collection
- non-approved plans now produce `plan_pending_review` work items
- manual and assisted controls now create governed `awaiting_collection` items instead of pretending to be automated
- manual evidence that does not require live AWS no longer pollutes the AWS SSO login plan with unnecessary default targets
- assessments now mark unresolved evidence as `needs_evidence`
- assessment approval is now blocked while linked evidence remains unresolved

### Governance backbone

- operational flows now rely only on approved framework-to-unified mappings
- heuristic mapping suggestions can now be captured as governed review artifacts
- mapping suggestions can be promoted directly into approved mappings with reviewer context
- the review queue now includes `awaiting_collection` evidence work, not only failures and pending review states

### Reliability and UX

- schedule execution now uses a runtime lock to reduce accidental overlap
- the workspace `Operations` page now exposes:
  - control execution maps
  - manual evidence action queues
  - scoped schedule execution
  - safer run-time error handling
- the workspace `Review Queue` now includes an `AI Suggestions` lane
- the CLI now supports reviewing AI suggestions

### Quality coverage

- added regression tests for:
  - plan-driven evidence behavior
  - assessment review gating
  - suggestion capture and promotion
  - evidence-action visibility in the review queue

## Updated maturity assessment

Maturity scale:

- `1/5`: concept only
- `2/5`: foundation exists
- `3/5`: usable with material gaps
- `4/5`: strong, governable, deployable
- `5/5`: enterprise-optimized

## Phase maturity

| Phase | Current estimate | Assessment |
| --- | --- | --- |
| Phase 1 foundation | `3.8/5` | The backbone is coherent: frameworks, unified controls, bindings, products, AWS targets, wizarded setup, and offline-first operation are usable and increasingly governed. |
| Phase 2 operations | `3.7/5` | Evidence is now materially more plan-driven, manual evidence is governed, readiness is clearer, and scoped schedules are more operationally safe. |
| Phase 3 enterprise readiness | `3.3/5` | Governed AI suggestion capture, stronger approval closure, and schedule locking move the enterprise layer forward, but RBAC, APIs, and durable workers are still missing. |

## Functional maturity

| Capability | Current estimate | Notes |
| --- | --- | --- |
| Framework catalog and control seeding | `3.8/5` | Strong seeded catalog and custom shells exist; lineage and governance are good enough for controlled use. |
| Unified controls and mappings | `3.5/5` | Approved mappings now matter operationally, and CSV suggestions can enter a review flow. Coverage depth is still growing. |
| Product and flavor-aware scoping | `4/5` | Implementations, evidence, assessments, schedules, and questionnaires are all consistently scope-aware. |
| AWS SSO operating model | `4/5` | Profile registry, validation, login planning, and assisted scope selection are strong for guided use. |
| Evidence engine | `3.7/5` | Evidence plans now drive behavior more honestly, but expiry policy, sufficiency decisions, and broader collector coverage are still open. |
| Manual evidence operations | `3.7/5` | Manual intake, encrypted storage, action queues, review states, and artifact download are in place. |
| Confluence publishing | `3.2/5` | Pages and attachments are supported, but destination policy, updates, and richer routing are still incomplete. |
| Assessments and recurring operations | `3.8/5` | Scoped assessments, schedule status, run execution, and approval gating are strong foundations. |
| Questionnaire support | `3/5` | Drafting and review exist, but reusable answers, export/redaction, and richer review policy are still below level 4. |
| Offline-first local administration | `4/5` | The system remains meaningfully usable without AWS connectivity for frameworks, mappings, questionnaires, assessments, and reporting. |

## Non-functional maturity

| Quality area | Current estimate | Notes |
| --- | --- | --- |
| Security | `3.7/5` | Encrypted evidence, protected secret handling, PAT hygiene, and stronger governed flows exist. RBAC and decrypt-on-demand access policy remain open. |
| Quality engineering | `3.4/5` | Migrations, tests, and deployment assets exist, and coverage improved in this pass. CI enforcement and wider test depth are still needed. |
| Reliability | `3.3/5` | Lock-aware schedule execution and clearer failure states help, but durable jobs, retries, and recovery orchestration are still absent. |
| Scalability | `2.8/5` | The model is ready for more scale, but execution is still interactive and local-process oriented. |
| Integrability | `3.1/5` | AWS and Confluence are meaningful integrations, and the suggestion/review layer is more machine-friendly, but no external API or event model exists yet. |
| Deployment | `3.8/5` | Ubuntu bootstrap, Compose, Alpine containerization, smoke scripts, and scan scripts form a credible deployable baseline. |
| UI and UX | `3.8/5` | The workspace is more action-oriented and less misleading now, especially in operations and review. It still needs lower-density dashboards and richer reporting packs to feel fully level 4. |

## UI and UX reassessment

### Stronger now

- the `Operations` page is closer to a real operator cockpit because it now shows control-level execution mode, plan state, evidence actions, and scoped schedule execution
- the `Review Queue` is more representative of actual work because it now includes AI mapping suggestions and `awaiting_collection` evidence tasks
- the system is less misleading because manual and assisted controls are surfaced as work items instead of fake automated results

### Still below a clear 4/5

- some flows remain form-dense and assume knowledgeable operators
- evidence exploration is readable but still not a full analyst workbench with advanced filters, pagination, or redaction views
- there is no dedicated jobs surface with retries, history filters, and run diagnostics beyond the current scoped schedule controls
- portfolio dashboards still need stronger rollups across products, frameworks, maturity, and assurance states

## Risks reduced in this pass

### Reduced from Phase 1 and Phase 2

- operational flows no longer depend on unapproved mappings
- evidence collection is no longer overly optimistic about automation readiness
- manual controls no longer force unnecessary AWS login plans in common cases
- assessment approval can no longer close while linked evidence remains unresolved
- schedule overlap risk is lower because a runtime lock now exists

### Reduced inside Phase 3

- the autonomy layer is no longer only a preview; suggestions can now enter review and become approved mappings
- operators can dismiss reviewed suggestions so the queue is more governable
- the review queue is closer to a real enterprise action register because evidence work and autonomy work now show up together

## Major gaps still open

### `P1`

- no RBAC or separation of duties
- no verified runtime test pass in this environment
- no evidence access policy beyond application-level behavior

### `P2`

- evidence expiry, attestation ownership, and sufficiency decisions still need deeper workflow support
- Confluence destination routing and idempotent update behavior are still incomplete
- questionnaire exports, reusable answers, and redaction flows are still not level 4

### `P3`

- no background workers or durable queue for evidence and schedule execution
- no external API or event model
- no enterprise connectors beyond AWS and Confluence
- no CI-enforced migration, test, and vulnerability gates in this workspace

## Conclusion

This pass materially improves maturity, especially in the places that were still overstating automation or under-enforcing governance. The project is stronger, more honest, and more usable.

The product is still not at a clean platform-wide `4/5`. The main blockers are enterprise control-plane blockers rather than local feature gaps:

- RBAC and separation of duties
- durable background execution
- external APIs and eventing
- deeper evidence and questionnaire lifecycle policy
- runtime verification on a real Ubuntu or containerized environment

## Recommended next tranche to reach a clear 4/5

1. Add RBAC plus approval segregation for mappings, evidence, questionnaires, and assessments.
2. Add a durable job runner with retries, locking, and a first-class jobs UI.
3. Add evidence attestation, expiry, and sufficiency decisions before assessment closure.
4. Add REST or CLI-export APIs, event hooks, and CI-enforced test, migration, and image-scan gates.
