---
fettle-work-item: true
id: uat-p73-exploration-charters
status: open
scope:
  - fettle/uat/session.py
  - fettle/uat/reconcile.py
spec: plan-uat-strength
---

# P73 — Beyond-spec exploration charters

Plan: `docs/uat-strength-plan.md`

Extend sessions past scenario execution with session-based-test-management
charters for the agent: time-boxed tours (Saboteur/adversarial,
Money/critical-path, Supermodel/data-boundary), multiple personas, and
malformed-input fuzzing. Discovered anomalies become *candidate* scenarios
that require operator attestation via `fettle uat attest` — never
auto-promoted into specs.

## Done when

- A charter run on a demo app produces candidate scenarios with artifact-
  backed anomaly evidence, and zero candidates enter active specs without
  an attestation record.
- Charter coverage accounting reports which routes/states the agent
  touched versus total discovered surface.
- Coverage accounting succeeds only when the discovered-surface inventory
  is non-empty and touched-surface counts reproduce deterministically from
  retained evidence; enumeration failure exits non-zero instead of
  reporting empty coverage.

## Resolution

Record how it was resolved.
