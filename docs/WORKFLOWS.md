# Guided Workflows

Canonical workflow sources live in `commands/`, ship in the default wheel, and install
with `fettle workflows install`, which is also run by `fettle init`.

```bash
fettle workflows list
fettle workflows install
```

| Category | Workflows |
|---|---|
| Quality | `quality`, `pr-review`, `review`, `explain`, `report`, `baseline` |
| Security and readiness | `security-review`, `threat-model`, `preflight`, `ops-review` |
| Planning and records | `plan-activate`, `plan-complete`, `worklog`, `lean-debt` |
| Governance | `learn`, `mcp-approve`, `mcp-revoke` |

Invocation names vary by host: Claude Code and Gemini CLI use
`/fettle:<name>`; VS Code and OpenCode use `/fettle-<name>`; Codex CLI uses
`/prompts:fettle-<name>`.

Workflows guide agent reasoning. CLI commands remain the deterministic
automation surface.

Run `fettle workflows list` after installation to see the exact destination and
invocation for each detected host. Re-run `fettle init` after upgrading Fettle so
host registrations and versioned bridges match the installed package.
