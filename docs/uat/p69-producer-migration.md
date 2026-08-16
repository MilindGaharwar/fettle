# UAT Report: P69 Producer Migration

Date: 2026-08-16

## Scenarios Tested

| Scenario | Result |
|---|---|
| Inspect complete coverage, UAT, integration, and mutation evidence | Pass |
| Preserve legacy decisions when canonical writing is disabled or fails | Pass |
| Reject missing, malformed, tampered, or wrongly bound override evidence | Pass |
| Retain mutation report fingerprints, identities, and counts | Pass |
| Identify aggregate source windows and incomplete inputs | Pass |

The CLI-only flows preserve existing domain reports and recovery messages.
Canonical sidecar failures are visible without converting legacy pass or
violation states, and each persisted sidecar uses portable paths and atomic
writes.

## Automated Evidence

- Focused P69 suite: 462 passed.
- BDD gate regression suite: 10 passed after restoring list accumulation.
- Full unexcluded suite: 2,631 passed.
- Ruff: passed.
- `fettle config --validate`: passed.
- `fettle completion validate`: `P63: complete`.
- `fettle check --changed`: completed with pre-existing advisory print findings.

## Accessibility

- Text and exit-code operation: Pass.
- Keyboard-only operation: Pass; affected commands are non-interactive.
- Color independence: Pass; states and recovery are textual.
- Browser/axe checks: Not applicable to this backend and CLI migration.

## Decision

SHIP. P69 preserves domain authority while adding portable canonical evidence,
strict override bindings, independent rollback, and visible write failures.
