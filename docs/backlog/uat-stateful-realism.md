---
fettle-work-item: true
id: uat-p75-statefulness
status: done
scope:
  - fettle/uat/session.py
  - fettle/uat/reconcile.py
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
- On a seeded fixture, generated data yields at least 8 distinct input
  equivalence classes (SHA-256-set cardinality), proven by a regression
  test; fewer classes fails the criterion.

## Resolution

Sessions now retain one deterministic profile with eight hashed input classes.
When `uat.start_command` is configured, the agent must stop and relaunch that
command and emit a structured persistence probe. Fettle retains the probe as a
separate artifact and reconciliation confirms it only when the transcript hash
matches; missing, malformed, or drifted evidence is non-pass. Sessions without
an explicit start command report the probe as `NOT_APPLICABLE`.
