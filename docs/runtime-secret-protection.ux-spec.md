# UX Spec: Runtime Secret Protection

Status: implemented and contract-tested; installed-host execution and
verification remain machine-specific

## Job To Be Done

When an AI coding agent is about to read data or return tool output, I want
Fettle to prevent credentials from entering the model context, so a mistaken
command or tool call cannot disclose a secret before I can react.

## Personas

- New maintainer: needs dangerous access blocked with one safe recovery action.
- Power user or agent: needs deterministic machine-readable decisions without
  secret values in output.
- Security owner: needs each host capability reported without overstating what
  was installed, trusted, executed, or verified.
- Accessible terminal user: needs plain text status and location; color is not
  required to understand a block.

## Journey

| Phase | User action | Sees | Recovery |
|---|---|---|---|
| Entry | Agent requests a file read or shell command | No prompt for ordinary safe work | None |
| Prevention | Request targets credential material or an environment dump | Block naming path, line when known, and credential type | Use a scoped non-secret source or explicit safe fixture |
| Filtering | Claude Code or Gemini receives tool output containing a credential | Claude Code receives replacement output; Gemini withholds the output with value-free guidance | Inspect the source outside the agent session |
| Failure | Protection cannot parse, scan, or sanitize | Request/output is withheld, with a bounded diagnostic | Run `fettle doctor` and retry after repair |
| Diagnosis | User runs `fettle doctor` | Separate installed, registered, trusted, executed, and verified states | Follow the first missing-state action |

Common safe work adds no interaction. A blocked operation requires one recovery
action and must never print the credential value.

## States

- First-time empty: diagnostics say protection is not registered or verified.
- Cleared empty: removing registration immediately removes the verified claim.
- Filtered empty: a clean scan returns no secret details and allows execution.
- Loading brief: the pre-tool decision completes within its hook budget.
- Loading long: timeout is a blocking protection failure, not an allow.
- Populated: findings contain only file, line, and credential type.
- Error recoverable: malformed input is blocked and names `fettle doctor`.
- Error fatal: unavailable filtering blocks on hosts claiming enforcement.
- Offline: all detection and redaction remain local and deterministic.
- Stale: stale generated hooks or bridges are registered but not verified.

## Accessibility And Information

- Messages use `Blocked secret access: <type> at <file>:<line>`.
- Secret values, matching lines, command expansions, and raw exceptions are
  never included in model-visible output or retained evidence.
- JSON uses explicit state names; no meaning depends on color or symbols.
- Host diagnostics never collapse registration into execution or verification.
- Codex and OpenCode are explicitly unsupported for pre-model output filtering;
  their PreToolUse secret boundary can block execution, but Fettle makes no claim
  that it can sanitize output after a tool has run.

## BDD Scenarios

### Scenario: Sensitive file read is blocked before execution

Given a requested file contains a synthetic credential
When an agent requests the file through a registered read tool
Then Fettle denies the tool before execution and reports only file, line, and
credential type.

### Scenario: Nested shell secret read is blocked

Given a shell command wraps a read or environment dump in another shell
When the agent requests execution
Then Fettle denies the outer command before any nested command executes.

### Scenario: Supported output interception redacts before exposure

Given a tool emits a synthetic credential in normal output or an exception
When a host supporting replacement passes the output through Fettle
Then the host supplies only redacted output to the model.

### Scenario: Filtering failure is non-pass

Given the strict scanner cannot parse or sanitize the request or output
When the boundary runs
Then it blocks or withholds the output and directs the user to diagnostics.

### Scenario: Diagnostic states remain distinct

Given a host binary exists but hooks are stale, untrusted, unexecuted, or have
returned malformed output
When the user runs diagnostics
Then each state is reported separately and the host is not called verified.

### Scenario: Completion requires feature-specific evidence

Given a change adds UI or agent behavior
When only legacy unit tests pass
Then completion remains non-pass until applicable UAT proves persistence and
failure recovery.

## Success Criteria

- Read and shell requests containing protected credentials are denied before
  execution, including nested shell forms.
- Swift dictionaries, JSON, YAML, environment dumps, and exception messages are
  covered with synthetic credentials.
- No denied or redacted result exposes the credential in stdout, stderr, hook
  JSON, trace evidence, or model-visible output.
- A scanner exception or malformed payload cannot allow a protected operation.
- Diagnostics distinguish installed, registered, trusted, executed, and
  verified and identify unsupported host capabilities.
- Generated hooks derive from the installed Fettle version and stale generated
  configurations cannot be reported current.
