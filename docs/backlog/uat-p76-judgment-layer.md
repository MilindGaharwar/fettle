---
fettle-work-item: true
id: uat-p76-judgment-layer
status: done
scope:
  - fettle/uat/reconcile.py
spec: plan-uat-strength
---

# P76 — Judgment layer: evaluator-optimizer pass

Plan: `docs/uat-strength-plan.md` · Research tree: `docs/hypothesis-tree-uat.md`

Add an independent second-pass reviewer that reads transcript *plus* P72
artifacts and hunts specifically for passes-for-the-wrong-reason, missed
confusion/friction signals, and severity classification. Output routes to
the existing `fettle uat attest` HITL gate; it never changes verdicts by
itself.

## Done when

- An adversarial fixture where a scenario passes for the wrong reason is
  flagged by the second pass while the primary reconciler accepted it.
- Second-pass findings carry severity plus the exact artifact reference
  that justifies them; no finding without an artifact resolves.

## Resolution

An optional `uat.evaluator_runner` launches a separate runner invocation over
the transcript and retained P72 artifact bodies. Findings survive only with a
recognized severity and exact scenario artifact hash, route to operator
attestation, and never mutate primary verdicts. Findings, malformed output, or
runner failure keep report completion non-pass.
