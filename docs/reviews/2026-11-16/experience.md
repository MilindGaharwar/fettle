# Experience Discipline proposal: publication review

Date: 2026-11-16. Base: `461e73b89d33bfc2d80c945e959be74dafe5f3ab`.
Scope: documentation reconciliation and publication authorized by the operator;
feature implementation and runtime qualification are not part of this change.

## Files

- `docs/experience-discipline-vnext-plan.md`
- `docs/experience-discipline-vnext.ux-spec.md`
- `docs/backlog/experience-discipline-vnext.md`

## Cross-document requirements and adversarial review

| Requirement | Review result |
|---|---|
| Authority and scope remain coherent across the documents | Plan and UX preserve proportional routing, evidence scope and explicit installation approval. Corrected the exclusive OpenCode-location claim using the later suite inventory. |
| Try to satisfy the stated checks without proving the intended claim | A keyword grader could reward claims without actions, or a weighted score could hide an unsafe action. The plan requires observable behavior, independent gates, retained indeterminate cases, protected holdouts and explicit installed-digest checks. |
| Distinguish fixture, proposed and live evidence; preserve non-goals and failure paths | No live model evaluation, accessibility conformance claim, bundle build or host installation. Reference standards must be rebound at ED-0. |

Review method: source/document comparison and manual semantic inspection, not an
independent human acceptance study or live feature evaluation. No new runtime
surface is being delivered. The [validation record](validation.md) reports the
actual checks, environment failures, reruns and residual limits for this publication.
