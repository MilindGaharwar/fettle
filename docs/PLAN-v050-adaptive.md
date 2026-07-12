# Fettle v0.5.0 — Adaptive Quality Enforcement

> Make Fettle dynamically adapt to any project, any stack. Catch CI failures locally before push.

## Problem Statement

CI pipelines fail after push, but failures aren't caught locally. Fettle checks syntax and imports but doesn't replicate what CI actually runs. The AI assistant edits, commits, pushes — and moves on without noticing the failure.

## Design Principles

1. **Profile-driven** — detect the stack, don't hardcode assumptions
2. **Tiered enforcement** — fast (10s) for hooks, changed (60s) for pre-push, full (5min) for pre-PR
3. **Wrap, don't reinvent** — use existing tools (pytest-testmon, deptry, pyright, gitleaks)
4. **CI parity via shared commands** — make local and CI run the same commands, not by parsing workflows
5. **Learn from real failures** — ingest CI results, classify, adapt gates
6. **AI-optimized output** — location + explanation + fix + re-run command

## Tiered Check Commands

```bash
fettle check --fast       # 5-15s, safe for hooks/Claude Code
fettle check --changed    # 30-90s, good for pre-push
fettle check --full       # local full validation
fettle check --ci         # closest known equivalent to CI
fettle ci diagnose        # explain last CI failure
fettle ci compare         # local-vs-CI coverage gap
```

| Tier | Budget | Runs | Trigger |
|------|--------|------|---------|
| fast | 5-15s | lint, format, deps, secrets, entry points | PostToolUse hook, pre-commit |
| changed | 30-90s | fast + targeted tests + type check | pre-push |
| full | 5min | full test suite + build + package | manual, pre-PR |
| ci | varies | same commands as CI workflow | explicit |

## Build Phases

### Phase 1: Foundation — Project Profile

Auto-detect stack by reading marker files. Cache in `.fettle/profile.json`.

**Detection sources:**
- `pyproject.toml` / `setup.py` → Python + pip/uv
- `package.json` → Node + npm/pnpm/yarn
- `Cargo.toml` → Rust + cargo
- `go.mod` → Go
- `Makefile` / `justfile` → Custom commands
- `.github/workflows/*.yml` → CI awareness (not emulation)
- Tool configs: `pyrightconfig.json`, `.eslintrc`, `rustfmt.toml`

**Profile schema:**
```json
{
  "languages": ["python"],
  "workspaces": [
    {
      "path": ".",
      "language": "python",
      "manager": "pip",
      "test_command": "python -m pytest tests/ -q",
      "lint_command": "ruff check .",
      "format_command": "ruff format --check .",
      "typecheck_command": "pyright",
      "build_command": "pip install -e .",
      "dependency_file": "pyproject.toml",
      "lockfile": null,
      "entry_points": {"acumen": "acumen.cli:main"},
      "source_roots": ["src/"],
      "test_roots": ["tests/"]
    }
  ],
  "ci": {
    "provider": "github_actions",
    "commands_detected": ["pip install -e .[dev]", "pytest"]
  }
}
```

**Invalidation:** Re-detect when marker files change (pyproject.toml, package.json, etc.)

**Deliverables:**
- `scripts/profile.py` — detection + caching
- `scripts/profile_python.py` — Python adapter
- Tests for detection logic

---

### Phase 2: Tiered Check Runner

Replace the current "run everything always" with tiered execution.

**Deliverables:**
- `fettle check --fast` / `--changed` / `--full` / `--ci`
- Policy config in `.fettle.toml`:
```toml
[policy.fast]
timeout_seconds = 15
checks = ["lint", "format", "secrets", "dependency-imports", "entry-points"]

[policy.changed]
timeout_seconds = 90
checks = ["fast", "typecheck", "targeted-tests"]

[policy.full]
timeout_seconds = 300
checks = ["changed", "full-tests", "build"]
```
- Hook integration: PostToolUse runs `--fast`, pre-push gate runs `--changed`

---

### Phase 3: Quick-Win Checkers

New checkers that use existing tools with high signal-to-noise.

| Checker | Tool to wrap | What it catches |
|---------|-------------|----------------|
| Dependency validation | `deptry` / stdlib list | Undeclared imports |
| Format check | `ruff format --check` | Formatting drift |
| Entry point wiring | custom (resolve module:func) | Broken console scripts |
| Secret scanning | `gitleaks` | Accidental credentials |
| Install check | `pip install -e .` | Broken package config |

**Deliverables:**
- `scripts/checkers/dependency.py`
- `scripts/checkers/format.py`
- `scripts/checkers/entry_points.py`
- `scripts/checkers/secrets.py`
- `scripts/checkers/install.py`

---

