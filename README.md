# Fettle

> **fettle** *(v.)* — to trim and clean a rough casting fresh from the mold.
> *"In fine fettle"* — in excellent condition.

Quality enforcement for AI-assisted development. Fettle intercepts code
mutations made by Claude Code or OpenCode, runs static analysis in real time, and surfaces
findings before they reach production — ruff linting, semgrep pattern matching,
and **incident-derived LLM-antipattern rules** layered into a defense model that
catches issues at the point of creation rather than in code review.

**Status: v1.0.0** — enterprise integration + SWEBOK v4 coverage. Full
engineering discipline enforcement with external tool adapters (SonarQube,
Black Duck, Pact), security review, threat modeling, deployment safety,
technical debt quantification, mutation testing, and requirements traceability.

## What It Does

| Layer | Hook | What runs |
|-------|------|-----------|
| **Per-edit lint** | PostToolUse (Write/Edit) | ruff + semgrep on every Python edit |
| **TDD ordering** | PreToolUse + PostToolUse | Test-before-implementation enforcement (v0.9) |
| **Complexity** | PostToolUse (Write/Edit) | Cyclomatic + cognitive per modified function (v0.9) |
| **Lean review** | PostToolUse (Write/Edit) | Over-engineering detection: abstractions, wrappers, large additions (v0.8) |
| **Pre-write gate** | PreToolUse (Write/Edit) | Plan gate, config protection, UX spec gate |
| **MCP trust** | PreToolUse (Bash) | Package install allowlist |
| **Artifact integrity** | PreToolUse (Bash) | Destructive command guard |
| **Doc freshness** | PostToolUse (Bash) | Warns if implementation changed but no docs updated |
| **Bash audit** | PostToolUse (Bash) | Structured event logging, privacy-first (v0.8) |
| **Cross-file** | Stop | Import/contract resolution before response delivery |
| **Coverage gate** | Stop | Diff line + branch coverage from coverage.json (v0.8/v0.9) |
| **Discipline link** | PostToolUse | Injects skill reminders when loop/scope/lean gates fire (v0.8) |

## Intelligence Layer (v0.3.0+)

| Feature | Command | Description |
|---------|---------|-------------|
| **Learn** | `/fettle:learn` | Incident text → LLM-generated semgrep rule + fixtures + citation |
| **Explain** | `/fettle:explain` | Why did the last hook block? Human-readable trace |
| **Baseline** | `/fettle:baseline` | Snapshot violations for incremental adoption |
| **Report** | `/fettle:report` | Effectiveness metrics (pass/violation rates, top violations) |

## Rules Catalog (semgrep)

| Rule | Severity | Catches |
|------|----------|---------|
| `regex-llm-output` | ERROR | Regex-parsing LLM output instead of structured tool use |
| `bare-except-swallow` | ERROR | `except: pass` swallowing all errors |
| `broad-except-no-reraise` | ERROR | `except Exception` without re-raise or logging |
| `missing-httpx-timeout` | ERROR | httpx clients without timeouts |
| `sql-fstring` | ERROR | SQL built with f-strings (injection) |
| `health-score-inversion` | ERROR | Health checks returning perfect on no data |
| `orphaned-queue-flag` | ERROR | Queue writes with no verified consumer |
| `datetime-now-pipeline` | WARNING | `datetime.now()` in pipeline code (breaks backfill) |
| `non-atomic-write-output` | WARNING | Non-atomic writes in pipeline output paths |

Plus ruff: `BLE001`, `S110`, `S608`, `S701` as errors; `SIM*`, `UP*` as warnings.

## Installation

```bash
# Clone to your projects folder
git clone https://github.com/MilindGaharwar/fettle ~/projects/fettle

# Symlink into Claude Code plugins (hooks require this path)
ln -s ~/projects/fettle ~/.claude/plugins/fettle

# Install tools
uv tool install ruff
uv tool install semgrep   # optional

# Verify
bash ~/.claude/plugins/fettle/scripts/run.sh doctor.py
```

Hooks auto-activate via `hooks/hooks.json` when symlinked in `~/.claude/plugins/`.
For OpenCode, register the adapter as described in
[docs/OPENCODE.md](docs/OPENCODE.md).

The `fettle` name on PyPI belongs to an unrelated project. Install this Fettle
CLI from GitHub instead:

```bash
pip install "git+https://github.com/MilindGaharwar/fettle.git@main"
fettle doctor
```

## CLI

```bash
fettle check [--all] [--changed] [--json] [--fix] [--baseline]
fettle config --print-effective
fettle config --explain
fettle explain [--last N]
fettle baseline create|update
fettle doctor
fettle lsp
```

## GitHub Actions

Use the composite Action at the same ref as your workflow:

```yaml
- uses: MilindGaharwar/fettle@main
  with:
    mode: advisory
```

For centralized adoption, call
`.github/workflows/fettle-reusable.yml`; both surfaces support SARIF and pull
request annotations. Pin a release tag instead of `main` for stable CI.

## Slash Commands (12)

| Command | Purpose |
|---------|---------|
| `/fettle:quality` | Full project scan |
| `/fettle:preflight` | Pre-deployment FMEA checklist |
| `/fettle:ops-review` | Operational readiness review |
| `/fettle:plan-activate` | Start a plan (required before edits in enforce mode) |
| `/fettle:plan-complete` | Mark plan done |
| `/fettle:mcp-approve` | Approve an MCP package |
| `/fettle:mcp-revoke` | Revoke MCP package trust |
| `/fettle:learn` | Generate rule from incident |
| `/fettle:explain` | Explain last hook decision |
| `/fettle:baseline` | Manage violation baselines |
| `/fettle:report` | Effectiveness metrics |

