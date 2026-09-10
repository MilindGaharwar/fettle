# Runtime Secret Protection Implementation Plan

Status: implementation complete and contract-tested; installed-host execution
and verification remain machine-specific and must be established separately

## User Story

As an AI coding-agent user, I want Fettle to prevent credential disclosure at
the tool boundary and report its enforcement capability truthfully, so passing
checks cannot create false assurance.

## Assumptions And Constraints

- Detection is local and deterministic; no credential text leaves the process.
- The strict runtime boundary fails closed independently of Fettle's general
  fail-open quality checks.
- Output replacement is claimed only for hosts whose transport can replace
  output before model consumption. Notification-only hooks remain unsupported.
- Existing unrelated worktree changes are preserved.
- Existing completion evidence remains compatible; additional evidence
  requirements apply only to claims that declare UI or agent behavior.

## Approach And Tradeoffs

Use a dedicated runtime boundary with shared detection/redaction primitives.
This avoids making every quality check fail closed, which would make agent
sessions brittle, while ensuring the security-critical path cannot fail open.
Conservative path and command blocking can produce false positives; recovery is
an explicit scoped allow policy rather than exposing matched values.

## Blast Radius

- Hook registration and transports: `hooks/hooks.json`, `fettle/bridge.py`,
  `fettle/init_cmd.py`, `integrations/opencode/fettle.ts`.
- Dispatcher selection and failure semantics: `fettle/dispatcher.py`,
  `fettle/dispatcher_registry.py`, agent translators.
- Detection and safe reporting: new runtime boundary plus existing secret and
  finding modules.
- Diagnostics and evidence: `fettle/doctor.py`, host capability declarations,
  completion/UAT contracts.
- Tests: dispatcher, agents, hooks, initialization, diagnostics, credentials,
  completion, and UAT regression suites.

`kgraph impact` was run for the primary files. Its index was stale and lacks
cross-language analysis, so direct call-site and transport tests remain the
authoritative blast-radius evidence.

## Work Packages

1. Add shared typed credential detection and value-free redaction; verify all
   requested synthetic formats and no-value reporting.
2. Add a strict PreToolUse boundary for Read, Bash, and normalized nested calls;
   verify scanner errors block.
3. Add pre-model output replacement for capable transports and explicit
   unsupported capability reporting elsewhere.
4. Replace ambiguous installation health with installed, registered, trusted,
   executed, and verified states; malformed output and tracebacks are non-pass.
5. Generate version-aligned hook configuration and detect stale existing
   generated hooks; preserve user-authored configuration.
6. Require feature-specific completion/UAT evidence for UI and agent claims,
   including persistence and failure recovery.
7. Run focused tests, full tests, Ruff, `fettle check --all`, completion
   validation, and `git diff --check`.

## Completion Gates

- All BDD scenarios in `docs/runtime-secret-protection.ux-spec.md` have direct
  automated evidence.
- No synthetic credential appears in captured process output or traces.
- Every claimed host enforcement state is demonstrated by a transport test.
- Existing legacy behavior remains unchanged outside the strict security path.

## Completion Evidence

- The strict PreToolUse guard is registered before general checks and blocks
  protected Read, Bash, nested-shell, environment-dump, and normalized MCP file
  reads on detection or scanner failure.
- Claude Code can replace credential-bearing tool output and Gemini can withhold
  it with value-free recovery guidance. Codex and OpenCode output filtering is
  explicitly `unsupported`; neither transport is represented as protected after
  execution.
- `fettle doctor` reports `installed`, `registered`, `trusted`, `executed`, and
  `verified` independently. A local registration file proves only registration.
- Generated bridges are versioned and digest-checked; stale generated assets are
  non-pass and route the user to `fettle init`.
- Focused runtime, transport, dispatcher, initialization, diagnostics, and
  completion tests pass. The full verification commands are recorded in the
  working change and must be rerun before release.
