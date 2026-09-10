# OpenCode Integration

Use this guide when you want Fettle findings inside OpenCode rather than only
from the standalone CLI.

Fettle's OpenCode plugin forwards OpenCode lifecycle events to the same
dispatcher used by Claude Code. Since WP-140, the dispatcher understands
OpenCode's **native** event shapes (`tool.execute.before/after`,
`session.idle`) directly via `fettle.agents.opencode` — translation is
conformance-tested in Python, and the TypeScript shim is a thin transport.

Run `fettle init --dry-run`, inspect the proposed plugin registration, then run
`fettle init`. The installed wheel materializes a versioned, digest-checked
TypeScript transport and preserves existing OpenCode config. Restart OpenCode
after installation. Manual checkout registration, if you prefer:

```json
{
  "plugin": [
    "file:///Users/you/projects/fettle/integrations/opencode/fettle.ts"
  ]
}
```

in `~/.config/opencode/config.json`. The checkout transport defaults to
`~/.claude/plugins/fettle`, where `fettle init` links the checkout when Claude
Code is installed. Otherwise set `FETTLE_PLUGIN_ROOT` to the checkout root
before starting OpenCode. Restart OpenCode after changing its configuration.

The adapter maps:

- `tool.execute.before` to `PreToolUse`
- `tool.execute.after` to `PostToolUse`
- `session.idle` to `Stop`

Claude Code continues to use `hooks/hooks.json` directly; installing this
adapter does not alter or replace that integration.

The adapter forwards local event payloads to Fettle's Python dispatcher.

OpenCode can enforce the strict PreToolUse secret boundary by rejecting a tool
before execution. Its current PostToolUse and Stop surfaces are notification-only,
and its transport cannot replace tool output before model exposure. Therefore
pre-model output filtering is explicitly unsupported on OpenCode; use
least-privilege credentials and do not rely on post-tool redaction.

## Verify the Integration

1. Run `fettle doctor` in the target repository.
2. Restart OpenCode after installation or configuration changes.
3. Edit a Python file with a known advisory Ruff finding.
4. Confirm OpenCode receives a Fettle advisory with a recovery action.
5. Run `fettle explain` if the expected finding does not appear.

`fettle doctor` may confirm that the plugin is registered, but it does not infer
trust, execution, or verification from registration. Complete the live exercise
before treating the integration as operational.

Keep the first trial advisory. Only enable blocking modes after the transport,
tool availability, and recovery flow work in your repository.

## Recover From Setup Problems

| Symptom | Action |
|---|---|
| Plugin is not loaded | Check the `file://` path, then restart OpenCode |
| Fettle executable or dispatcher is missing | Run `fettle init`, then `fettle doctor`; in checkout mode verify `FETTLE_PLUGIN_ROOT` points to the checkout |
| No findings appear | Confirm the event reached `.fettle/trace.jsonl`, then verify the relevant gate is enabled |
| External analyzer is unavailable | Install the tool or leave the gate advisory; unavailable analysis is not a clean result |
