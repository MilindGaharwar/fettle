---
fettle-work-item: true
id: cli-hardening
status: open
scope:
  - fettle/cli.py
  - tests/test_cli.py
  - docs/cli-survivor-classes.json
  - docs/cli-behavioral-kill-list.json
spec: improvement-plan
---

# cli.py mutation hardening (phased)

1,087+ estimated survivors in cli.py (1,789 lines, ~2,300 mutants).
First 149 classified: 84 implementation_detail (waived), 65 behavioral.

## Phase 1 (next session)

Kill the 65 known behavioral survivors (see docs/cli-behavioral-kill-list.json).
Write CLI integration tests asserting exact exit codes and output per
command's success and error paths.

## Phase 2

Run full mutation (3,600s timeout). Auto-classify new survivors. Kill
behavioral. Waive the rest. Repeat until behavioral survivors < 50.

## Phase 3

Re-attempt enforcement flip with `enforce_ready = true` from the
survivor classifier.

## Learnings

See docs/improvement-plan.md "Mutation hardening learnings" section.

## Resolution

Record how it was resolved.
