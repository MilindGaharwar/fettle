---
fettle-work-item: v2
id: evidence-guided-handoffs-pilot
status: open
scope:
  - docs/evidence-guided-handoffs.ux-spec.md
  - docs/evidence-guided-handoffs-plan.md
  - docs/hypothesis-tree-evidence-guided-handoffs.md
  - docs/plan-index.md
  - docs/ROADMAP.md
  - docs/backlog/evidence-guided-handoffs-pilot.md
spec: evidence-guided-handoffs
---

# Evidence-Guided Handoff Pilot

## State

Planning only. Runtime implementation and pilot execution are blocked until
Assurance Integrity CS-6 graduates and the operator separately authorizes WP-EH-0.

## Acceptance Criteria

- The UX contract covers normal, empty, stale, malformed, offline, and recovery
  behavior with BDD scenarios.
- The experiment names a falsifiable primary hypothesis, matched control,
  eligibility rules, primary metrics, cost measures, thresholds, and stop rules.
- Fettle remains a harness-neutral validator; orchestration is an explicit
  non-goal.
- The plan reuses canonical evidence identity and does not define a competing
  authority model.
- No runtime code, configuration, command, policy, or enforcement behavior changes
  in this planning item.

## Verification

Run `uv run python -m fettle.plan_validator
docs/evidence-guided-handoffs-plan.md`, `uv run fettle config --validate`,
`uv run fettle completion validate`, and `uv run fettle check --changed`.
