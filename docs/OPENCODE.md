# OpenCode Integration

Fettle's OpenCode plugin forwards OpenCode lifecycle events to the same
dispatcher used by Claude Code. Since WP-140, the dispatcher understands
OpenCode's **native** event shapes (`tool.execute.before/after`,
`session.idle`) directly via `fettle.agents.opencode` — translation is
conformance-tested in Python, and the TypeScript shim is a thin transport.

**Setup: run `fettle init` from a Fettle Git checkout.** It detects
`~/.config/opencode` and registers the plugin while preserving existing config.
The PyPI wheel does not include this TypeScript transport. Manual
registration, if you prefer:

```json
{
  "plugin": [
    "file:///Users/you/projects/fettle/integrations/opencode/fettle.ts"
  ]
}
```

in `~/.config/opencode/config.json`. Set `FETTLE_PLUGIN_ROOT` if Fettle is
installed somewhere other than `~/.claude/plugins/fettle`. Restart OpenCode
after changing its configuration.

The adapter maps:

- `tool.execute.before` to `PreToolUse`
- `tool.execute.after` to `PostToolUse`
- `session.idle` to `Stop`

Claude Code continues to use `hooks/hooks.json` directly; installing this
adapter does not alter or replace that integration.

The adapter forwards local event payloads to Fettle's Python dispatcher. Run
`fettle doctor` after setup, restart OpenCode, and test an advisory rule before
enabling blocking modes.
