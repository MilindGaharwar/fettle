# Installed Bridge UAT Plan

Date: 2026-08-16
Status: executed; see `docs/uat/installed-bridge-v1.11.1.md`

## User Story

As a user installing or upgrading Fettle from a wheel, I want each supported
agent host to invoke the installed dispatcher and recover from stale transport
state, so that governance does not depend on a source checkout.

## Assumptions And Safety

- Lifecycle tests use disposable repositories, homes, and virtual environments.
- Host configuration unrelated to Fettle must survive byte-for-byte in meaning.
- Real sessions may use the operator's existing host authentication, but work
  only in a disposable repository and may create only an agreed marker file.
- Missing binaries, authentication, provider access, or host hook support are
  blocked outcomes, not passes.
- Browser, mobile, visual, and axe checks are not applicable to these CLI hosts.

## Acceptance Scenarios

Scenario: Clean wheel install registers every host
  Given a new isolated home with all four host configuration directories
  When the wheel-installed user runs `fettle init`
  Then the versioned bridge validates
  And Claude Code, Codex CLI, Gemini CLI, and OpenCode reference the installed bridge
  And unrelated host settings remain present

Scenario: Upgrade preserves stable host registrations
  Given an isolated home initialized by the previous released wheel
  When Fettle is upgraded to the candidate wheel and `fettle init` runs again
  Then a candidate-version bridge is published atomically
  And every host registration points to the candidate bridge
  And unrelated host settings remain present

Scenario: Stale bridge recovers explicitly
  Given one manifest-owned bridge file has been tampered with
  When bridge validation and doctor run
  Then they report `stale` and instruct the user to run `fettle init`
  When the user reruns `fettle init`
  Then bridge validation returns `supported-installed`

Scenario: Real host session invokes governance
  Given a real supported host CLI is installed and authenticated
  And the candidate wheel bridge is registered
  When a non-interactive session asks the host to create `host-session.txt`
  Then the host completes successfully in the disposable repository
  And Fettle records a host-triggered event for that session

Scenario: Host session cannot run
  Given a host binary, authentication, provider, or hook capability is unavailable
  When the session is attempted
  Then the report identifies the exact blocker and recovery action
  And the host is not marked as passed

## Execution Steps

1. Build wheel and sdist; inspect their contents for bridge resources.
2. Create candidate and previous-release virtual environments.
3. Run clean install and idempotent rerun in an isolated home.
4. Run previous-release initialization, upgrade, and candidate re-initialization.
5. Tamper with a manifest-owned bridge file, verify stale diagnosis, and recover.
6. Send one normalized event through each generated transport configuration.
7. Install missing official host CLIs where feasible without changing project dependencies.
8. Run real Claude Code, Codex CLI, Gemini CLI, and OpenCode sessions in a disposable repository.
9. Record host versions, outcomes, blockers, recovery, and retained evidence.
10. Run focused tests, full tests if code changes, Ruff, Fettle scan, and completion validation.

## Success Criteria

- Clean install, idempotence, upgrade, and stale recovery pass for all four host registrations.
- Each generated transport invokes the candidate wheel's absolute interpreter.
- Every available and authenticated host completes a real session with observable Fettle activity.
- Every unavailable host remains visibly blocked with an exact recovery action.
- No real project files or unrelated user host settings are modified.
