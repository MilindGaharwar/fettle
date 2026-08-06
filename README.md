<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/MilindGaharwar/fettle/main/assets/wordmark-dark.svg">
    <img src="https://raw.githubusercontent.com/MilindGaharwar/fettle/main/assets/wordmark-light.svg" alt="Fettle" height="160">
  </picture>
</p>

<h3 align="center">Quality governance inside AI coding sessions</h3>

<p align="center"><b>The only quality system that catches issues while the AI agent still has context to fix them.</b></p>

<p align="center">
  <a href="https://pypi.org/project/finefettle/"><img src="https://img.shields.io/pypi/v/finefettle?label=PyPI&color=brightgreen" alt="PyPI"></a>
  <a href="https://github.com/MilindGaharWar/fettle/actions/workflows/ci.yml"><img src="https://github.com/MilindGaharWar/fettle/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/finefettle/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT license"></a>
  <a href="https://github.com/MilindGaharWar/fettle"><img src="https://img.shields.io/badge/tests-2100%2B-brightgreen" alt="2100+ tests"></a>
</p>

<p align="center">
  <a href="#installation">Installation</a> ·
  <a href="#why-fettle-exists">Why</a> ·
  <a href="#what-makes-fettle-unique">Unique Features</a> ·
  <a href="#capabilities">Capabilities</a> ·
  <a href="docs/README.md">Docs</a>
</p>

> **fettle** *(v.)* — a foundry term for trimming and cleaning a rough casting.

---

**AI agents can produce dozens of edits before commit hooks, CI, or PR reviewers see the results.** By then, the agent has moved on, lost context, and the feedback loop takes hours or days.

**Fettle changes this**. It hooks directly into your AI coding agent's tool lifecycle (Claude Code, Codex, Gemini CLI, OpenCode) and runs quality checks **in-session** — while the agent still knows what it was trying to do.

```text
agent edits code ──▶ Fettle checks immediately ──▶ agent repairs in same session
     │                                              instead of next commit/PR
     └── < 1 second                                 └── hours/days later
```

## Installation

### For Agent Session Governance

**Recommended**: Clone and run from the repository (agent hooks require integration assets not in the wheel):

```bash
git clone https://github.com/MilindGaharWar/fettle ~/projects/fettle
cd ~/projects/fettle
python3 fettle/cli.py init --install-tools
fettle doctor
```

This gives you:
- **Live agent hooks** that check code as your AI assistant writes it
- **Workflow commands** accessible from your agent (`/fettle:quality`, `/fettle:review`, etc.)
- **Immediate feedback** in the session where context exists

### For CI/CLI Automation

Install the wheel for deterministic batch operations:

```bash
pipx install finefettle
fettle check --changed
fettle verify
```

<details>
<summary><b>⚙️ pipx installation notes</b></summary>

The PyPI package is named `finefettle` (the `fettle` name is taken). The installed command is still `fettle`.

**Important**: When using pipx to install from a local clone, use:
```bash
pipx install --force /path/to/fettle  # Non-editable install
```

Editable installs (`pipx install -e .`) bypass the build step that bundles workflow commands, causing "no commands found" errors. Install from PyPI or use `--force` for non-editable installs.

</details>

## Why Fettle Exists

### The Problem

Most quality tools operate at repository boundaries:

| Check happens | When | Cost of fix |
|---|---|---|
| Editor/linter | While you type | Seconds |
| Commit hooks | After you finish | Minutes |
| CI/PR | After push | Hours to days |
| **Fettle** | **During generation** | **Seconds** |

**AI agents amplify this problem**. They can make 20 edits in seconds, but commit hooks, CI, and reviews still happen later. When a bug surfaces in CI, the agent has lost the context of *why* it wrote that code.

### The Solution

Fettle integrates directly with AI coding agent platforms:

- **Hooks into tool events** (Write, Edit, Bash) across Claude Code, Codex, Gemini, OpenCode
- **Runs configured checks** (lint, security patterns, process gates) before/after each tool call
- **Returns findings in-session** so the agent can immediately repair
- **Preserves evidence** in structured traces for audits and learning

**Result**: A broken pattern caught in-session costs one tool invocation to fix. The same issue in CI costs a context switch, investigation, and rework.

## What Makes Fettle Unique

### 1. **One Policy, Five Surfaces**

A single `.fettle.toml` governs all your development surfaces:

- **Claude Code** — hooks into tool lifecycle
- **Codex CLI** — PreToolUse/PostToolUse integration
- **Gemini CLI** — event stream integration
- **OpenCode** — native plugin transport
- **VS Code** — Python LSP diagnostics with same rules

**Write the rule once, enforce it everywhere** your team works.

### 2. **Findings Arrive In-Session**

