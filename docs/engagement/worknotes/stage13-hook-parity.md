# Stage 13 — Full hook parity: Codex CLI, Gemini CLI, OpenCode

**Scope**: backlog item 3 ("runner adapters codex/gemini/opencode"),
widened per instruction to *full* hook parity — both directions:

- **Inbound**: Fettle gates fire inside each agent via its native hook
  system (translator + `fettle init` registration).
- **Outbound**: headless `AgentRunner` adapters so evals/UAT can drive
  each agent CLI.

## Capability matrix

| Capability | Claude Code | Codex CLI | Gemini CLI | OpenCode |
|---|---|---|---|---|
| Inbound translator | `claude_code.py` | `codex.py` (delegates to claude_code) | `gemini.py` | `opencode.py` (WP-140) |
| Detection key | `hook_event_name` | `hook_event_name` + `turn_id` | Gemini event names | `type` (plugin events) |
| PreToolUse equivalent | PreToolUse | PreToolUse | BeforeTool | tool.execute.before |
| PostToolUse equivalent | PostToolUse | PostToolUse | AfterTool | tool.execute.after |
| Stop equivalent | Stop | Stop | AfterAgent | session.idle |
| Registration (`fettle init`) | `~/.claude/plugins/fettle` symlink | `~/.codex/hooks.json` merge + `features.hooks` action | `~/.gemini/settings.json` merge | `~/.config/opencode/config.json` plugin merge |
| Hook timeout units | seconds | seconds | **milliseconds** | n/a (plugin) |
| Outbound runner | `claude -p --dangerously-skip-permissions` | `codex exec --full-auto` | `gemini --yolo -p` | `opencode run` |
| Runner verification | live (dogfooded) | spec-derived¹ | spec-derived¹ | live (`--help` verified) |
| Conformance fixtures | ✅ | ✅ | ✅ | ✅ |

¹ codex/gemini are not installed on this machine; adapters are derived
from primary sources (codex-rs `hooks/src/schema.rs`, gemini-cli
`docs/hooks/reference.md`) and pinned by conformance fixtures.
**Follow-up**: verify against live installs when available.

## The output-wire fix (the actual hard part)

Codex parses hook output with `deny_unknown_fields`. The old aggregator
emitted `hookSpecificOutput.permissionDecision` on **every** block — legal
in lenient Claude/Gemini, illegal in Codex on PostToolUse, and
`hookSpecificOutput` does not exist at all in Codex's Stop output schema.

New event-correct wire (legal in all four hosts):

| Event | Block (exit 2) | Advisory (exit 0) | Clean (exit 0) |
|---|---|---|---|
| PreToolUse | top-level `decision`/`reason` + hso with `permissionDecision: deny` | hso `additionalContext` | hso `hookEventName` |
| PostToolUse | top-level `decision`/`reason` + hso **without** permission fields | hso `additionalContext` | hso `hookEventName` |
| Stop / SubagentStop | top-level `decision`/`reason` only; advisories folded into reason | `{"systemMessage": …}` | `{}` |

`dispatcher._empty_output` follows the same rule (eventless no-op = `{}`).
The OpenCode plugin (`integrations/opencode/fettle.ts`) reads the new
top-level `decision`/`reason` alongside the legacy hso fields.

Claude Code's behavior is unchanged in practice: exit 2 + PreToolUse
`permissionDecision` still drive blocking; the added top-level
`decision`/`reason` is Claude's own documented block shape.

## Spec-derived assumptions (re-verify on live installs)

- Codex `~/.codex/hooks.json` root shape `{"hooks": {…}}` (same event
  schema as the inline `[hooks]` table in config.toml).
- Codex file edits surface as Claude-style tool names on the hook wire
  (their own schema test uses `"Bash"`); native ids `shell`/`local_shell`/
  `apply_patch` are mapped defensively in the translator.
- `codex exec --full-auto` and `gemini --yolo -p` argv shapes.

## Tests

- `tests/test_agents.py` — detection/conformance/robustness across all
  four agents (shared fixtures in
  `tests/fixtures/agent_payloads/conformance.json`), plus native-payload
  dispatcher end-to-end runs per agent.
- `tests/test_output_schema.py` — event-correct wire pinned: Stop block =
  top-level only, Stop advisory = systemMessage, clean Stop = `{}`,
  PostToolUse block carries no permissionDecision.
- `tests/test_init_cmd.py` — codex/gemini registration: created /
  idempotent / preserves-existing / malformed-config-is-action.
- `tests/test_runners.py` — parametrized adapter tests (argv flags, cwd,
  timeout, fail-visible error mapping) + registry has all four.

Full suite: 1516 passed, 4 skipped.
