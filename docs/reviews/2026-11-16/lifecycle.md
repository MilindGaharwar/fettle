# Work-item lifecycle proposal: publication review

Date: 2026-11-16. Base: `461e73b89d33bfc2d80c945e959be74dafe5f3ab`.
Scope: documentation reconciliation and publication authorized by the operator;
feature implementation and runtime qualification are not part of this change.

## Files

- `docs/work-item-lifecycle-integrity-plan.md`
- `docs/work-item-lifecycle-integrity.ux-spec.md`
- `docs/backlog/work-item-lifecycle-integrity.md`

## Cross-document requirements and adversarial review

| Requirement | Review result |
|---|---|
| Authority and scope remain coherent across the documents | Plan, UX and backlog agree on structured state, explicit migration approval and separate runtime claims. |
| Try to satisfy the stated checks without proving the intended claim | A Resolution heading could falsely close a partial item. The proposal rejects prose-derived closure, delegates v2 evidence to the existing completion evaluator and preserves P46 as a negative historical case. |
| Distinguish fixture, proposed and live evidence; preserve non-goals and failure paths | No lifecycle invariant, validator, corpus migration or external branch protection was implemented or proved. |

Review method: source/document comparison and manual semantic inspection, not an
independent human acceptance study or live feature evaluation. No new runtime
surface is being delivered. The [validation record](validation.md) reports the
actual checks, environment failures, reruns and residual limits for this publication.
