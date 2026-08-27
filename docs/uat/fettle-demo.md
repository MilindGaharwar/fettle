# UAT Report: Fettle Demo And Installed Init

Date: 2026-08-27

## Scenarios Tested

| Scenario | Persona | Environment | Result |
|---|---|---|---|
| Run demo outside a project | New user | Isolated pipx installation on macOS | Pass |
| Repeat demo with identical output | Power user | Two independent subprocesses | Pass |
| Fail independent verification | Power user | Injected verifier failure | Pass |
| Initialize a detected host | New user | Empty Git repo, isolated home, detected OpenCode | Pass |
| Run without network or API key | New user | Local wheel, self-contained runtime | Pass |

## Accessibility

The CLI uses ordered plain text without color-only meaning, cursor control, or
interactive input. Browser accessibility checks do not apply.

## Performance

The installed-wheel demo completed in 0.16 seconds on the local macOS host,
within the 20-second budget.

## Platform Evidence

- macOS: passed through an isolated pipx home.
- Linux: blocking CI builds and installs the exact wheel through pipx in a
  `python:3.12-slim` container, then runs the demo and configures OpenCode.
- Windows: the blocking installed-bridge job runs the demo before bridge checks.
- Container: not run locally because neither Docker nor Podman is installed.

## Decision

PENDING CI: local macOS and isolated-wheel evidence pass. Shipping remains
blocked until the Linux container and Windows jobs pass on the pushed commit.
