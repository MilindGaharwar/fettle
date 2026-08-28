# Capability Matrix

Fettle support is described by surface rather than by one broad "polyglot"
claim.

| Surface | Current scope | Important boundary |
|---|---|---|
| Agent lifecycle | Claude Code, Codex CLI, and OpenCode live-verified; Gemini CLI contract-tested | Host transports differ; normalized policy is shared |
| Post-edit adapters | Python, JavaScript/TypeScript, Go, Rust | Native tools must be available |
| `fettle check` | Python Ruff and bundled Semgrep rules | Not the full polyglot adapter surface |
| `fettle verify` | Every affected discovered workspace with a test command | Impacted-test narrowing is Python-specific |
| LSP / VS Code | Python | Hook-only process gates are not editor diagnostics |
| External integrations | SonarQube, Black Duck/Polaris, Pact | Disabled by default; credentials come from environment variables |
| Guided workflows | 17 workflows across supported agents | Workflows guide agent reasoning; CLI commands remain deterministic automation |
| Delegation | Worktrees, claims, topology, spawn, capsules, roles, reports | Defense in depth, not process isolation |
| Mutation evidence | Python preflight, changed/full execution, retained schema-v2 reports, accepted baseline comparison | Changed-scope survivors are enforced in this repository; adoption elsewhere remains policy-controlled |
| Specifications and UAT | Living Markdown specs, trace coverage, agent/manual acceptance verdicts | UAT is report-only; unavailable automation remains visible |

Every analyzer result preserves the distinction between `pass`, `violation`,
`tool_error`, and `unknown`. Surface-specific non-applicable outcomes are also
reported explicitly. Missing or malformed evidence does not become clean.

See [Configuration](CONFIG.md) for policy details and the
[documentation index](README.md) for task-oriented guides.
