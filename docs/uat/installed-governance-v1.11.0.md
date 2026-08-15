# UAT Report: Installed Governance Bridge v1.11.0

Date: 2026-08-15

## Scenarios Tested

| Scenario | Persona | Environment | Result |
|---|---|---|---|
| Preview all host and repository mutations without writes | New adopter | Clean wheel, isolated HOME | PASS |
| Publish bridge and register four detected hosts | New adopter | Clean wheel, isolated HOME | PASS |
| Repeat initialization without changing valid state | Power user | Clean wheel, isolated HOME | PASS |
| Dispatch a normalized PostToolUse event outside checkout | Power user | Clean wheel, isolated repository | PASS |
| Build and import bridge from source distribution | Maintainer | Clean sdist environment | PASS |
| Detect tampered bridge and provide one recovery command | Accessible terminal user | Automated isolated HOME | PASS |
| Preserve malformed or unrelated host configuration | Existing adopter | Automated isolated HOME | PASS |
| Claude Code executable availability | Host user | Local machine, Claude Code 2.1.233 | AVAILABLE; transport contract tested |
| OpenCode executable availability | Host user | Local machine, OpenCode 1.18.15 | AVAILABLE; transport contract tested |
| Codex CLI real session | Host user | Local machine | UNOBSERVED; executable unavailable |
| Gemini CLI real session | Host user | Local machine | UNOBSERVED; executable unavailable |

## Accessibility

- All initialization, validation, error, and recovery states are textual.
- `--json` provides the same state distinctions without color or TTY behavior.
- Dry-run and recovery require no mouse, animation, or interactive prompt.
- README proof includes semantic SVG title/description, alt text, and an
  authoritative text transcript.

## Performance

- Source-tree `fettle check --changed`: 2.07 seconds at baseline.
- Bridge dispatch completed within the host command timeout in installed-wheel
  UAT. Hook-level performance remains governed by existing per-check budgets.

## Evidence

- Focused bridge, init, doctor, workflow, and assurance-loop tests: 81 passed.
- Wheel and sdist built independently; each installed outside the checkout.
- Wheel dry-run left the isolated HOME bridge path absent.
- Wheel init produced a digest-valid bridge and registered Claude Code, Codex
  CLI, Gemini CLI, and OpenCode fixtures.
- A normalized event executed through `python -m fettle.dispatcher` from the
  wheel environment and returned native hook output.

## Limitations

Real authenticated Codex and Gemini sessions were unavailable. Their package,
event, configuration-preservation, timeout-unit, and dispatcher contracts pass,
but this report does not reinterpret unavailable external sessions as observed
success.

## Decision

SHIP v1.11.0. The installed artifact and host registration contract are
reproducible. Real-session observations remain operational follow-up rather than
hidden completion evidence.