## Configuration

`.fettle.toml` at project root. Full reference: [docs/CONFIG.md](docs/CONFIG.md).

```toml
[gates.lint]
enabled = true
mode = "advisory"   # advisory | soft | enforce

[gates.lean_review]
mode = "advisory"   # silent | advisory — surfaces over-engineering findings (v0.8)

[gates.complexity]
enabled = true
max_cyclomatic = 10
max_cognitive = 15

[gates.coverage]
enabled = false
threshold = 80                  # Line coverage % for changed lines
minimum_branch_percent = 0      # Branch coverage (0 = disabled)

[gates.tdd]
enabled = false
mode = "advisory"               # advisory only in v0.9
accept_preexisting_tests = true

[gates.plan]
enabled = false
threshold = 3                   # Files changed before plan required
risk_paths = []                 # Globs that auto-require plan (e.g. "**/auth/**")
module_threshold = null         # Distinct packages, null = disabled
line_threshold = null           # Added lines, null = disabled

[gates.bash_audit]
enabled = false                 # Privacy-first: opt-in only
capture_command = false         # If true, applies redaction before logging

[gates.advisory]
cooldown_seconds = 300
max_per_turn = 3

[gates.discipline_link]
enabled = true
cooldown_seconds = 300

[severity]
error_rules = ["BLE001", "S110", "S608", "S701"]
warning_prefixes = ["SIM", "UP"]
```

## Architecture

```
Claude Code Tool Call
    │
    ▼
PreToolUse ──→ dispatcher.py selects checks by event + tool + extension:
             → quality_gate (plan, UX spec)
             → tdd_gate (test-first ordering)
             → config_protect, destructive_guard
             → mcp_trust_gate (Bash only)
    │
    ▼ (tool executes)
    │
PostToolUse ──→ dispatcher.py:
              → post_edit (ruff + semgrep on .py)
              → post_edit_ts, post_edit_go (language-specific)
              → complexity_check (cyclomatic + cognitive)
              → lean_sniffers (over-engineering detection)
              → bash_audit (structured event logging)
              → tdd_gate (records test/impl edits)
              → loop_detect + scope_creep + discipline_link
    │
    ▼
Stop ──→ dispatcher.py:
       → quality_gate (test freshness)
       → stop_quality_gate (imports + cargo check)
       → coverage_gate (line + branch coverage)
```

All checks route through `dispatcher.py` (single process, per-check budget,
advisory cap). 17 checks registered, ordered by priority, fail-open on error.

## Result Taxonomy

Every hook returns one of:

| Status | Meaning | User action |
|--------|---------|-------------|
| `PASS` | No issues | None |
| `VIOLATION` | Code quality issue | Fix the code |
| `TOOL_ERROR` | ruff/semgrep missing or crashed | Run `fettle doctor` |
| `CONFIG_ERROR` | Invalid .fettle.toml | Fix config |
| `SKIPPED` | File not in scope | None |

## Key Design Principles

1. **Advisory by default** — opinionated gates default off; lint is advisory; every block names its disable key
2. **Fail visible** — tool crashes surface as warnings, never as silent passes
3. **Rules carry receipts** — every rule has origin + citation; `/fettle:learn` rules cite their incident
4. **Single config source** — `.fettle.toml`, no scattered env vars
5. **No shared global state** — per-session state dirs

## Extensibility

### Checker Protocol (`scripts/checker.py`)

```python
class Checker(ABC):
    name: str
    file_extensions: set[str]
    def is_available(self) -> AvailabilityResult: ...
    def check(self, context: CheckContext) -> list[Finding]: ...
    def can_fix(self) -> bool: ...
```

Built-in: `RuffChecker`, `SemgrepChecker`. Register custom: `register_checker(MyChecker())`.

### Policy Engine (`scripts/policy.py`)

```python
decision = evaluate_policy("PostToolUse", "src/app.py", config)
# → PolicyDecision(should_check=True, checkers=['ruff', 'semgrep'], block_on_error=False)
```

### Event Model (`scripts/event.py`)

```python
event = FettleEvent.from_stdin(HookType.POST_TOOL_USE)
# → typed, normalized: event.is_python, event.file_extension, event.repo_root
```

### Result Caching (`scripts/cache.py`)

Cache key = file content hash + config hash. Skips re-scanning unchanged files.

## Testing

```bash
cd ~/.claude/plugins/fettle
.venv/bin/python -m pytest tests/ -q
```

**939 tests** across 117 test files covering all checks, adapters, and
infrastructure. All adapter tests use mocked tool outputs — no eslint, biome,
tsc, cargo, or semgrep installation required to run the suite.

## Roadmap

| Version | Theme | Status |
|---------|-------|--------|
| v0.2.0 | Core lint gates | **Shipped** |
| v0.3.0 | Process gates + intelligence foundation | **Shipped** |
| v0.4.0 | TS/JS rules, cross-review, SARIF, caching, autofix, checker protocol | **Shipped** |
| v0.5.0 | Adaptive enforcement platform | **Shipped** |
| v0.6.0 | Trust and precision | **Shipped** |
| v0.7.0 | Action, LSP, policy layering, OpenCode adapter | **Shipped** |
| v0.8.0 | Discipline integration (advisory contract, link pilot, budget, audit, coverage) | **Shipped** |
| v0.9.0 | Engineering discipline enforcement (branch coverage, complexity, plan thresholds, TDD) | **Shipped** |

See [docs/ROADMAP.md](docs/ROADMAP.md) for remaining governance and
distribution work.

## License

MIT (c) Milind Gaharwar
