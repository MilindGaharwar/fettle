# Formal conformance proposal: publication review

Date: 2026-11-16. Base: `461e73b89d33bfc2d80c945e959be74dafe5f3ab`.
Scope: documentation reconciliation and publication authorized by the operator;
feature implementation and runtime qualification are not part of this change.

## Files

- `docs/formal-verification-conformance-plan.md`
- `docs/formal-verification-conformance.ux-spec.md`
- `docs/formal-verification-conformance.ui-spec.md`
- `docs/backlog/formal-verification-conformance.md`

## Cross-document requirements and adversarial review

| Requirement | Review result |
|---|---|
| Authority and scope remain coherent across the documents | Plan/UX/UI and coordination item retain separate model, implementation, evidence and acceptance claims. October AH07 observations are explicitly historical; newer audit records remain unchanged. |
| Try to satisfy the stated checks without proving the intended claim | A model pass could hide Python divergence, stale evidence or missing required observations. The plan requires a separate implementation oracle, fault sensitivity, candidate identity and scoped eligibility; FM-7 through FM-11 cannot promote a new universal authority. |
| Distinguish fixture, proposed and live evidence; preserve non-goals and failure paths | No solver execution, proof, formal qualification or P43 graduation. Finite bounds and incomplete evidence remain visible. |

Review method: source/document comparison and manual semantic inspection, not an
independent human acceptance study or live feature evaluation. No new runtime
surface is being delivered. The [validation record](validation.md) reports the
actual checks, environment failures, reruns and residual limits for this publication.

Structural review found 11 pre-existing task tables missing the required Method column. They now name methods and retain explicit TDD, integration, named regressions and bounded local commands for implementation packages. These are future obligations, not checks claimed as executed here. No validator was weakened.
