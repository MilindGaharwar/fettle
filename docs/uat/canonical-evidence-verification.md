# UAT Report: Canonical Verification Evidence

Date: 2026-08-15

## Scenarios Tested

| Scenario | Persona | Surface | Result |
|---|---|---|---|
| Run verification in a fresh repository | New adopter | Installed CLI, non-TTY | Pass |
| Read the concise green verdict | Accessible terminal user | Plain text | Pass |
| Inspect canonical artifact and stamp reference | Power user/agent | Local JSON | Pass |
| Validate digest and result through installed package | Maintainer | Python API | Pass |

Observed human output:

```text
verify: green — python3 -c pass (full, 0.05s)
```

The generated `.fettle/verify-evidence.json` parsed successfully and its full
digest matched `.fettle/verify.json`'s canonical reference.

## Accessibility

- Text and exit-code operation: Pass.
- Keyboard-only operation: Pass; one non-interactive command.
- Color independence: Pass; verdict includes the word `green`.
- Browser/axe checks: Not applicable to this CLI-only change.

## Performance

- Tiny verification command plus artifact persistence: 0.05 seconds as shown by
  the CLI.
- Stop-gate budget remains 100 ms; automated gate tests passed.

## Automated Evidence

- Focused kernel, contract, finding, and verify tests: 91 passed.
- Full repository suite: 2514 passed in 294.85 seconds.
- Ruff: passed.
- `fettle check`: completed with 69 pre-existing debug-print warnings and no
  findings in changed files.

## Bugs Found

| Severity | Description | Resolution |
|---|---|---|
| P0 | Sidecar write failure initially left the returned run green | The run now becomes non-green with a visible persistence error |
| P1 | Unsupported canonical reference schema was initially ignored | The Stop gate now rejects it as `unsupported` |
| P1 | Fettle-owned untracked runtime files could invalidate their own source snapshot | `.fettle/` runtime state is excluded from source identity |

## Decision

SHIP the P67 verification pilot. Legacy stamps remain available for explicit
rollback; stamps that claim canonical evidence fail closed when it is invalid.
