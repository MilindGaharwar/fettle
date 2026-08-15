# UAT Report: Mutation Quality Developer Experience

Date: 2026-08-15

## Scenarios Tested

| Scenario | Surface | Result |
|---|---|---|
| Discover mutation commands and playbook | Installed `fettle mutation --help` | Pass |
| Inspect pinned-engine readiness | Installed `fettle doctor --json` | Pass |
| Render complete preflight counts and next action | Human renderer contract | Pass |
| Distinguish success, policy failure, and integrity/tool failure | Exit-code contract | Pass |
| Recover from missing or unsupported mutmut | Doctor unit and JSON contracts | Pass |
| Preserve historical failure regressions | Permanent fixture manifest | Pass |
| Run clean-sample preflight inside a 120-second manual window | Exact wheel in a dedicated environment | Pass: 6 generated, 6 canonicalized, 0 rejected/collisions |
| Execute the copied local validation funnel | Clean installed-CLI project | Pass: changed run killed 6/6 in 4.036 s |

Observed readiness:

```text
mutation: ready
mutmut 2.5.1 ... run: fettle mutation preflight
```

The installed command reported `healthy: true`; the mutation readiness check is
non-required and does not turn unrelated doctor health red. The help surface
linked the public mutation playbook.

## States

- First-time/disabled: covered by the doctor disabled-state test.
- Ready/success: covered through the installed executable and renderer test.
- Empty: covered by preflight's zero-mutant bounded-range and full-scope
  fail-closed tests.
- Error: covered for missing/wrong engine, parser drift, collisions, stale cache,
  timeout, and incomplete evidence.
- Recovery: every visible readiness/error state names one next command or repair.

The original temporary-project preflight exceeded 120 seconds and remains
error-state evidence only. The corrective UAT pinned the exact wheel digest,
fixture digests, dedicated environment, `mutmut==2.5.1`, and executable PATH.
It exposed and repaired mutmut 2.5.1's empty `show all` behavior, then completed
preflight and changed-scope execution. No full mutation run was used.

## Accessibility

- Text and exit-code operation: Pass.
- Keyboard-only operation: Pass; commands are non-interactive.
- Color independence: Pass; states and actions are words, not color alone.
- Browser/axe checks: Not applicable to this CLI-only change.

## Automated Evidence

- CLI/doctor focused suite: 86 passed.
- Mutation/CLI focused suite: 195 passed.
- Full suite and quality scan are recorded at completion.

## Bugs Found

| Severity | Description | Resolution |
|---|---|---|
| P1 | Installed `fettle doctor` initially probed mutmut with unsupported `--version` and falsely reported the pinned engine unsupported | Probe now uses `mutmut version`, matching execution preflight |
| P1 | Installed `fettle doctor --json` did not forward `--json` to the package doctor | CLI parser and subprocess forwarding now preserve JSON output |

## Status

- Implementation: Complete.
- Automated verification: Complete.
- Error-state UAT: Complete.
- Successful installed preflight UAT: Complete.
- Copied validation funnel: Complete.
- P63 milestone: Complete.

## Decision

SHIP. The prior timeout still proves only its error path; independent installed
success evidence now confirms the required flow. Full mutation execution was
not repeated and the accepted independent calibration evidence is unchanged.
