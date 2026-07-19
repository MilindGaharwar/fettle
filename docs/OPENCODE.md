# OpenCode Integration

Fettle's OpenCode plugin translates OpenCode lifecycle events into the same
dispatcher protocol used by Claude Code. This keeps policy and checks in one
implementation.

Add the integration to one active global OpenCode config, such as
`~/.config/opencode/config.json`:

```json
{
  "plugin": [
    "file:///Users/you/.claude/plugins/fettle/integrations/opencode/fettle.ts"
  ]
}
```

Set `FETTLE_PLUGIN_ROOT` if Fettle is installed somewhere other than
`~/.claude/plugins/fettle`. Restart OpenCode after changing its configuration.

The adapter maps:

- `tool.execute.before` to `PreToolUse`
- `tool.execute.after` to `PostToolUse`
- `session.idle` to `Stop`

Claude Code continues to use `hooks/hooks.json` directly; installing this
adapter does not alter or replace that integration.

The TypeScript adapter is distributed with the Git repository. It is not
included in Python wheels because OpenCode loads it directly from the checkout.
