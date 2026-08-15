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
| Run clean-sample preflight inside a 120-second manual window | Temporary installed-CLI project | Timed out; no success claimed |

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

The temporary-project preflight exceeded 120 seconds and was terminated by the
UAT harness. This is retained as error-state evidence only; it did not authorize
a replay or full run. Accepted preflight and calibration evidence remains the
retained run set in the implementation plan.

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

## Decision

P63 developer guidance and readiness are acceptable for advisory use. Full
mutation execution was not repeated: it remains held-out verification, and the
accepted independent calibration evidence is unchanged.