When Fettle catches an issue:
1. The agent just made the edit (< 1 second ago)
2. The agent still knows the implementation intent
3. The agent can repair immediately in the same turn

Traditional approach:
1. Agent commits broken code
2. Hours later, CI fails
3. Developer context-switches to investigate
4. Agent re-learns the context to fix it

**Fettle cuts the loop from hours to seconds.**

### 3. **Zero-Dependency Runtime**

The entire engine is pure Python standard library:
- No transitive supply chain to audit
- Fast hook startup (< 50ms)
- No version conflicts with your project's dependencies
- Explicit tools (Ruff, Semgrep, golangci-lint) are optional and user-controlled

### 4. **Workspace-Aware Polyglot Support**

Fettle understands modern polyglot repositories:

- **Discovers nested workspaces** from native markers (`pyproject.toml`, `go.mod`, `Cargo.toml`, `package.json`)
- **Routes edits to the right workspace** using longest-prefix matching
- **Runs native tools per language**:
  - Python: Ruff + Semgrep
  - JavaScript/TypeScript: ESLint/Biome + Semgrep
  - Go: golangci-lint + Semgrep
  - Rust: Clippy
- **Tracks verification across all affected workspaces**

### 5. **Four-State Result Model**

Every check returns one of four explicit states:

- `pass` — clean result
- `violation` — findings detected
- `tool_error` — analysis tool missing/timed out
- `unknown` — check not applicable

**Missing tools cannot appear clean.** A degraded analysis is reported as degraded, not as a pass.

### 6. **Evidence-Based Learning**

```text
incident/failure ──▶ fettle learn ──▶ quarantined proposal
                                              │
                          human review ◀──────┘
                                │
                                ▼
                       promoted learned rule ──▶ catches future occurrences
```

- Rules are **drafted from real incidents** (not hypothetical patterns)
- Proposals stay **quarantined** until human promotion
- Every promoted rule carries its **origin evidence**
- False positives feed back into the learning loop

### 7. **Policy With Provenance**

Eight configuration layers resolve deterministically:

1. Built-in defaults
2. Organization pack
3. Team pack
4. Digest-pinned central policy
5. Repository `.fettle.toml`
6. Directory overrides
7. Environment variables
8. Delegation capsules

**Every value has a source**: `fettle config --explain` shows exactly which layer set each option.

### 8. **Delegation Without Policy Loss**

When an orchestrator spawns child agents:

1. Policy capsule travels with the child (digest-checked)
2. Child receives the full policy context
3. Child can tighten but never loosen policy
4. Completion report returns to orchestrator

**Governance survives delegation** without requiring centralized orchestration.

### 9. **Verifiable Claims**

- **2,100+ collected tests** covering adapters, gates, and integrations
- **SLSA build provenance** on every release
- **CycloneDX SBOM** for supply-chain transparency
- **PyPI Trusted Publishing** (no long-lived credentials)
- **No dependencies** in the runtime = minimal attack surface

The same evidence discipline Fettle asks of your sessions, it applies to itself.

## Capabilities

### In-Session Checks

| Category | Examples |
|---|---|
| **Code quality** | Post-edit lint routed to Python/JS/TS/Go/Rust workspaces |
| **Security** | Semgrep antipattern rules (SQL injection, unsafe deserialization, credential exposure) |
| **Shell safety** | Guards on destructive commands (`rm -rf /`, `DROP DATABASE`) |
| **Process gates** | Plan tracking, TDD ordering, complexity budgets, coverage gates |
| **Verification** | Impacted test discovery, affected-workspace test runs |

All checks:
- Support **per-call budgets** (timeout = degraded, not failure)
- Return **canonical four-state results** (no hidden errors)
- Default to **advisory mode** (non-blocking)

### Post-Edit Polyglot Lint

**Python:**
```bash
# After agent edits a .py file:
ruff check --output-format=json  # Fast lint
semgrep --config rules/python-antipatterns.yml  # Security patterns
```

**JavaScript/TypeScript:**
```bash
biome check --reporter=json  # Or ESLint
semgrep --config rules/ts-antipatterns.yml  # Fetch timeout, SQL string templates
```

**Go:**
```bash
golangci-lint run --out-format=line-number
semgrep --config rules/go-antipatterns.yml  # HTTP client timeout, SQL concat
```

**Rust:**
```bash
cargo clippy --message-format=short
```

### Workspace-Aware Verification

```bash
fettle verify           # Smart: changed files → impacted tests
fettle verify --full    # Full suite across all affected workspaces
```

- **Discovers workspaces** from native markers (no manual configuration)
- **Maps changed files to tests** (Python: name-based; other languages: full suite fallback)
- **Records per-workspace results** with command, exit code, duration
- **Handles deleted files** — still mapped to their former workspaces

### Guided Workflows

17 agent-invocable workflows bundled with Fettle:

