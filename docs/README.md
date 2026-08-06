# Fettle Documentation

Start with the path that matches what you are trying to accomplish.

## Adopt Fettle

| Goal | Start here |
|---|---|
| Evaluate locally without agent hooks | Install `finefettle`, then run `fettle check --changed` |
| Add agent-session checks | Follow the [README quick start](../README.md#quick-start) from a Git checkout |
| Understand polyglot routing | Read [Languages and surfaces](#languages-and-surfaces) |
| Fit policy to one developer | `fettle init --profile solo` |
| Add shared plans and worklogs | `fettle init --profile team` |
| Evaluate stricter multi-agent controls | `fettle init --profile enterprise` in a test repository first |

## Active Guides

- [Configuration reference](CONFIG.md): gate defaults, modes, central policy,
  telemetry, environment variables, and state.
- [OpenCode integration](OPENCODE.md): transport setup and event mapping.
- [Behavioral evaluations](../evals/README.md): static validation and trusted
  live-agent experiments.
- [VS Code integration](../integrations/vscode/README.md): current Python editor
  diagnostics and source installation.
- [Roadmap](ROADMAP.md): prioritized future work and graduation triggers.
- [Changelog](../CHANGELOG.md): shipped behavior by release.
- [Contributing](../CONTRIBUTING.md): development setup and verification.
- [Security policy](../SECURITY.md): supported releases and private reporting.

## Languages and Surfaces

Support is described by surface rather than by one blanket "supported
languages" label:

| Surface | Current scope |
|---|---|
| Agent post-edit lint | Python, JavaScript/TypeScript, Go, and Rust through workspace-aware adapters |
| `fettle verify` | Every affected discovered workspace with a test command; impacted-test narrowing is currently Python-specific |
| `fettle check --changed` | Changed Python files |
| `fettle check --all` | Python Ruff and bundled Semgrep scan |
| LSP / VS Code diagnostics | Python |

Repositories may contain nested workspaces. Fettle discovers project markers,
uses longest-prefix routing for an edited file, and keeps tool failures distinct
from a clean result. The adapter result vocabulary is `pass`, `violation`,
`tool_error`, and `unknown`.

## Agent Workflows

Fettle ships guided slash-command workflows, canonically defined under
`commands/` and installable into every supported agent environment with
`fettle workflows install` (run automatically by `fettle init`). They
complement deterministic CLI commands by asking the agent to interpret
findings, conduct reviews, or create evidence artifacts.

- Quality: `/fettle:quality`, `/fettle:pr-review`, `/fettle:review`,
  `/fettle:explain`, `/fettle:report`.
- Security and readiness: `/fettle:security-review`, `/fettle:threat-model`,
  `/fettle:preflight`, `/fettle:ops-review`.
- Planning and records: `/fettle:plan-activate`, `/fettle:plan-complete`,
  `/fettle:worklog`, `/fettle:baseline`.
- Governance: `/fettle:learn`, `/fettle:mcp-approve`, `/fettle:mcp-revoke`,
  `/fettle:lean-debt`.

Naming per host: Claude Code and Gemini CLI use `/fettle:<name>`; VS Code and
OpenCode use `/fettle-<name>`; Codex CLI uses `/prompts:fettle-<name>`. Treat
`fettle --help` and the active CLI documentation as authoritative for
automation; the workflows add agent interpretation around those commands.

## Operating Model

1. Begin advisory and inspect `fettle explain` plus `.fettle/trace.jsonl`.
2. Fix missing tools and wiring with `fettle doctor`.
3. Measure noise before promoting a gate to `enforce`.
4. Keep tests and CI as independent evidence boundaries.
5. For delegated agents, validate capsule, worktree, and claim behavior in your
   own runner before relying on strict enforcement.

## Verification Scope

Use change-sensitive verification:

- Documentation-only changes: validate links, formats, examples, metadata, and
  `git diff --check`.
- Run a targeted test when documentation participates in a code contract, such
  as README/package version alignment.
- Run the full suite for behavior-changing code, shared configuration logic, or
  broad refactors.

## Scope Notes

The repository also contains archived plans and engagement records. They retain
design provenance but are not current product instructions. Use this index,
the configuration reference, and the changelog for active behavior.
