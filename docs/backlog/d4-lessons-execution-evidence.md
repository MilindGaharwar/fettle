---
fettle-work-item: v2
id: d4-lessons-execution-evidence
status: open
scope:
  - docs/backlog/d4-lessons-execution-evidence.md
  - docs/d4-lessons-implementation-plan.md
  - docs/engagement/TODO.md
  - docs/plan-index.md
spec: mutation-quality-playbook
---

# D4 lessons: execution-evidence hardening

Recorded 2026-11-07 after the D4 full-scope mutation path needed seven fix
cycles (PRs #62 review, #65, #66, #67, and the post-preflight container fix;
gate runs 42156076978, 42193150589, 42317146142; preflight 42344083136) before
one shard executed end to end in the target container. Every defect was
container- or timing-specific, invisible to green unit tests, and first
observed on the CI gate rather than before push. One miss (preflight shards)
cost 256 failed jobs. Two timing fixtures produced opaque `tool_error` shards
that were initially misread as infrastructure.

The [detailed plan](../d4-lessons-implementation-plan.md) turns each lesson into
an advisory mechanism in an existing Fettle seam, in priority order:

1. XE-2 classify `tool_error` shards by cause (`baseline_test_failure` with
   failing test IDs, `engine_crash`, `dependency_missing`, `interrupted`).
2. XE-6 PostToolUse notice when a mutation watch-name file is edited.
3. XE-3 `rules/timing-sensitive-tests.yml` advisory pack.
4. XE-5 `rules/ci-container-jobs.yml` advisory pack (safe.directory, bash,
   venv python, digest pin, slim-without-git).
5. XE-4 retained-output rule (redirected output never uploaded).
6. XE-1 Stop advisory: workflow edited this session has not executed at HEAD.
7. XE-7 playbook section: gate-before-fan-out and container rehearsal.

## Constraints

- `main` is frozen for the D4 three-run sequence; nothing merges before run 3
  is terminal and validated. XE-2 may be prepared on a branch.
- Advisory only. No new required gate, no change to mutation pass semantics,
  outcome budgets, waivers, or D4 criteria. No Docker dependency in Fettle.
- Process lessons (one push per cycle, enumerate siblings before "edit only",
  batch by failure class, quote gate evidence in approvals) remain in operator
  discipline skills, not in this item.

## Done when

Each package has fixture tests that fail before and pass after, validated
packs, `fettle check --changed` clean, and a `behavior-map.md`/`event-map.md`
row where a new check or command is introduced. Promotion of any pack to a
default requires a separate decision with observed false-positive counts.