```bash
fettle workflows install   # Install to all detected agents
fettle workflows list      # Show invocation syntax
```

| Category | Workflows |
|---|---|
| **Quality** | `/fettle:quality`, `/fettle:pr-review`, `/fettle:review` |
| **Security** | `/fettle:security-review`, `/fettle:threat-model`, `/fettle:ops-review` |
| **Planning** | `/fettle:plan-activate`, `/fettle:plan-complete`, `/fettle:worklog` |
| **Learning** | `/fettle:learn`, `/fettle:mcp-approve`, `/fettle:mcp-revoke` |
| **Operations** | `/fettle:preflight`, `/fettle:explain`, `/fettle:report`, `/fettle:baseline`, `/fettle:lean-debt` |

**Cross-platform invocation:**
- Claude Code, Gemini CLI: `/fettle:<name>`
- VS Code, OpenCode: `/fettle-<name>`
- Codex CLI: `/prompts:fettle-<name>`

### Session Reliability

For orchestrators and structured audit trails:

```bash
fettle plan start --title "Add export feature" --item "Write contract test"
fettle plan check "Write contract test"
fettle verify
fettle brief    # Structured session summary
fettle report --days 7 --lineage
```

### Delegation and Worktrees

```bash
fettle topology advise     # Analyze codebase structure
fettle topology apply      # Configure worktree setup
fettle spawn claude --task "Implement the approved item"
fettle brief --json        # Child returns structured state
```

Policy capsules preserve governance across delegation boundaries (digest-checked, capsule can only tighten policy).

## Daily Commands

```bash
fettle                          # Status dashboard
fettle check --changed          # Lint changed Python files (CLI mode)
fettle verify                   # Run impacted tests across workspaces
fettle config --validate        # Check .fettle.toml
fettle doctor --fix             # Verify environment
fettle explain                  # Recent gate decisions with evidence
fettle report --days 7          # Session history
fettle ratchet show             # Quality trend data
```

All subcommands support `--help`:

```bash
fettle --help
fettle verify --help
```

## Configuration

`.fettle.toml` in your repository root:

```toml
[gates.lint]
enabled = true
mode = "advisory"       # advisory | soft | enforce

[gates.plan]
enabled = false         # Require active plans in session
threshold = 3

[gates.tdd]
enabled = false         # Warn on impl-before-test
mode = "advisory"

[gates.verification]
enabled = true
mode = "advisory"
scope = "impacted"      # impacted | full
```

**Advisory by default** — promote individual gates after measuring signal/noise in your workflow.

Policy resolves through **layered sources** with full provenance:

```bash
fettle config --explain
```

See [docs/CONFIG.md](docs/CONFIG.md) for all options, precedence rules, environment variables, and policy layering.

## Enterprise & Governance

For teams and organizations:

- **Central policy distribution** via digest-pinned `[extends]`
- **Append-only JSONL traces** for audit/compliance
- **Organization/lineage reports** with structured output
- **SARIF + JUnit** for existing CI dashboards
- **Opt-in aggregate telemetry** controlled by central policy
- **JSON Schema validation** for `.fettle.toml`

**Note**: Each surface (CLI, hooks, CI, editor) supports different check subsets. Validate the exact surface you plan to enforce.

## Operational Boundaries

| Boundary | Details |
|---|---|
| **Python version** | 3.11+ required |
| **Agent integrations** | Require repository checkout (hooks, transports not in wheel) |
| **Language support** | Python lint richest; JS/TS/Go/Rust depend on external tools |
| **VS Code/LSP** | Current path analyzes Python only |
| **External tools** | Ruff, Semgrep, golangci-lint, clippy, test runners are optional/user-installed |
| **Default mode** | Advisory (non-blocking) for opinionated gates |
| **Error handling** | Hooks favor continuity; tool failures reported as degraded, not clean |
| **CI role** | Independent fail-closed boundary; Fettle is earlier control point |

## Evidence

- **Test coverage**: 2,100+ collected tests
- **Build provenance**: SLSA on every release
- **Supply chain**: CycloneDX SBOM
- **Publishing**: PyPI Trusted Publishing (no long-lived credentials)
- **Dependencies**: Zero in runtime (Python stdlib only)

## Documentation

| Need | Resource |
|---|---|
| Next steps | [Documentation index](docs/README.md) |
| Configuration reference | [docs/CONFIG.md](docs/CONFIG.md) |
| OpenCode setup | [docs/OPENCODE.md](docs/OPENCODE.md) |
| Behavioral evaluations | [evals/README.md](evals/README.md) |
| Roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Security | [SECURITY.md](SECURITY.md) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, change verification, and pull request expectations.

**Security vulnerabilities**: Report via [SECURITY.md](SECURITY.md), not public issues.

## License

MIT © Milind
