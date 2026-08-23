---
fettle-work-item: true
id: uat-p72-evidence-hardening
status: open
scope:
  - fettle/uat/reconcile.py
  - fettle/uat/session.py
  - tests/test_uat_reconcile.py
spec: plan-uat-strength
---

# P72 — UAT evidence hardening (trust floor)

Plan: `docs/uat-strength-plan.md` · Research tree: `docs/hypothesis-tree-uat.md`

Capture independent observation channels for every UAT session step —
screenshot (web), accessibility-tree/DOM snapshot, and HTTP interaction log —
and make the reconciler verify each scenario verdict against those artifacts
instead of trusting the transcript's self-reported `OBSERVED:` text.

## Done when

- A session that reports `matches` without a retained artifact for the
  scenario is rejected as `unknown` (fail-visible), proven by a regression
  test.
- Reconciliation survives a tampered transcript when artifacts disagree,
  proven by an adversarial fixture.

## Resolution

Record how it was resolved.
