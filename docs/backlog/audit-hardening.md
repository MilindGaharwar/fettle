---
fettle-work-item: v2
id: audit-hardening
status: claimed
scope:
  - fettle/quality_scan.py
  - fettle/action_entrypoint.py
  - fettle/dispatcher.py
  - fettle/dispatcher_registry.py
  - fettle/dispatcher_types.py
  - fettle/config.py
  - fettle/evidence_ledger.py
  - fettle/uat/session.py
  - fettle/installed_artifact_canary.py
  - pyproject.toml
  - setup.py
  - tests/**
  - .github/workflows/**
  - docs/audit-hardening*
  - docs/plan-index.md
  - docs/backlog/audit-hardening.md
spec: audit-hardening
---

# Audit Hardening

Authorized to start by the operator on 2026-09-18. Full activity inventory and
acceptance criteria: [implementation plan](../audit-hardening-implementation-plan.md).

## Resolution

Done on 2026-10-26. PR #46 source `9791109` landed as tree-equivalent squash
`2605978`; PR #47 source `a572f80` landed as tree-equivalent squash `023f9b3`.
Exact-tip main CI passed after both merges. The criterion-level completion record
is [`docs/completion/audit-hardening.json`](../completion/audit-hardening.json),
with retained detailed evidence in
[`docs/completion/evidence/audit-hardening.json`](../completion/evidence/audit-hardening.json).
This resolution accepts audit hardening only; full mutation qualification remains
`CLOSED_NON_PASS`.

## Acceptance Criteria

- Required scanner and Action failures cannot produce success.
- Enforced dispatcher checks cannot be omitted into an allow result.
- Concurrent ledger operations preserve the chain or fail explicitly.
- Fresh installed artifacts include graph providers without checkout leakage.
- UAT input values preserve their declared semantic classes.
- Independent verification, current completion evidence, and explicit limitations
  precede a done status. Later discovery/research work retains its admission gates.
