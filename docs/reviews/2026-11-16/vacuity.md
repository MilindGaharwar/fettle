# Vacuous-test research lead and evidence limits: publication review

Date: 2026-11-16. Base: `461e73b89d33bfc2d80c945e959be74dafe5f3ab`.
Scope: documentation reconciliation and publication authorized by the operator;
feature implementation and runtime qualification are not part of this change.

## Files

- `docs/backlog/vacuous-test-rule-pack.md`
- `docs/evidence-artifact-contract.md`

## Cross-document requirements and adversarial review

| Requirement | Review result |
|---|---|
| Authority and scope remain coherent across the documents | The earlier old-checkout review could not locate billing_authority. The current remote does contain it in capacity-validation plans in mutation_test.py, set false alongside qualification_eligible; it is not a universal evidence-envelope field. canonical_evidence references are also present. The misleading generic field analogy is removed. |
| Try to satisfy the stated checks without proving the intended claim | A digest or field name could be interpreted as proof or permission. The corrected contract states identity limits and producer-owned authority instead of equivalence to a proof corpus. |
| Distinguish fixture, proposed and live evidence; preserve non-goals and failure paths | External OSS Verify/OSS-Fuzz descriptions remain explicitly unverified research leads. Removed the unverified corpus-size assertion; no rules, external enrollment or schema fields adopted. |

Review method: source/document comparison and manual semantic inspection, not an
independent human acceptance study or live feature evaluation. No new runtime
surface is being delivered. The [validation record](validation.md) reports the
actual checks, environment failures, reruns and residual limits for this publication.
