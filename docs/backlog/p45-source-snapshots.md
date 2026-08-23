---
fettle-work-item: true
id: p45-source-snapshots
status: open
scope:
  - fettle/source_snapshot.py
  - fettle/paths.py
  - fettle/config.py
  - fettle/worktrees.py
  - tests/test_source_snapshot.py
spec: change-integrity-implementation-plan
---

# P45 — Graph-independent committed and working source snapshots

Authorized 2026-08-23 (sole dependency P44 complete). Plan:
`docs/change-integrity-implementation-plan.md` §P45.

Build `fettle/source_snapshot.py`: committed snapshot manifests from Git
tree objects; working manifests covering index/tracked/untracked/required-
ignored inputs with content hashes; restrictive materialization or a
complete read-set API with post-run revalidation; policy provenance bound
into source identity; conflict detection for index conflicts, mode/type
changes, and transient races. Materialization failure must preserve user
files and return an actionable canonical non-pass.

## Done when

Per §5.P45 acceptance: identical trees → identical portable identities;
no provider can read mixed live states into a consequential result;
untracked content changes alter working identity; materialization failure
is canonical non-pass with user files preserved — each proven in
`tests/test_source_snapshot.py`.

## Resolution

Record how it was resolved.
