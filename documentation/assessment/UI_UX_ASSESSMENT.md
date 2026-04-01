# UI/UX Assessment

## Executive view

The Streamlit workspace is now materially better than a simple admin console. It has a strong visual identity, first-run wizards, a review queue, readiness views, and maturity reporting. Its current maturity is best described as `3.4/5`: coherent and useful, but still denser and more operator-driven than a polished level-4 enterprise product.

## Strengths

- The app is now organized around real operator workflows: onboarding, standards, portfolio, AWS profiles, mappings, review, operations, questionnaires, and maturity.
- The `Wizards` section reduces first-run friction and respects the offline-first model.
- The `Overview` page has become a real control tower by combining maturity, queue pressure, and operational context.
- The `Review Queue` is the strongest enterprise-facing UX surface right now because it turns governance debt into visible actionable work.
- The visual system feels intentional and distinct from a default Streamlit page.

## Main UX gaps

### 1. High information density

Some pages still rely on large forms and broad tables with minimal progressive disclosure. This is workable for power users but not yet ideal for occasional operators.

### 2. Weak task closure cues

The app shows what exists, but several flows still do not clearly answer:

- what is ready
- what is blocked
- who should act next
- what the operator should do first

### 3. Limited deployment/runtime feedback

The workspace shows maturity and readiness, but it still lacks a dedicated deployment/runtime health view with migration state, smoke-test status, and container posture.

### 4. Evidence workflow is not yet tactile enough

Operators can collect evidence and inspect readiness, but there is still no first-class evidence explorer or reviewer-centric workbench.

### 5. Offline-first messaging can be stronger

Offline mode is implemented correctly, but more pages should state clearly whether the current task is local-only, AWS-assisted, or Confluence-assisted.

## Cohesion findings

### Positive

- The app now aligns better with the intended lifecycle: define controls, map them, scope them to products, plan evidence, validate AWS connectivity, collect evidence, assess, review, report.
- The review queue and enterprise maturity model give the workspace a shared center of gravity.

### Risks

- Styling originally depended on remote Google Fonts, which conflicted with the offline-first product model. That dependency should stay removed.
- Some creation flows are still optimistic and assume knowledgeable operators rather than guiding them through consequences and next actions.

## Level-4 UX target

The UI should reach `4/5` when:

- the first-run wizard can bring a clean install to a usable operating baseline without referencing docs mid-flow
- the overview page tells an operator exactly what is blocked, what is healthy, and what to do next
- evidence, reviews, and schedules each have dedicated operator surfaces with history and outcomes
- product/flavor scope is obvious in every operational action
- AWS and offline behavior are visible enough that operators cannot confuse metadata work with live collection work

## Recommended UX roadmap

### Short term

- add a deployment/runtime card to `Overview`
- add stronger empty states with direct next actions
- add filters and counts at the top of review-heavy pages
- keep offline/live mode banners visible on all operational screens

### Mid term

- add an evidence explorer with scoped browsing and decrypt-on-demand access
- add a jobs page with schedule history, failures, and retries
- add “what changed” summaries after write actions
- reduce form sprawl by splitting long forms into steps

### Longer term

- add role-oriented home views for operator, reviewer, and auditor personas
- add saved views and deep links for product, framework, and review contexts
- add richer reporting packs and auditor-friendly export surfaces

## Current maturity score

| UX area | Score | Note |
| --- | --- | --- |
| First-run onboarding | `3.8/5` | Good wizard baseline, still room for better diagnostics and completion cues. |
| Day-to-day operations | `3.4/5` | Readiness and review surfaces are solid, but evidence and jobs UX need more depth. |
| Governance visibility | `3.7/5` | Queue and lifecycle visibility are meaningful strengths. |
| Learnability | `3.2/5` | Stronger task framing and fewer dense forms would help. |
| Offline-first coherence | `3.7/5` | The product behavior is coherent; messaging and state visibility can still improve. |

## Summary

The workspace is no longer the weak point of the product. It is now a credible operator surface. To reach a true level-4 UX, the next step is not a visual rewrite. It is deeper task guidance, better evidence/review ergonomics, and a clearer runtime/deployment picture inside the app itself.
