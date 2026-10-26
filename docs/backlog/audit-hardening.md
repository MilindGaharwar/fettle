---
fettle-work-item: v2
id: audit-hardening
status: open
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

## Acceptance Criteria

- Required scanner and Action failures cannot produce success.
- Enforced dispatcher checks cannot be omitted into an allow result.
- Concurrent ledger operations preserve the chain or fail explicitly.
- Fresh installed artifacts include graph providers without checkout leakage.
- UAT input values preserve their declared semantic classes.
- Independent verification, current completion evidence, and explicit limitations
  precede a done status. Later discovery/research work retains its admission gates.