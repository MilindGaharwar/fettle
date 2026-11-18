# UAT Report: TR-3 Truthful Verification

Date: 2026-11-18

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

## Fable adversarial outcomes

Every hypothesis was exercised through the installed plugin and bridge commands.
Shared non-hook consumers were also covered by their owning focused tests.

| # | Hypothesis | Outcome |
|---:|---|---|
| 1 | Attacker-controlled UNKNOWN text downgrades missing canonical evidence | Reproduced; fixed. Both modes block on missing canonical evidence. |
| 2 | Rewriting mutable `session_id` reuses another session's evidence | Reproduced; fixed by canonical scope binding. Both modes block `wrong_scope`. |
| 3 | Workspace without a command aggregates to PASS | Reproduced; fixed as `TOOL_ERROR`; both modes consume the same installed Stop path. |
| 4 | Exit-zero command with failing JUnit passes | Reproduced; fixed. Both modes block the canonical violation. |
| 5 | Zero-count/wrapped pytest is advisory | Reproduced only as the documented D-6 compatibility limit: missing counts are UNKNOWN and advisory; zero counted execution is a violation. |
| 6 | Mutable/stale CI revision or a local commit after push passes | Stamp edits and stale SHA did not reproduce; canonical source binding rejects them. Commit-after-push reproduced and was fixed by current-HEAD binding. |
| 7 | Full default never takes effect | Reproduced; fixed in resolved defaults. Both modes record `scope = full` without an explicit key. |
| 8 | Non-finite trace values crash Assurance | Reproduced at the canonical digest boundary; fixed by finite normalization/non-finite sentinel. |
| 9 | Missing `result_state` infers PASS from `ok` | Reproduced; fixed. Missing state now mints `TOOL_ERROR`, never PASS. |
| 10 | One successful workflow masks skipped workflows | Did not reproduce as all-skipped: all-skipped is red. Mixed success/skipped remains intentionally green because at least one workflow succeeded; required-check identity is not available from this API. |
| 11 | Portable argv loses absolute interpreter/report paths or quoted arguments crash | Path projection is deliberate portability, not authority loss; argv is now retained before rendering, so quoted arguments do not reparse or crash. |
| 12 | Unrelated `playwright`/`screenshots` text sets browser marker | Reproduced; fixed. Only a parsed `playwright test` invocation marks browser use. |
| 13 | Brief shows CI for a previous commit as green | Reproduced; fixed by current-HEAD comparison; malformed/missing canonical evidence remains stale. |
| 14 | Effective `profile.test_command` override changes behavior without framework re-derivation | Reproduced; intended policy precedence retained, and framework is now re-derived for scope selection. Workspace policy remains owned by workspace discovery. |
| 15 | Push in another repository makes Assurance CI UNKNOWN | Reproduced; fixed by recording and matching repository identity. |
| 16 | Genuine verification never marks edits tested | Reproduced; fixed. Only canonical PASS marks the session journal tested. |
| 17 | Workspace UNKNOWN blocks despite compatibility window | Reproduced; fixed. Workspace UNKNOWN reaches the same advisory rule as root verification. |
| 18 | CI messages and override scope changed | Reproduced as an intentional fail-closed change: missing canonical evidence blocks and only canonical violations are override-eligible. Documented as covered behavior. |
| 19 | Report path deletion and false pytest detection change behavior | Reproduced; fixed without deletion by report-generation identity. `tox -e pytest` is no longer rewritten. |
| 20 | Independence digest omits arbitrary trace fields and sub-second time | Did not reproduce as an authorization bypass. The digest intentionally projects decision fields; timestamps are normalized to stable seconds. This is listed as not covered rather than full-trace integrity. |

Installed evidence: `8 passed` for the direct Fable cases and `22 passed` for the
broader tampering/deletion/zero-selection/CI matrix, each parameterized over both
launch modes. The complete focused TR-3 suite reported `402 passed` after the
final boundary additions.

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
The D-6 uncounted-command advisory window, same-user forgery without signatures,
required-workflow identity, and full-trace integrity remain explicit limits.

## Decision

Automated and manual UAT pass for the current candidate. Final SHIP remains
blocked until committed-candidate quality, completion, and pre-push gates pass.
