# UAT Report: TR-3 Truthful Verification

Date: 2026-11-15

## User flow

A coding agent runs `fettle verify`, then reaches an installed Stop hook or an
operator reads `fettle assurance` or `fettle brief`. Every surface reports the
validated result for the current source. A green result means tests executed;
missing counts, zero execution, stale source, and edited stamps stay visible as
non-pass outcomes with a recovery command.

## BDD scenarios

### Edited stamp cannot pass

- **Given** the retained canonical verification failed
- **When** an agent changes only the mutable stamp's `ok` field to true
- **Then** both installed Stop launch modes block on the canonical violation
- **And** the recovery action is `fettle verify`

### Zero executed tests is not a pass

- **Given** pytest collects tests but skips all of them
- **When** the user runs `fettle verify`
- **Then** the result is a violation with `executed = 0`
- **And** the message says that no tests executed

### A command with no test count is unknown

- **Given** a custom command exits zero without producing JUnit evidence
- **When** the user runs `fettle verify`
- **Then** the result is UNKNOWN rather than PASS
- **And** the Stop gate reports it without blocking during the compatibility window

### CI evidence for another commit does not count

- **Given** retained CI evidence belongs to a different commit, or a pushed
  commit has no retained CI status
- **When** the operator builds an Assurance Record
- **Then** the CI dimension is UNKNOWN rather than PASS or NOT_APPLICABLE

### Status views agree with gates

- **Given** source changes after a passing verification
- **When** the operator runs `fettle brief`
- **Then** verification is shown as stale, not green

## Runtime-boundary matrix

| Boundary | Capability | Evidence | Result |
|---|---|---|---|
| Source CLI | Count pytest execution and classify zero/no-count outcomes | `tests/test_trust_remediation_tr3.py` | Pass |
| Installed plugin command | Reject edited `ok` after canonical failure | `tests/test_installed_hooks_e2e.py` | Pass |
| Installed bridge command | Reject edited `ok` after canonical failure | `tests/test_installed_hooks_e2e.py` | Pass |
| CI Stop gate | Reject edited `ok` after canonical CI failure | `tests/test_ci_gate.py` | Pass |
| Assurance/brief | Reject stale, missing, or malformed authority | `tests/test_assurance_record.py`, `tests/test_brief.py` | Pass |

## Accessibility and visual applicability

This package changes CLI and agent-hook text only. It adds no browser page,
DOM, visual layout, pointer interaction, or keyboard navigation. Axe-core,
viewport, visual-regression, and browser performance checks are not applicable.
Messages were exercised through both installed launch modes.

## Manual protocol

- Run a one-test pytest project and confirm the command reports green with one
  executed test.
- Run an all-skipped pytest project and confirm the command reports no tests
  executed and exits non-zero.
- Run a successful custom command without JUnit and confirm UNKNOWN plus the
  report-configuration recovery text.
- Edit `ok` after a failed run and invoke Stop through plugin and bridge paths;
  confirm both block on the canonical violation.
- Change source after a passing record and confirm `fettle brief` says stale.

## Severity assessment

No unresolved P0, P1, P2, or P3 defect is known in the exercised TR-3 flow.

## Decision

FIX_FIRST until the full regression suite, completion evidence, and required
predecessor merge/rebase gates are complete.
