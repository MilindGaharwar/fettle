# OpenCode Integration

Fettle's OpenCode plugin forwards OpenCode lifecycle events to the same
dispatcher used by Claude Code. Since WP-140, the dispatcher understands
OpenCode's **native** event shapes (`tool.execute.before/after`,
`session.idle`) directly via `fettle.agents.opencode` — translation is
conformance-tested in Python, and the TypeScript shim is a thin transport.

**Setup: run `fettle init`** — it detects `~/.config/opencode` and registers
the plugin automatically, preserving your existing config. Manual
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

The TypeScript adapter is distributed with the Git repository. It is not
included in Python wheels because OpenCode loads it directly from the checkout.
