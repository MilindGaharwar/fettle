# Fettle Documentation

Fettle is the assurance layer between an AI coding agent's authority, actions,
evidence, and independent verification. Start with the outcome you need rather
than reading every subsystem.

## Choose Your Path

| I want to... | Start here | Expected result |
|---|---|---|
| Evaluate Fettle without changing agent settings | `pipx install finefettle`, then `fettle check --changed` | A local quality report |
| Add checks to an agent session | [Agent quick start](../README.md#add-live-agent-governance) | Advisory findings inside supported agents |
| Understand what each language surface supports | [Capability matrix](#capability-matrix) | No ambiguity between hooks, CLI, verify, and editor support |
| Configure a personal project | `fettle init --profile solo` | Lightweight advisory policy |
| Coordinate a team | `fettle init --profile team` | Plans, worklogs, and shared evidence |
| Evaluate delegated-agent governance | `fettle init --profile enterprise` in a test repository | Capsules, claims, verification, and reports to validate |
| Measure test-suite strength | [Mutation evidence](CONFIG.md#mutation-evidence-mutation) | Canonical changed/full Python mutation reports and baseline comparison |
| Connect requirements to tests | `fettle spec lint`, then `fettle spec coverage` | Living-spec and scenario trace evidence |
| Test from a user's perspective | `fettle uat doctor`, then `fettle uat manual` | Explicit acceptance scenarios and observable verdicts |
| Integrate an enterprise analyzer | [Configuration: integrations](CONFIG.md#integrations-integrations-wp-14b) | Explicit, opt-in SonarQube, Black Duck, or Pact evidence |

## The Core Journey

1. Run `fettle init --dry-run` and inspect what would change.
2. Initialize with an appropriate profile.
3. Run `fettle doctor`; resolve missing required tools or invalid policy.
4. Trigger one known advisory finding in a test branch.
5. Use `fettle explain` to inspect the reason and recovery action.
6. Run `fettle verify`, then retain CI as the independent authority.
7. Measure signal before promoting any gate to `enforce`.

## Active Guides

- [Configuration reference](CONFIG.md): precedence, modes, every gate family,
  central policy, integrations, telemetry, workspace routing, and state.
- [OpenCode integration](OPENCODE.md): setup, event mapping, verification, and
  recovery.
- [VS Code integration](../integrations/vscode/README.md): source installation
  and the current Python-only diagnostic boundary.
- [Behavioral evaluations](../evals/README.md): CI-safe static evaluation and
  trusted-operator live experiments.
- [Evidence artifact contract](evidence-artifact-contract.md): portable
  identity, completeness, freshness, and authority boundaries across assurance
  producers.
- [Canonical verification UX contract](canonical-evidence-verification.ux-spec.md):
  active `fettle verify` artifact bindings, terminal states, compatibility, and
  recovery behavior. See the [UAT report](uat/canonical-evidence-verification.md)
  for installed-CLI evidence.
- [Mutation quality contract](mutation-quality.ux-spec.md): user-facing states,
  evidence semantics, and graduation boundaries for Python mutation testing.
- [Mutation quality playbook](mutation-quality-playbook.md): setup, validation
  funnel, cache isolation, exit semantics, and recovery.
- [Roadmap](ROADMAP.md): shipped baseline, active trust work, and graduation
  triggers.
- [Advisory code-intelligence evaluation](advisory-code-intelligence-evaluation.md):
  bounded `codebase-memory-mcp` benchmark, limitations, and no-integration decision.
- [Changelog](../CHANGELOG.md): behavior shipped in each release.
- [Contributing](../CONTRIBUTING.md): setup and evidence expected from changes.
- [Security policy](../SECURITY.md): supported releases, private reporting, and
  trust boundaries.

## Capability Matrix

| Surface | Current scope | Important boundary |
|---|---|---|
| Agent lifecycle | Claude Code, Codex CLI, Gemini CLI, OpenCode | Host transports differ; normalized policy is shared |
| Post-edit adapters | Python, JavaScript/TypeScript, Go, Rust | Native tools must be available |
| `fettle check` | Python Ruff and bundled Semgrep rules | Not the full polyglot adapter surface |
| `fettle verify` | Every affected discovered workspace with a test command | Impacted-test narrowing is Python-specific |
| LSP / VS Code | Python | Hook-only process gates are not editor diagnostics |
| External integrations | SonarQube, Black Duck/Polaris, Pact | Disabled by default; credentials come from environment variables |
| Guided workflows | 17 workflows across supported agents | Workflows guide agent reasoning; CLI commands remain deterministic automation |
| Delegation | Worktrees, claims, topology, spawn, capsules, roles, reports | Defense in depth, not process isolation |
| Mutation evidence | Python preflight, changed/full execution, retained schema-v2 reports, accepted baseline comparison | Requires pinned mutmut; changed-scope enforcement remains advisory |
| Specifications and UAT | Living Markdown specs, trace coverage, agent/manual acceptance verdicts | UAT is report-only; unavailable automation remains visible |

Every analyzer result preserves the distinction between `pass`, `violation`,
`tool_error`, and `unknown`. Surface-specific non-applicable outcomes are also
reported explicitly. Missing or malformed evidence must not become clean.

## Agent Workflows

Canonical workflow sources live in `commands/`, ship in the wheel, and install
with `fettle workflows install` (also run by `fettle init`).

| Category | Workflows |
|---|---|
| Quality | quality, PR review, cross-review, explain, report, baseline |
| Security and readiness | security review, threat model, preflight, operations review |
| Planning and records | plan activate, plan complete, worklog, lean debt |
| Governance | incident learning, MCP approval, MCP revocation |

Invocation names vary by host: Claude Code and Gemini CLI use
`/fettle:<name>`; VS Code and OpenCode use `/fettle-<name>`; Codex CLI uses
`/prompts:fettle-<name>`.

## Trust Model

- Hooks are early feedback and default to advisory behavior.
- CI and explicit verification are independent evidence boundaries.
- Tool errors and unknown analysis remain visible.
- Capsules can tighten inherited policy but cannot loosen it.
- Telemetry is off by default and can only be enabled by digest-pinned central
  policy.
- Shell guards and multi-agent controls supplement, but do not replace,
  least-privilege credentials and isolated runners.

## Architecture and Future Work

These documents explain active design contracts and evidence-gated work; they
are not all descriptions of shipped runtime behavior:

- [Evolution implementation plan](fettle-evolution-implementation-plan.md)
- [Polyglot governance UX contract](polyglot-governance.ux-spec.md)
- [Change-integrity architecture](change-integrity-architecture.md)
- [Change-integrity UX contract](change-integrity.ux-spec.md)
- [Change-integrity implementation plan](change-integrity-implementation-plan.md)
- [Advisory code-intelligence evaluation](advisory-code-intelligence-evaluation.md)
- [TLA+ formal verification](tla-plus-formal-verification.md)

`docs/archive/` and `docs/engagement/` preserve decisions, audits, and work
history. Use this index, the configuration reference, and the changelog for
current product instructions.
