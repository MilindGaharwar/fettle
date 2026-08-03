<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/MilindGaharwar/fettle/main/assets/wordmark-dark.svg">
    <img src="https://raw.githubusercontent.com/MilindGaharwar/fettle/main/assets/wordmark-light.svg" alt="Fettle" height="160">
  </picture>
</p>

<h3 align="center">Quality governance inside AI coding sessions</h3>

<p align="center"><b>Catch risky code and broken engineering process while the agent still has the context to fix them.</b></p>

<p align="center">
  <a href="https://pypi.org/project/finefettle/"><img src="https://img.shields.io/pypi/v/finefettle?label=PyPI&color=brightgreen" alt="PyPI"></a>
  <a href="https://github.com/MilindGaharwar/fettle/actions/workflows/ci.yml"><img src="https://github.com/MilindGaharwar/fettle/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/finefettle/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#why-fettle">Why Fettle</a> ·
  <a href="#capabilities">Capabilities</a> ·
  <a href="#multi-agent-work">Multi-agent</a> ·
  <a href="docs/README.md">Docs</a>
</p>

> **fettle** *(v.)* — a foundry term for trimming and cleaning a rough casting.

AI coding agents can produce dozens of edits before commit hooks, CI, or a pull
request reviewer sees the result. Fettle connects to the agent's tool lifecycle,
normalizes events from **Claude Code, Codex CLI, Gemini CLI, and OpenCode**, and
runs configured checks before, after, and at the end of a session.

```text
agent edits ──▶ Fettle checks ──▶ finding returns in-session ──▶ agent repairs
```

**Status: v1.6.1 "Hardened Gates"**

## Quick Start

Agent integrations currently run from a Git checkout:

```bash
git clone https://github.com/MilindGaharwar/fettle ~/projects/fettle
cd ~/projects/fettle
python3 fettle/cli.py init --install-tools
fettle doctor
```

`fettle init` detects installed agents, creates project configuration, and wires
supported integrations without replacing unrelated settings. Preview changes
with `--dry-run`, or generate a fitted configuration explicitly:

```bash
fettle init --interactive
fettle init --profile solo       # also: team, enterprise
```

For the standalone CLI only:

```bash
pipx install finefettle
fettle check --changed
```

The PyPI package is named `finefettle` because the `fettle` package name is
unrelated. The installed command remains `fettle`.

## Why Fettle

Most quality tools act at a repository boundary. Fettle adds an earlier control
point: the session where code is being generated.

| Control point | Typical feedback time | Fettle's role |
|---|---|---|
| Editor or linter | While a human edits | Invoke analysis from agent events too |
| Commit hook | At commit | Catch selected issues before they accumulate |
| CI / PR review | After push | Keep CI as independent evidence, not first feedback |
| Agent session | During generation | Enforce code and process policy with current context |

Fettle is not a replacement for tests, review, or CI. It connects those forms
of evidence into the agent workflow and records what happened.

## Capabilities

### In-session checks

- Runs `ruff` and optional `semgrep` after Python edits.
- Guards destructive shell commands and protected configuration before use.
- Supports opt-in gates for plans, TDD ordering, complexity, coverage, BDD
  links, verification stamps, remote CI, claims, worklogs, and session reports.
- Uses per-check budgets and records tool/config failures instead of presenting
  them as clean analysis.
- Returns advisories by default; blocking behavior is enabled per gate.

### One event model for four agents

Claude Code, Codex CLI, Gemini CLI, and native OpenCode events pass through
agent-specific translators into one dispatcher. This lets a repository express
policy once while using different agent clients. Integration transport and
installation still differ by client; see the [documentation index](docs/README.md).

### Evidence loop

```text
incident or repeated failure
        │
        ▼
quarantined rule proposal ── human review ──▶ promoted learned rule
        ▲                                      │
        └──────── fire / false-positive evidence ────────┘
```

- `fettle learn` drafts Semgrep proposals from incidents or trace signatures.
- Proposed rules remain outside active rule directories until a human runs
  `fettle rules promote`.
- `fettle ratchet` uses recorded evidence to support advisory/enforce changes.
- Suppressions can carry an owner, reason, and expiry.

### Session reliability

```bash
fettle plan start --title "Add export" --item "Write contract test"
fettle plan check "Write contract test"
fettle verify
fettle brief
```

Session plans, worklogs, verification stamps, CI verdicts, and completion
reports give an orchestrator structured state instead of requiring transcript
reconstruction. These gates are opt-in unless selected by a setup profile.

## Multi-Agent Work

Fettle can govern delegated work through isolated worktrees, claims, topology
advice, and policy capsules:

