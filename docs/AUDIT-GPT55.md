# Fettle Audit — GPT 5.5 (2026-07-07)

Independent code audit conducted by GPT 5.5.

---

## 1. Top 5 Bugs / Code Quality Issues

### 1. Hook exit semantics are fragile
- Nonzero exit codes from ruff/semgrep not distinguished from tool crashes
- Fix: Normalize results into explicit categories: PASS, POLICY_VIOLATION, TOOL_ERROR, CONFIG_ERROR, SKIPPED

### 2. Path handling security risk
- Hook payloads may contain `../`, symlinks, spaces
- Paths may resolve differently when CWD differs
- Fix: Centralize path resolution — canonicalize, reject outside repo root, handle symlinks

### 3. `run.sh` can hide failures
- Different behavior under bash/zsh/dash
- Missing interpreter reported as policy failure
- Fix: Keep run.sh minimal (find root → find interpreter → exec). All logic in Python.

### 4. ruff/semgrep failures conflated
- Code violation vs tool not installed vs tool crash all look the same to user
- Fix: Separate diagnostic categories with distinct messages

### 5. Configuration precedence unclear
- No documentation of: defaults < user < project < env < CLI
- No way to see effective merged config
- Fix: `fettle config --print-effective` command

---

## 2. Top 5 Improvements / Enhancements

### 1. Explain mode
```bash
fettle explain --last   # Why did Fettle block? Which hook, which files, which rules?
```

### 2. Baseline support
```bash
fettle baseline create   # Snapshot existing violations
fettle check --baseline  # Only report NEW violations
```
Critical for legacy repo adoption.

### 3. Autofix support
```toml
[tools.ruff]
fix = "safe"   # none | safe | aggressive
```
Run `ruff --fix` on PostToolUse for safe fixes.

### 4. Structured JSON output
```bash
fettle check --json   # Machine-readable findings
```
Enables CI, dashboards, editor integrations.

### 5. CI mode
```bash
fettle check --all        # Full project scan (no hook context needed)
fettle check --changed    # Only changed files
fettle install-hooks      # One-command setup
```

---

## 3. Top 5 Architecture Changes

### 1. Formal tool/plugin interface
```python
class Checker:
    name: str
    def is_available(self) -> AvailabilityResult: ...
    def select_files(self, context: CheckContext) -> list[Path]: ...
    def run(self, context: CheckContext) -> CheckResult: ...
```
Enables: mypy, pyright, eslint, bandit, gitleaks, shellcheck, custom checks.

### 2. Separate hook parsing from enforcement
```
Claude hook adapter → Event model → Policy engine → Checker registry → Reporter
```
Supports Claude hooks, CLI, CI, editors without duplicating logic.

### 3. Typed internal event model
```python
@dataclass
class FettleEvent:
    hook: HookType
    tool_name: str | None
    changed_files: list[Path]
    repo_root: Path
    raw_payload: dict
```
Easier testing, safer paths, resilient to Claude payload changes.

### 4. Policy engine
```toml
[policy.failures]
ruff = "block"
semgrep = "block"
missing_tool = "warn"
config_error = "block"
```
Central decision point: what runs, what blocks, what warns.

### 5. Standardized results + reporters
```python
@dataclass
class Finding:
    tool: str
    severity: Severity
    path: Path | None
    line: int | None
    code: str | None
    message: str
    fixable: bool = False
```
Output as: text, JSON, SARIF, GitHub Actions annotations.

---

## 4. Prioritized TODO

### HIGH

| # | Item | Why |
|---|------|-----|
| H1 | Harden hook payload parsing (validate JSON, handle missing fields, debug logging) | Hooks break silently |
| H2 | Centralize path normalization + repo boundary check | Security + correctness |
| H3 | Distinguish violations from infrastructure failures | User trust |
| H4 | Comprehensive hook behavior tests (empty, unsupported, non-Python, missing tools) | Core product surface |
| H5 | `fettle doctor` (version, config, tools, hooks, permissions) | Reduces support friction |

### MEDIUM

| # | Item |
|---|------|
| M1 | Effective config printing (`fettle config --print-effective`) |
| M2 | Checker abstraction (ruff + semgrep as interface implementations) |
| M3 | JSON output mode |
| M4 | Baseline mode (snapshot + incremental) |
| M5 | CI-friendly check command (no hook context needed) |

### LOW

| # | Item |
|---|------|
| L1 | Autofix (safe ruff fixes only) |
| L2 | SARIF output (GitHub code scanning) |
| L3 | Rule-level suppression with reason + expiry |
| L4 | Result caching (by file hash + tool version) |
| L5 | Install UX (`fettle install-hooks`, upgrade, uninstall) |

---

## Summary

**Biggest risks:** hook parsing, path safety, exit-code semantics, conflating tool failures with code violations.

**Most valuable enhancements:** doctor mode, CI mode, JSON output, baselines, autofix.

**Architecture direction:** clean separation between Claude hook adapters, policy engine, checker plugins, and standardized result/reporting layers.
