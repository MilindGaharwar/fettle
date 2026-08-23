---
fettle-work-item: true
id: uat-p75-statefulness
status: open
scope:
  - fettle/uat/session.py
spec: plan-uat-strength
---

# P75 — Statefulness and realistic-data probes

Plan: `docs/uat-strength-plan.md`

Give sessions persistent user profiles within a run so scenarios observe
each other's effects like one human's continued use; add deliberate
restart/interruption probes (kill mid-flow, relaunch, verify persistence)
and seeded realistic data generation instead of placeholder strings.

## Done when

- A session executes at least one restart probe and its persistence verdict
  reconciles against artifacts.
- Generated data diversity is measured (distinct-shape count) rather than
  asserted.

## Resolution

Record how it was resolved.
