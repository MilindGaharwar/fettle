# Antigravity Host Implementation Plan

Status: assessment complete; implementation is a no-go until a pinned CLI
runtime establishes the enforcement contract. Current Gemini CLI support remains
unchanged.

Related UX contract: [antigravity-host.ux-spec.md](antigravity-host.ux-spec.md)

## Outcome

If the runtime gate passes, add Antigravity CLI as a distinct Fettle host without
weakening or replacing Gemini CLI support. Normalize its events into Fettle's
existing policy model, then serialize decisions back to its native wire contract
at the dispatcher boundary.

## User Story

As an Antigravity user, I want Fettle to preserve my host configuration and
enforce the same repository policy with protocol-correct responses, so I can use
the new host without a governance gap.

## Evidence Snapshot

Reviewed 2026-08-16 against official Google documentation:

- [Antigravity CLI features](https://antigravity.google/docs/cli/features/)
  identifies CLI `v1.1.13`, plugin `hooks.json`, and the CLI profile at
  `~/.gemini/antigravity-cli/`.
- [Plugins and skills](https://antigravity.google/docs/cli/plugins/) says hooks
  may be supplied by a plugin or primary `settings.json` and inspected with
  `/hooks`. It does not define CLI hook event payloads or response semantics.
- [Gemini CLI migration](https://antigravity.google/docs/cli/gcli-migration/)
  documents automatic first-launch migration and `agy plugin import gemini`,
  while explicitly describing only partial parity.
- [Antigravity 2.0 hooks](https://antigravity.google/docs/hooks/) documents
  `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, and `Stop`,
  camelCase input, second-based timeouts, and native decisions. That page is
  scoped to Antigravity 2.0 `v2.8.1`, not the CLI `v1.1.13` documentation set;
  it is candidate design evidence, not sufficient CLI release evidence.
- No `agy` or `antigravity` executable or Antigravity application is available
  in the current UAT environment, so configuration loading and wire behavior
  could not be observed.

Evidence rule: a customization file being discoverable does not prove that the
CLI emits the 2.0 payload or honors the 2.0 response. Missing CLI-specific or
live evidence remains a non-pass.

## Compatibility Matrix

| Fettle requirement | Gemini CLI | Antigravity CLI v1.1.13 evidence | Decision |
|---|---|---|---|
| Pre-tool enforcement | `BeforeTool` adapter exists | Hooks are advertised; event and wire schema not published in CLI docs | Blocked |
| Post-tool diagnostics | `AfterTool` adapter exists | Hooks are advertised; output/remediation contract not published | Blocked |
| Completion enforcement | `AfterAgent` adapter exists | Stop behavior is not published in CLI docs | Blocked |
| Configuration ownership | Merge in `~/.gemini/settings.json` | Plugin `hooks.json` and primary settings hooks documented; exact settings shape and merge ownership absent | Plugin is preferred, live validation required |
| Commands and workflows | Gemini TOML commands | Skills/plugins and Gemini import are documented | Compatible in principle, not a hook substitute |
| Policy/context | `GEMINI.md` and existing adapter | `GEMINI.md`, `AGENTS.md`, rules, MCP, and permissions documented | Advisory/context only; not enforcement parity |
| Authentication | Existing paths remain valid for eligible users | First-launch token migration to OS keyring documented | Do not copy or inspect credentials |
| Headless UAT | Existing runner contract | Headless capability documented separately; hook behavior unobserved | Blocked |

## Migration Decision

Support both hosts during migration. Do not replace or alias Gemini CLI:

- Existing enterprise, API-key, and Workspace users may still depend on Gemini
  CLI, and its event contract differs from the Antigravity 2.0 candidate.
- Antigravity CLI is a separate host and must receive a separate adapter,
  registration owner, runner, doctor state, and UAT evidence.
- Prefer a versioned Antigravity plugin over direct mutation of sparse user
  settings if live validation proves plugin installation and disable/upgrade
  behavior. This gives Fettle an explicit ownership boundary.
- Do not implement from the 2.0 schema alone. Reconsider the no-go only after a
  pinned `agy` CLI demonstrates its exact stdin, stdout, exit-code, timeout,
  ordering, bypass, and nested-agent behavior.
- Deprecation timing for Gemini is not set. Revisit only after Antigravity reaches
  supported-installed status and Gemini's supported authentication paths are
  officially retired.

## Decision And Tradeoffs

### Recommended after the runtime gate: host-aware serialization at the dispatcher boundary

Detection returns both the normalized `HookInput` and host identity. The
aggregator continues to produce a host-neutral decision, while a small host
serializer converts that decision to Antigravity or the existing shared wire.

Benefits:

- Existing checks and `CheckResult` remain host-neutral.
- Antigravity-specific deny/continue semantics cannot leak into Codex's strict
  parser or Gemini output.
- Future host protocol tests have one explicit boundary.

Cost: the dispatcher contract changes from normalization-only to preserving host
identity through final serialization.

### Rejected: alias Antigravity to Gemini

This is smaller but incorrect. Event names, casing, tool names, timeout units,
and output decisions differ.

### Rejected: put Antigravity fields in `CheckResult` or `Aggregator`

This couples every check and aggregation test to one host and increases the risk
of cross-host schema regressions.

### Preferred pending validation: plugin-first packaging

A versioned Antigravity plugin is the best documented ownership boundary, but its
installation, discovery, disablement, and upgrade behavior still require live
validation. Do not mutate primary sparse settings until an ownership-safe schema
is documented and observed.

## Candidate Contract, Not Release Evidence

- Add `AgentKind.ANTIGRAVITY` and `fettle/agents/antigravity.py`.
- Add a detection API that returns host identity with normalized input while
  retaining `normalize()` for callers that need only `HookInput`.
- Normalize documented tools at minimum:
  `run_command -> Bash`, `write_to_file -> Write`, and
  `replace_file_content -> Edit`.
- Normalize PascalCase arguments to existing keys such as `command`,
  `file_path`, `old_string`, and `new_string` only when the documented tool
  contract proves each mapping.
- If the CLI matches the 2.0 contract, serialize allow and deny decisions
  explicitly for `PreToolUse`.
- If live evidence confirms it, serialize a completion block as `continue` for
  `Stop`.
- Emit only `{}` for `PostToolUse` if the CLI documents or accepts that
  output.
- Preserve the existing output byte contract for Claude Code, Codex, Gemini CLI,
  OpenCode, and unknown payloads.

## Work Packages

Tests are written before behavior changes. Each item is intended as one small,
independently verifiable change.

### WP1: Freeze Live Contract Evidence

- [ ] Install or obtain access to pinned Antigravity CLI `v1.1.13` or later;
  verify with
  `agy --version` and retain only version metadata.
- [ ] Capture redacted input/output samples for allow, pre-tool deny, post-tool,
  and stop continue; verify samples contain no credentials, prompts, source
  content, absolute home paths, or headers.
- [ ] Exercise timeout, process failure, malformed JSON, missing decision, hook
  ordering, disabled hook, nested agent, MCP tool, and
  `--dangerously-skip-permissions` behavior; record each as pass, non-pass, or
  unknown rather than inferring it.
- [ ] Confirm plugin `hooks.json` discovery, primary-settings hook shape, and
  the authoritative ownership mechanism on a
  clean temporary home before registration code is written.

### WP2: Fixture-First Normalization

- [ ] Add redacted Antigravity cases to
  `tests/fixtures/agent_payloads/conformance.json`; verify they express edit,
  write, command, and stop without invented fields.
- [ ] Extend `tests/test_agents.py` detection and conformance assertions with
  `antigravity`; run `pytest tests/test_agents.py` and observe the expected
  failures before implementation.
- [ ] Add malformed payload boundaries to `tests/test_agents.py`; verify missing
  `toolCall`, non-object `args`, invalid workspace paths, and non-string IDs
  remain non-crashing and fail open.
- [ ] Implement `fettle/agents/antigravity.py` and register it in
  `fettle/agents/__init__.py`; rerun `pytest tests/test_agents.py`.

### WP3: Host-Specific Output Boundary

- [ ] Add host serializer tests for Antigravity pre-tool allow/deny,
  post-tool no-op, and stop allow/continue in a focused test module; assert
  exact keys and exit codes.
- [ ] Add regression assertions that existing output-schema tests remain
  byte-compatible for Claude, Codex, Gemini, OpenCode, and unknown payloads.
- [ ] Introduce the smallest host-neutral aggregate result or serializer input
  needed in `fettle/dispatcher_aggregate.py`; do not add native Antigravity keys
  to `CheckResult`.
- [ ] Preserve detected `AgentKind` in `fettle/dispatcher.py` and invoke the host
  serializer after aggregation; run focused dispatcher and output-schema tests.
- [ ] Add subprocess contract tests using native Antigravity fixtures for an
  allowed action, blocked destructive command, and incomplete Stop event.

### WP4: Safe Registration

- [ ] Add isolated-home tests in `tests/test_init_cmd.py` for absent host, fresh
  registration, dry-run, idempotency, foreign hooks, malformed config, and dual
  Gemini/Antigravity installation.
- [ ] Prefer installing a manifest-owned Fettle plugin. Implement direct settings
  merge only if live evidence proves a safe ownership boundary; preserve all
  unrelated configuration.
- [ ] Add Antigravity to `run_init()` only after all ownership and malformed-file
  tests pass.
- [ ] Extend wheel-mode bridge and manifest tests if registration requires a new
  transport asset; otherwise reuse only the existing absolute dispatcher
  command.

### WP5: Doctor, Documentation, And Graduation

- [ ] Add doctor contract tests for unavailable, configured, verified, stale,
  malformed, unsupported-version, and conflicting states.
- [ ] Implement the narrow doctor probe and ensure registration alone is not
  called verified.
- [ ] Update `docs/installed-governance-bridge.md` with Antigravity only after
  wheel/sdist and live runtime evidence pass.
- [ ] Update `docs/ROADMAP.md`, README host lists, and `CHANGELOG.md` only at the
  appropriate experimental or supported graduation state.
- [ ] Run focused tests, full tests, Ruff, the Fettle quality scan, and
  `fettle completion validate` before claiming the milestone complete.

## Blast Radius

Primary files:

- `fettle/agents/antigravity.py`: native payload translator.
- `fettle/agents/__init__.py`: detection order and host identity.
- `fettle/dispatcher.py`: preserve host through output serialization.
- `fettle/dispatcher_aggregate.py`: expose host-neutral aggregate outcome.
- A focused serializer module: native output schema and exit semantics.
- `fettle/init_cmd.py`: safe detection and registration.
- `tests/fixtures/agent_payloads/conformance.json`, `tests/test_agents.py`,
  `tests/test_init_cmd.py`, and dispatcher/output tests: contract evidence.

Secondary risks:

- Existing strict Codex output can regress if serialization is not isolated.
- Incorrect detection order can classify Antigravity as Claude or Gemini.
- Shared `~/.gemini` ancestry can cause Antigravity and Gemini ownership
  confusion even though documented profile paths differ; live discovery evidence
  is mandatory.
- Post-tool advisories may be silently lost because the documented host output
  is empty; this limitation must remain visible.
- A stale kgraph index currently limits impact confidence. Refresh it before
  behavior edits and rerun positional `kgraph impact` on all primary files.

## Success Criteria

Functional:

- Every captured Antigravity fixture normalizes identically to the equivalent
  existing-host action.
- Native pre-tool deny and stop continue responses pass exact schema tests and a
  real supported CLI session.
- Existing host output-schema and end-to-end tests remain unchanged and green.
- Init preserves foreign configuration, is idempotent, and supports concurrent
  Gemini and Antigravity installations.
- Missing, malformed, stale, partial, or contradictory runtime evidence is a
  non-pass for graduation.

Product:

- A user gets a useful status and next action from one `fettle init` run.
- Clean actions remain silent; denied actions contain one concise reason and
  recovery route.
- Registration is never represented as verified runtime governance.

Security:

- No secrets or event bodies enter the generated bridge or retained fixtures.
- No shell command includes host-controlled event data.
- Malformed or foreign configuration is preserved rather than overwritten.
- Bypass-mode and nested-agent behavior are explicitly tested and documented.

## Stop Conditions

- Stop if the live payload differs from the documented fields; update fixtures
  and the contract before implementation rather than adding permissive guesses.
- Stop if Antigravity and Gemini cannot be safely distinguished in shared config;
  require an explicit host selector or plugin ownership mechanism.
- Do not graduate if timeout, malformed-output, disabled-hook, bypass-mode, or
  nested-agent behavior is unknown for an enforcement-critical path.
- Do not emulate post-tool remediation through undocumented output fields.
- Retain Gemini support while enterprise/API-key consumers remain valid.

## Compliance Gate

- Phase 0 UX: complete in `docs/antigravity-host.ux-spec.md`.
- Phase 0.5 UI: not applicable; this is a CLI and hook transport change. Terminal
  accessibility and output states are specified in the UX contract.
- Phase 1 plan: complete in this document.
- Phase 3.5 UAT: Given/When/Then scenarios are defined before implementation.
- Feature manifest: not applicable; Fettle uses `docs/ROADMAP.md` and
  `CHANGELOG.md`.
- Research decision: support both; no-go for implementation until WP1 passes.
- Implementation authorization: requires explicit approval after WP1 evidence.
