---
fettle-work-item: v2
id: completion-work-item-linkage
status: done
scope:
  - fettle/completion.py
  - fettle/completion_gate.py
  - fettle/work_items.py
  - fettle/dispatcher_registry.py
  - fettle/consistency_runner.py
  - tests/test_completion.py
  - tests/test_completion_gate.py
  - tests/test_work_items.py
  - tests/test_consistency_runner.py
  - docs/completion-evidence.ux-spec.md
  - docs/completion-evidence-implementation-plan.md
  - docs/completion/**
spec: completion-evidence
---

# Completion and work-item lifecycle linkage

## Acceptance Criteria

- A v2 work item marked `done` without a same-ID completion manifest fails
  explicit validation and completion-gate checks.
- A v2 work item reaches `done` only when every required completion criterion
  has valid evidence.
- Stop and release validate every v2 done work item, including committed items
  merged from another worktree.
- Completion evidence is bound to current bytes in the declared work-item scope.
- Malformed marked work items fail closed, and newly added v1 items are rejected.
- Legacy v1 work items remain readable without historical evidence backfill.
- P56a has a valid same-ID completion manifest and retained evidence.

## Resolution

Completion evaluation now links every `fettle-work-item: v2` done record to a
same-ID completion manifest and current scoped-file digest. Post-edit, Stop,
explicit validation, and release reuse the same fail-closed evaluator. Malformed
marked work items and newly added v1 records are rejected; tracked legacy v1
records remain compatible until migration.
