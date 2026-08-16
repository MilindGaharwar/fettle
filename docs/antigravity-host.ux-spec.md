# UX Spec: Antigravity Host Support

Status: proposed; runtime support is not yet enabled. Official Antigravity CLI
documentation confirms hook discovery, but not the CLI-specific wire contract
required for Fettle enforcement.

## Jobs To Be Done

When I use Google Antigravity in a Fettle-managed repository, I want `fettle
init` to detect and safely register the host, so the same governance decisions
apply without damaging my existing Antigravity configuration.

When host compatibility is unverified or broken, I want Fettle to report the
exact limitation and recovery action, so I never mistake an installed hook for
working governance.

## Personas

- New adopter: expects `fettle init` to configure detected hosts without
  requiring knowledge of hook schemas.
- Power user or platform engineer: needs idempotent registration, preserved
  custom hooks, version visibility, and deterministic JSON output.
- Accessible terminal user: needs text status and recovery instructions that do
  not depend on color, symbols, or interactive controls.

## Journey

| Phase | User action | Sees | Failure to prevent |
|---|---|---|---|
| Discover | Runs `fettle init` | Antigravity detected, unavailable, or unsupported-version status | Silent non-detection |
| Register | Allows normal initialization | Exact config path and restart or verification action | Overwritten foreign configuration |
| Verify | Runs `fettle doctor` or the documented host probe | Hook registration, supported version, and observed contract status | Configuration mistaken for runtime proof |
| Work | Antigravity invokes a tool or stops | No output on allow; concise reason and recovery on deny/continue | Invalid host response or advisory noise |
| Recover | Repairs config or upgrades the host | Exact rerun command | Raw parser errors or destructive auto-repair |

## Flow And Budgets

1. `fettle init` detects Antigravity alongside, not instead of, Gemini CLI.
2. It preserves unrelated settings and adds only Fettle-owned hook entries.
3. It prints the configuration path and one verification action.
4. `fettle doctor` distinguishes configured, verified, stale, conflict, and
   unavailable states.

Budgets:

- No additional prompt in normal non-interactive initialization.
- One follow-up command to verify registration.
- Clean hook execution produces no user-facing advisory.
- A denied action identifies the decision, reason, and `fettle explain` route.

## Required States

- First-time empty: Antigravity is not detected; report `skipped` without
  creating Antigravity directories.
- Cleared empty: Fettle-owned entries were removed manually; doctor reports the
  missing registration and the exact `fettle init` recovery.
- Filtered empty: a host-specific status request finds no Antigravity install;
  name the requested host.
- Loading brief: initialization and local hook checks remain quiet.
- Loading long: a live conformance probe identifies the command being checked
  and does not claim success before it exits.
- Populated: registration path, host version, events, and verification state are
  visible in human and JSON output.
- Error recoverable: malformed or foreign configuration is preserved; Fettle
  reports manual action without writing.
- Error fatal: an unsupported or contradictory hook contract prevents Fettle
  from claiming Antigravity support and names the required upgrade or evidence.
- Offline: local registered hooks continue; documentation or update checks are
  explicitly unavailable and do not erase local evidence.
- Stale: host version, bridge version, or observed payload no longer matches the
  validated contract; doctor requests revalidation.

## Information Architecture

- Antigravity appears as another host row in existing `fettle init` and doctor
  output. No new top-level command is introduced.
- Gemini CLI remains a separate row and adapter.
- Default output shows status and next action. Technical payload and version
  evidence belong in `--json` or detailed doctor output.

## Accessibility

- Status always has a text label and stable JSON value; color and marks are
  decoration only.
- Output remains understandable with `NO_COLOR=1` and in a non-TTY pipeline.
- Recovery uses copyable commands and paths, not mouse-only interaction.
- Hook denial reasons are concise and do not continually rewrite the terminal.

## Security And Trust

- Initialization never copies credentials, OAuth data, MCP headers, prompts, or
  event bodies into the bridge.
- Malformed settings are not replaced or repaired automatically.
- Only manifest-owned Fettle entries may be upgraded or deduplicated.
- Registration is not presented as verified governance until a real supported
  Antigravity runtime accepts the input and output contracts.

## UAT Scenarios

### Scenario: Fresh supported installation

Given a supported Antigravity CLI installation with a live-verified hook contract
When the user runs `fettle init`
Then Fettle adds one owned hook for each supported lifecycle event
And preserves every unrelated setting and foreign hook
And reports one verification action.

### Scenario: Existing Gemini and Antigravity installations

Given Gemini CLI and Antigravity are both installed
When the user runs `fettle init`
Then each host receives its own protocol-correct registration
And neither host registration replaces or aliases the other.

### Scenario: Malformed configuration

Given Antigravity configuration cannot be parsed as the documented object shape
When the user runs `fettle init`
Then Fettle leaves the file byte-for-byte unchanged
And reports `manual-action` with the path and recovery guidance.

### Scenario: Pre-tool denial

Given Antigravity CLI sends a live-validated `PreToolUse` payload for a destructive command
When Fettle policy blocks the normalized Bash action
Then stdout contains the live-validated Antigravity CLI deny decision and reason
And no Claude, Codex, or Gemini-only fields are emitted.

### Scenario: Stop requires more work

Given Antigravity CLI sends a live-validated `Stop` payload before required criteria pass
When Fettle evaluates completion
Then stdout contains the live-validated Antigravity CLI continue decision and reason
And the response does not claim the required criterion passed.

### Scenario: Runtime contract is unavailable

Given no supported Antigravity executable is available for live conformance
When release evidence is evaluated
Then automated fixture tests may pass
But Antigravity remains proposed or experimental rather than documented as
supported-installed.

## Success Metrics

- Existing settings and foreign hooks are preserved in every registration test.
- Initialization is idempotent and leaves exactly one Fettle-owned hook per
  supported event.
- All normalized conformance fixtures agree with existing hosts.
- Every host response passes a host-specific schema test; no cross-host fields
  leak into Antigravity output.
- A real supported CLI session demonstrates allow, pre-tool deny, and stop
  continue before support graduates.
