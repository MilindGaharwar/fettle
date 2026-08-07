<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/MilindGaharwar/fettle/main/assets/wordmark-dark.svg">
    <img src="https://raw.githubusercontent.com/MilindGaharwar/fettle/main/assets/wordmark-light.svg" alt="Fettle" height="160">
  </picture>
</p>

<h3 align="center">Quality governance for AI coding sessions</h3>

<p align="center"><b>Give agents useful feedback while the code and intent are still in the same conversation.</b></p>

<p align="center">
  <a href="https://pypi.org/project/finefettle/"><img src="https://img.shields.io/pypi/v/finefettle?label=PyPI&color=brightgreen" alt="PyPI"></a>
  <a href="https://github.com/MilindGaharwar/fettle/actions/workflows/ci.yml"><img src="https://github.com/MilindGaharwar/fettle/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/finefettle/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#start-in-two-minutes">Quick start</a> ·
  <a href="#why-fettle">Why Fettle</a> ·
  <a href="#what-makes-it-different">Why it is different</a> ·
  <a href="#capability-map">Capabilities</a> ·
  <a href="docs/README.md">Documentation</a>
</p>

> **fettle** *(v.)* — a foundry term for trimming and cleaning a rough casting.

AI agents can make many related edits before a commit hook, CI job, or reviewer
responds. Fettle moves selected engineering checks into the agent lifecycle so
the finding arrives where it is cheapest to act on: the session that created it.

```text
agent tool call -> Fettle policy + checks -> actionable finding -> repair in context
                         |
                         +-> bounded trace and verification evidence
```

Fettle does not replace tests, review, CI, or a sandbox. It connects those
boundaries to AI-assisted development and makes degraded evidence visible.

## Start in Two Minutes

Choose the path that matches your job.

### Evaluate the CLI

Use the zero-runtime-dependency wheel for local scans, CI, reports, and policy
inspection:

```bash
pipx install finefettle
cd your-project
fettle check --changed
fettle doctor
```

The PyPI package is `finefettle`; the installed command is `fettle`.

### Add Live Agent Governance

Agent transports currently run from a Git checkout because host hook assets are
not part of the wheel:

```bash
git clone https://github.com/MilindGaharwar/fettle ~/projects/fettle
cd ~/projects/fettle
python3 fettle/cli.py init --install-tools
fettle doctor
```

`fettle init` detects Claude Code, Codex CLI, Gemini CLI, and OpenCode, preserves
unrelated host settings, creates an advisory-first project configuration, and
installs guided workflows. Use `--dry-run` to inspect changes first.

```bash
python3 fettle/cli.py init --dry-run
python3 fettle/cli.py init --interactive
```

## Why Fettle

Repository-bound quality controls are essential, but they often respond after
the generation loop has moved on. Fettle adds an earlier control point without
weakening the later ones.

| Control point | What it is good at | Fettle's role |
|---|---|---|
| Editor and linter | Immediate local feedback | Reuse analyzers from agent events |
| Commit hook | Protecting repository transitions | Catch selected issues before they accumulate |
| CI and review | Independent, reproducible evidence | Remain the fail-closed authority |
| Agent session | Intent and context are still available | Return findings and recovery steps in-session |

This matters most when an agent works across files, languages, or delegated
workers. Quality is not only a lint result; it is also whether policy survived
delegation, tests were independently run, evidence is fresh, and tool failure
was reported honestly.

## What Makes It Different

### One Policy Across Four Agent Hosts

Claude Code, Codex CLI, Gemini CLI, and OpenCode events normalize into one
dispatcher and one `.fettle.toml` policy. Host transports differ, but gate logic
does not need to be rewritten for every agent.

### Evidence Never Becomes Clean by Accident

Fettle distinguishes `pass`, `violation`, `tool_error`, `unknown`, and
surface-specific non-applicable outcomes. Missing analyzers, malformed output,
timeouts, and zero mutation evidence cannot manufacture a pass.

### Workspace-Aware Polyglot Routing

