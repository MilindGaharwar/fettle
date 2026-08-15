# UAT Report: Canonical CI Evidence Inspection

Date: 2026-08-15

## Scenarios Tested

| Scenario | Persona | Surface | Result |
|---|---|---|---|
| Validate independently recorded green CI evidence | New adopter | Installed CLI and Stop gate | Pass |
| Reject malformed canonical CI evidence | Maintainer | Enforcing Stop gate | Pass |
| Inspect accepted and rejected evidence | Power user/agent | Human and JSON explain output | Pass |
| Review acceptance and rejection totals | Accessible terminal user | Human and JSON report output | Pass |

The installed executable showed the same rejected `malformed` validity and
recovery data in detailed human and JSON explain output. Human report output
showed `1 accepted, 1 rejected`; JSON reported the same counts.

## Accessibility

- Text and exit-code operation: Pass.
- Keyboard-only operation: Pass; commands are non-interactive.
- Color independence: Pass; validity, decision, reason, and recovery are text.
- Browser/axe checks: Not applicable to this CLI-only change.

## Performance

- 300 accepted Stop-gate validations: p50 0.288 ms, p95 0.359 ms, maximum
  3.29 ms.
- Existing Stop-gate budget: 100 ms.
- The Stop gate performed no network access.

## Automated Evidence

- CI, trace, explain, report, and CLI tests: 124 passed.
- Exact candidate, policy, scope, producer, occurrence, malformed, incomplete,
  local-substitution, trace-loss, and legacy-replay paths have regressions.

## Bugs Found

None during final UAT.

## Decision

SHIP P68. Canonical CI evidence remains independent remote evidence; trace is
diagnostic only, and durable attestation remains outside this work.