```text
orchestrator ── fettle spawn ──▶ child in worktree
      │                              │
      ├── policy capsule             ├── claim + plan + checks
      └── topology manifest ◀────────└── completion report
```

```bash
fettle topology advise
fettle topology apply
fettle topology status
fettle spawn claude --task "Implement the approved work item"
fettle brief --json
fettle report --lineage
```

Capsules are intended to preserve effective policy across delegation and are
digest-checked by the child session. Treat this as an additional application
control, not a sandbox or substitute for operating-system isolation. Review the
current security notes and enable strict gates only after validating them in
your environment.

## Enterprise Controls

- Digest-pinned central policy through `[extends]`, synchronized outside hooks.
- Append-only JSONL decision traces and org/lineage/compliance reports.
- SARIF and JUnit output for existing CI dashboards.
- Opt-in aggregate telemetry controlled by central policy.
- JSON Schema validation for `.fettle.toml`.
- SLSA provenance and CycloneDX SBOM in the release workflow.

Repository policy, hook policy, CLI scans, CI, and editor diagnostics share
configuration, but each surface supports a different subset of checks. Validate
the exact surface you plan to enforce; do not assume perfect output parity.

## Daily Commands

```bash
fettle                              # local status dashboard
fettle check --changed              # changed Python files
fettle config --validate
fettle doctor --fix
fettle explain                      # explain recent gate decisions
fettle verify [--full]
fettle ci status
fettle report --days 7
```

Discover all commands with `fettle --help` and command-specific options with
`fettle <command> --help`.

## Guided Agent Workflows

The Claude Code plugin also bundles 17 user-invocable slash commands. These are
agent workflows rather than CLI subcommands: they combine Fettle checks with
structured review, explanation, and artifact creation.

| Workflow | Slash commands |
|---|---|
| Quality and review | `/fettle:quality`, `/fettle:pr-review`, `/fettle:review`, `/fettle:explain`, `/fettle:report` |
| Security and operations | `/fettle:security-review`, `/fettle:threat-model`, `/fettle:preflight`, `/fettle:ops-review` |
| Planning and evidence | `/fettle:plan-activate`, `/fettle:plan-complete`, `/fettle:worklog`, `/fettle:baseline` |
| Policy and learning | `/fettle:learn`, `/fettle:mcp-approve`, `/fettle:mcp-revoke`, `/fettle:lean-debt` |

Use these when you want the agent to interpret results or guide a review. Use
the `fettle` CLI for deterministic automation and CI. The slash commands ship
with the Git checkout/plugin, not the standalone PyPI wheel.

## Configuration

Fettle reads `.fettle.toml` from the project root. Start advisory and promote
individual gates after measuring noise:

```toml
[gates.lint]
enabled = true
mode = "advisory"       # advisory | soft | enforce

[gates.plan]
enabled = false
threshold = 3
session_plans = true

[gates.tdd]
enabled = false
mode = "advisory"

[gates.session_report]
enabled = false
```

See the [configuration reference](docs/CONFIG.md) for defaults, supported modes,
central policy, environment variables, and state locations.

## Operational Boundaries

- Python 3.11 or newer is required.
- Agent integrations and the OpenCode transport require a repository checkout;
  the wheel contains the CLI and Python package, not every integration asset.
- Hook-time lint is richest for Python. Other language adapters depend on their
  external tools and configured surface.
- The current LSP/VS Code diagnostic path analyzes Python files only.
- Ruff, Semgrep, test runners, agent CLIs, and GitHub tooling are external and
  optional unless the enabled workflow requires them.
- Opinionated and potentially blocking gates mostly default off or advisory.
- Hooks favor continuity and visible degradation for environment/tool errors;
  use CI for an independent fail-closed boundary.

## Documentation

| Need | Guide |
|---|---|
| Choose the next setup step | [Documentation index](docs/README.md) |
| Configure gates and policy | [Configuration](docs/CONFIG.md) |
| Install OpenCode integration | [OpenCode](docs/OPENCODE.md) |
| Run behavioral evaluations | [Evals](evals/README.md) |
| Track future direction | [Roadmap](docs/ROADMAP.md) |
| Review release history | [Changelog](CHANGELOG.md) |

## Contributing and Testing

Match verification effort to the changed surface. Documentation-only changes
do not require the full test suite unless they alter a tested contract such as
version metadata or executable examples.

```bash
# Documentation or metadata only
git diff --check
fettle config --validate

# Behavior-changing Python code
python -m pytest tests -q
fettle check --changed
```

Fettle dogfoods its own hooks and CI controls. Rules include positive and clean
fixtures; behavioral evals separately test whether feedback changes agent
behavior.

## License

MIT (c) Milind Gaharwar