Nested Python, JavaScript/TypeScript, Go, and Rust workspaces are discovered
from native project markers. Edits route to the most specific workspace and its
repository-native tools. Python currently has the richest CLI and editor
surface; the [capability map](#capability-map) states the boundaries explicitly.

### Governance That Travels With Delegation

Fettle combines policy capsules, isolated worktrees, work-item claims, session
plans, verification stamps, completion reports, and role-based file authority.
Capsules are digest-checked and tighten-only. These are application controls,
not operating-system isolation.

### Rules Learn From Real Failures, With Human Control

`fettle learn` drafts a rule from an incident or trace signature into
quarantine. A human reviews and promotes it; evidence and false-positive data
drive later ratcheting. The model may propose policy, but it cannot silently
activate it.

### Small Runtime, Strong Release Evidence

The core package has no runtime dependencies. External analyzers remain
explicit and user-controlled. Releases use PyPI Trusted Publishing, GitHub build
provenance attestations, pinned workflow actions, and a CycloneDX SBOM.

## Capability Map

Support is described by surface, not by one broad "polyglot" claim.

| Surface | Current scope |
|---|---|
| Agent lifecycle | Claude Code, Codex CLI, Gemini CLI, OpenCode |
| Post-edit workspace adapters | Python, JavaScript/TypeScript, Go, Rust |
| `fettle check` | Python Ruff and bundled Semgrep rules |
| `fettle verify` | Affected discovered workspaces; Python can narrow to impacted tests |
| LSP / VS Code | Python diagnostics |
| External integrations | SonarQube, Black Duck/Polaris, Pact; opt-in |
| Guided workflows | 17 quality, security, planning, learning, and readiness workflows |
| Multi-agent controls | Worktrees, claims, topology, spawn, capsules, role authority, reports |
| Assurance | Canonical result states, behavioral evals, advisory mutation evidence, TLA+ models for selected protocols |

### Quality and Security Gates

- Ruff and bundled Semgrep checks with actionable locations and rerun commands.
- Destructive-command, protected-config, MCP package-trust, secret, boundary,
  dependency, and deployment checks.
- Plan, TDD ordering, complexity, coverage, BDD, worklog, claims, verification,
  and remote-CI gates.
- Per-check budgets and advisory-first defaults so teams can measure signal
  before enabling enforcement.

### Evidence and Operations

```bash
fettle config --explain       # effective value and provenance for each key
fettle explain                # recent gate decisions and recovery context
fettle verify                 # run tests and bind a verification stamp
fettle ci                     # independent fail-closed gate sequence
fettle report --days 7        # effectiveness and lineage evidence
fettle ratchet show           # evidence for promotion or demotion
```

### Multi-Agent Work

```bash
fettle plan start --title "Add export" --item "Write contract test"
fettle topology advise
fettle spawn claude --role tester --task "Write the failing tests"
fettle work claim export-tests
fettle brief --json
```

Role-based authorship separation is available, while broader end-to-end
graduation evidence remains in progress. Start advisory and validate your agent
runner before enforcing it.

### Guided Workflows

```bash
fettle workflows list
fettle workflows install
```

The 17 bundled workflows cover quality review, PR review, security review,
threat modeling, deployment readiness, plans, worklogs, incident learning,
MCP approval, baselines, explanations, reports, and lean-debt tracking.

## Configuration

Start with advisory defaults and promote one gate at a time:

```toml
[gates.lint]
enabled = true
mode = "advisory"

[gates.tdd]
enabled = false
mode = "advisory"

[gates.verify]
enabled = false
mode = "advisory"
scope = "impacted"
```

Policy resolves through built-in defaults, org and team packs, digest-pinned
central policy, repository and directory configuration, environment overrides,
and a tighten-only delegation capsule. Inspect the final value and source with:

```bash
fettle config --validate
fettle config --explain
```

See the [configuration reference](docs/CONFIG.md) for the complete contract.

## Operational Boundaries

- Python 3.11 or newer is required.
- Agent transports currently require a repository checkout; CLI workflows,
  rules, and templates ship in the wheel.
- External analyzers and language toolchains must be installed when their
  checks are enabled.
- Hooks favor session continuity and visible degradation; CI is the independent
  fail-closed boundary.
- Shell mediation, capsules, worktrees, and role gates are defense in depth,
  not a sandbox or substitute for least privilege.
- Formal models cover selected high-risk protocols, not the whole product.

## Documentation

| Goal | Guide |
|---|---|
| Choose an adoption path | [Documentation index](docs/README.md) |
| Configure gates and policy | [Configuration](docs/CONFIG.md) |
| Connect OpenCode | [OpenCode integration](docs/OPENCODE.md) |
| Use VS Code diagnostics | [VS Code integration](integrations/vscode/README.md) |
| Run behavioral evaluations | [Evaluation lab](evals/README.md) |
| Understand current and planned work | [Roadmap](docs/ROADMAP.md) |
| Review release history | [Changelog](CHANGELOG.md) |
| Contribute | [Contributing](CONTRIBUTING.md) |
| Report a vulnerability | [Security](SECURITY.md) |

## Contributing

Contributions are welcome. Fettle expects focused changes, explicit failure
states, clean and violating fixtures, and verification proportional to risk.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT (c) Milind Gaharwar