### Phase 4: Type Checking + Targeted Tests

| Checker | Tool | Notes |
|---------|------|-------|
| Type check | `pyright` (or `mypy`) | Incremental, changed files + dependents |
| Targeted tests | `pytest-testmon` or `pytest --picked` | Only tests covering changed code |
| Last-failed | `pytest --lf` | Re-run failures first |

**Targeted test strategy:**
1. Direct test file changed → run it (high confidence)
2. Source file mapped by testmon/coverage → run mapped tests (medium confidence)
3. No known covering tests → warn, defer to full suite
4. Config/lockfile changed → force full suite

**Deliverables:**
- `scripts/checkers/typecheck.py`
- `scripts/checkers/targeted_tests.py`
- Integration with `pytest-testmon` / `pytest-picked`

---

### Phase 5: CI Failure Ingestion Loop

**The biggest missing piece.** Read actual CI failures and learn from them.

```bash
fettle ci diagnose              # explain last CI failure
fettle ci compare               # local-vs-CI coverage gap
fettle ci learn <run-id>        # generate checker from failure
```

**How:**
- Use `gh run list --status failure` + `gh run view --log-failed`
- Classify failure: lint | type | test | dependency | build | env | flaky
- Check if local Fettle would have caught it
- If not → suggest adding the check
- Store in `.fettle/ci-history.jsonl`

**Deliverables:**
- `scripts/ci_ingest.py`
- `scripts/ci_diagnose.py`
- CI-history storage + classification

---

### Phase 6: Polyglot Adapters

Add language adapters one at a time. Each implements:

```python
class LanguageAdapter(ABC):
    def detect(self, repo_root: str) -> bool: ...
    def lint(self, mode: str, files: list[str]) -> list[Finding]: ...
    def format_check(self, mode: str, files: list[str]) -> list[Finding]: ...
    def typecheck(self, mode: str, files: list[str]) -> list[Finding]: ...
    def test(self, mode: str, files: list[str]) -> list[Finding]: ...
    def build(self, mode: str) -> list[Finding]: ...
    def dependency_check(self, files: list[str]) -> list[Finding]: ...
```

**Priority order:**
1. Python (already partially done)
2. TypeScript/JavaScript
3. Rust
4. Go

---

### Phase 7: Advanced Features (Future)

- **Generated code drift** — detect stale protobuf/migration/OpenAPI artifacts
- **Database migration checks** — `alembic check`, `makemigrations --check`
- **Workspace/monorepo support** — route checks to affected workspace only
- **Health dashboard** — trend metrics, quality drift detection
- **Remote preflight** — trigger CI on temp branch before push
- **SARIF/JUnit normalization** — unified result format

---

## AI-Agent Output Format

Every failure must be actionable:

```
FAIL [checker]: path/to/file.py:42
  Error description in plain language.

  Suggested fix:
    - Specific action to take

  Re-run:
    ruff check path/to/file.py
```

---

## Configuration

```toml
# .fettle.toml additions for v0.5.0

[profile]
auto_detect = true          # Auto-detect stack (default: true)
cache_ttl_hours = 24        # Re-detect after this long

[policy.fast]
timeout_seconds = 15
block_on = ["lint", "format", "secrets", "dependency-imports"]
warn_on = ["tests-skipped", "coverage-gap"]

[policy.changed]
timeout_seconds = 90
block_on = ["lint", "format", "typecheck", "targeted-tests", "dependency-imports"]

[policy.full]
timeout_seconds = 300
block_on = ["all"]

[commands]
# Override auto-detected commands
test = "python -m pytest tests/ -q"
lint = "ruff check ."
format = "ruff format --check ."
typecheck = "pyright"
build = "pip install -e ."

[ci]
provider = "github_actions"
# Commands CI runs that Fettle should replicate locally
replicate = ["pip install -e .[dev]", "pytest", "ruff check ."]
```

---

## Success Criteria

1. **Zero surprise CI failures** for lint, format, type, dependency, and targeted test issues
2. **Sub-15s feedback** on every code edit via hooks
3. **Works on any Python project** without manual configuration
4. **Extensible to other stacks** via adapter protocol
5. **CI feedback loop** learns from failures and suggests new gates

---

## Anti-Goals

- NOT a GitHub Actions emulator
- NOT a full test runner (we delegate to pytest/vitest/cargo test)
- NOT a CI replacement (we complement CI, not duplicate it)
- NOT a dashboard-first product (checks first, metrics later)

---

## References

- GPT 5.5 review (2026-07-12): validated proposals, identified CI failure ingestion as biggest gap
- Existing Fettle architecture: Checker protocol, policy engine, event model, cache
- Off-the-shelf tools to integrate: deptry, pytest-testmon, pyright, gitleaks, actionlint
