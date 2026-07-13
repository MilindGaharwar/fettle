# Fettle v0.5.0 Work Packages — Adaptive Quality Enforcement

> Restructured based on GPT 5.5 review (2026-07-12). Addresses: foundational gaps moved early, oversized WPs split, adapter protocol ahead of checkers, result schema before output.

## Summary

| Phase | WPs | Theme | Goal |
|-------|-----|-------|------|
| 1 | 67–73 | Core platform | Stable foundation all checkers share |
| 2 | 74–77 | Runner + hooks | `fettle check --fast/--changed/--full/--ci` works |
| 3 | 78–85 | Python-first checks | Strong Python vertical slice |
| 4 | 86–89 | Targeted tests + confidence | Changed-tier is useful and safe |
| 5 | 90–93 | CI feedback loop | Local-vs-CI parity |
| 6 | 94–97 | Polyglot adapters | TypeScript, Rust, Go |
| 7 | 98–103 | Advanced | Generated code, migrations, dashboard |
| 8 | 104–114 | Pre-generation + agent guardrails | Shape what gets written; block destructive patterns; catch debug/scope drift |
| **Total** | **48 WPs** | | |

Platform: macOS + Linux. Windows explicitly not targeted in v0.5.0.

---

## Phase 1: Core Platform (WP-67 → WP-73)

### WP-67 — Project profile detector

Auto-detect project stack from marker files. Cache in `.fettle/profile.json`.

**Detection matrix:**

| Marker | Language | Manager |
|--------|----------|---------|
| `pyproject.toml` | Python | pip/uv/poetry/pdm |
| `package.json` | JS/TS | npm/pnpm/yarn |
| `Cargo.toml` | Rust | cargo |
| `go.mod` | Go | go |

**Deliverables:**
- `scripts/profile.py` — detection + caching + invalidation
- Marker precedence rules (e.g., `pyproject.toml` + `setup.py` = Python/pip)
- Confidence levels (high/medium/low) per detection
- `fettle profile` CLI command
- Cache invalidation on marker mtime/content-hash change

**TDD contracts:**
```
test_detects_python_from_pyproject_toml
test_detects_python_from_setup_py
test_detects_node_from_package_json
test_detects_rust_from_cargo_toml
test_detects_go_from_go_mod
test_detects_polyglot_repo
test_conflicting_markers_resolved_by_precedence
test_no_markers_returns_empty_profile
test_cache_invalidation_on_marker_change
test_does_not_walk_outside_repo_root
test_custom_commands_from_fettle_toml_override
```

---

### WP-68 — Workspace / monorepo awareness

Detect multiple workspaces within one repo. Route checks by changed-file path.

**Deliverables:**
- Workspace discovery (nested markers, pnpm workspaces, cargo workspaces)
- Changed-file → workspace routing
- Shared-file expansion (lockfiles, CI config, migrations broaden scope)

**TDD contracts:**
```
test_detects_multiple_workspaces
test_routes_backend_file_to_python_workspace
test_routes_frontend_file_to_node_workspace
test_shared_lockfile_triggers_all_workspaces
test_root_only_repo_is_single_workspace
test_nested_pyproject_not_confused_with_root
test_pnpm_workspace_packages_detected
test_cargo_workspace_members_detected
test_deleted_file_routes_correctly
test_file_outside_all_workspaces_handled
```

---

### WP-69 — Structured finding / result schema

Define the canonical format all checkers emit. Every downstream consumer (runner, hooks, CI comparison, dashboard) reads this schema.

**Schema fields:**
- `id`, `checker`, `severity` (error/warning/info)
- `blocking` (bool), `confidence` (high/medium/low)
- `file`, `line`, `column`, `workspace`
- `message`, `suggested_fix`, `rerun_command`
- `raw_tool_output` (truncated), `redacted` (bool)

**Deliverables:**
- `scripts/finding.py` — Finding dataclass + serialization
- JSON output mode + human-readable mode
- Deterministic sorting (file, line, severity)
- Redaction support (secrets never printed)
- SARIF export option
- Golden-file output tests

**TDD contracts:**
```
test_finding_serializes_to_json
test_finding_serializes_to_human_readable
test_findings_sorted_deterministically
test_secret_values_redacted_in_output
test_long_output_truncated
test_multiple_workspaces_grouped
test_sarif_export_valid
test_schema_version_included
test_empty_findings_produces_clean_output
```

---

### WP-70 — Tool execution abstraction

Common subprocess runner all checkers use. Handles timeouts, env, redaction, platform.

**Deliverables:**
- `scripts/tool_runner.py`
- Subprocess with timeout enforcement
- Working directory management (per-workspace)
- Environment variable passthrough + redaction
- Output capture (stdout/stderr split)
- Tool-missing detection (clean advisory finding, not crash)
- Fake executor for deterministic tests

**TDD contracts:**
```
test_runs_command_and_captures_output
test_timeout_kills_process_cleanly
test_timeout_produces_structured_finding
test_missing_tool_produces_advisory
test_working_directory_set_correctly
test_env_vars_passed_through
test_secret_env_vars_redacted_in_logs
test_fake_executor_for_testing
test_nonzero_exit_handled
test_binary_output_handled
```

---

### WP-71 — Git change-set detection

Robust source of truth for "what changed" — drives --changed tier and workspace routing.

**Deliverables:**
- `scripts/changeset.py`
- Modes: unstaged, staged, vs-base-branch (merge-base), vs-HEAD~1
- Handles: renames, deletes, untracked, ignored
- Returns: list of `ChangedFile(path, status, workspace)`

**TDD contracts:**
```
test_detects_staged_changes
test_detects_unstaged_changes
test_detects_untracked_files
test_merge_base_diff_against_main
test_renamed_files_tracked
test_deleted_files_included
test_ignored_files_excluded
test_routes_changed_files_to_workspaces
test_no_git_repo_handled_gracefully
test_empty_diff_returns_empty_list
```

---

### WP-72 — Tool / runtime discovery

Detect available tools, runtime versions, and lockfile status. Foundational for all checkers.

**Deliverables:**
- `scripts/environment.py`
- Runtime detection: Python version, Node version, Rust toolchain, Go version
- Tool detection: ruff, pyright, eslint, cargo, gitleaks, etc.
- Lockfile sync check: `uv.lock`, `pnpm-lock.yaml`, `Cargo.lock`
- Version file detection: `.python-version`, `.node-version`, `.tool-versions`
- Local vs CI version mismatch detection

**TDD contracts:**
```
test_detects_python_version
test_detects_node_version
test_detects_missing_tool
test_detects_lockfile_out_of_sync
test_reads_python_version_file
test_reads_node_version_file
test_compares_local_vs_ci_version
test_tool_discovery_prefers_workspace_local
test_unsupported_runtime_handled
test_reports_advisory_on_mismatch
```

---

### WP-73 — Configuration and enforcement policy

Unified config system for all gates, checkers, and tiers.

**Deliverables:**
- Extend existing `.fettle.toml` with:
  - `[policy.fast]`, `[policy.changed]`, `[policy.full]`, `[policy.ci]`
  - `[checks.<name>]` — enable/disable, severity, timeout per checker
  - `[suppressions]` — path patterns, inline markers, expiry
  - `[exclude]` — generated dirs, vendor, node_modules, .venv, target
- Config layering: defaults → repo `.fettle.toml` → workspace override → CLI flags
- Invalid config → clear error finding

**TDD contracts:**
```
test_default_config_works_with_no_file
test_repo_config_overrides_defaults
test_workspace_config_overrides_repo
test_cli_flags_override_config
test_invalid_config_produces_clear_error
test_policy_controls_blocking_advisory
test_suppression_excludes_finding
test_suppression_with_expiry_re_enables
test_exclude_patterns_skip_files
test_unknown_checker_in_config_warned
```

---

## Phase 2: Runner + Hooks (WP-74 → WP-77)

### WP-74 — Check runner core

Orchestrates checkers with timeout, result aggregation, and exit codes.

**Deliverables:**
- `scripts/check_runner.py`
- Checker registration + discovery
- Sequential/parallel execution within tier budget
- Timeout enforcement (per-checker and per-tier)
- Result aggregation → structured output
- Exit codes: 0=pass, 1=warnings, 2=blocking

**TDD contracts:**
```
test_runs_registered_checkers
test_aggregates_findings_from_multiple_checkers
test_per_checker_timeout_enforced
test_tier_budget_enforced
test_timed_out_checker_reported_as_deferred
test_exit_code_0_on_pass
test_exit_code_1_on_warnings_only
test_exit_code_2_on_blocking_findings
test_checker_crash_produces_tool_error_finding
test_empty_checker_list_passes
```

---

### WP-75 — Tier policy and routing

Define fast/changed/full/ci tiers. Route checkers by tier and changed files.

**Deliverables:**
- `fettle check --fast` / `--changed` / `--full` / `--ci`
- Tier→checker mapping from policy config
- Changed-file scoping (passes only relevant files to checkers)
- Full tier runs all checks on all files
- CI tier runs commands from profile

**TDD contracts:**
```
test_fast_tier_runs_only_configured_checkers
test_changed_tier_scopes_to_changed_files
test_full_tier_runs_all_checkers_all_files
test_ci_tier_runs_profile_commands
test_unknown_tier_errors_clearly
test_checker_receives_only_relevant_files
test_no_changed_files_skips_changed_tier
test_workspace_routing_applied_per_tier
```

---

### WP-76 — Hook integration for tiered checks

Wire tiered runner into Fettle's Claude Code hooks.

**Deliverables:**
- PostToolUse (Write/Edit): run `--fast` on changed file
- PostToolUse (Bash) on `git commit`/`git push`: run `--changed`
- Stop hook: report deferred results from timed-out checkers
- Result persistence for deferred reporting

**TDD contracts:**
```
test_post_edit_triggers_fast_check
test_git_commit_triggers_changed_check
test_git_push_triggers_changed_check
test_stop_hook_reports_deferred_results
test_fast_check_within_15s_budget
test_blocking_finding_blocks_commit
test_advisory_finding_does_not_block
test_secret_finding_always_blocks
```

---

### WP-77 — Suppressions and baselines

Allow teams to adopt Fettle without fixing every historical issue.

**Deliverables:**
- Baseline file (`.fettle/baseline.json`) — suppress existing findings
- Inline suppression (`# fettle:ignore[checker] reason`)
- Expiring suppressions (`expires: 2026-08-01`)
- `fettle baseline create` / `fettle baseline update`
- New findings still reported even with baseline

**TDD contracts:**
```
test_baseline_suppresses_existing_findings
test_new_findings_still_reported_with_baseline
test_inline_suppression_works
test_suppression_requires_reason
test_expired_suppression_re_enables_finding
test_baseline_create_captures_current_state
test_baseline_update_adds_new_suppressions
test_invalid_baseline_file_warned
```

---

## Phase 3: Python-First Checks (WP-78 → WP-85)

### WP-78 — Language adapter protocol + Python adapter

Define the adapter interface and implement Python as the reference.

**Interface:**
```python
class LanguageAdapter(ABC):
    language: str
    def detect(self, profile: Profile) -> bool
    def lint(self, mode: str, files: list[str]) -> list[Finding]
    def format_check(self, mode: str, files: list[str]) -> list[Finding]
    def typecheck(self, mode: str, files: list[str]) -> list[Finding]
    def test(self, mode: str, files: list[str]) -> list[Finding]
    def build(self, mode: str) -> list[Finding]
    def dependency_check(self, files: list[str]) -> list[Finding]
```

**Python adapter wraps:** ruff (lint+format), pyright/mypy, pytest, deptry/pip-check, pip install -e .

**Deliverables:**
- `scripts/adapters/__init__.py` — protocol + registry
- `scripts/adapters/python.py` — full Python adapter
- Adapter discovery from `adapters/` directory

**TDD contracts:**
```
test_adapter_registry_discovers_python
test_adapter_protocol_enforced
test_python_adapter_detects_from_profile
test_python_lint_wraps_ruff
test_python_format_wraps_ruff_format
test_python_typecheck_wraps_pyright
test_python_test_wraps_pytest
test_python_build_wraps_pip_install
test_python_dependency_wraps_deptry
test_missing_tool_produces_advisory
test_adapter_routing_by_workspace_language
```

---

### WP-79 — Dependency validation checker

Detect undeclared imports in Python code.

**Deliverables:**
- AST-based import extraction from edited files
- Compare against `pyproject.toml` / `requirements.txt` declared deps
- Stdlib module list (Python 3.11–3.14)
- Distinguish: stdlib, declared, local package, undeclared

**TDD contracts:**
```
test_detects_undeclared_import
test_ignores_stdlib_import
test_ignores_declared_dependency
test_ignores_local_package_import
test_handles_from_import
test_handles_conditional_import
test_handles_type_checking_import
test_reads_pyproject_dependencies
test_reads_requirements_txt
test_handles_extras_and_dev_deps
test_namespace_packages_handled
```

---

### WP-80 — Format checking

Verify formatting matches project style.

**Deliverables:**
- Python: `ruff format --check --diff`
- Profile-driven (reads command from adapter)
- Reports diff of violations
- Only checks changed files in fast/changed tier

**TDD contracts:**
```
test_detects_python_format_violation
test_passes_correctly_formatted_file
test_changed_tier_scopes_to_changed_files
test_full_tier_checks_all_files
test_reports_diff_output
test_missing_formatter_produces_advisory
test_generated_files_excluded
```

---

### WP-81 — Secret scanning

Detect accidentally committed credentials. BLOCKING by default.

**Deliverables:**
- Wrap `gitleaks` if available
- Regex fallback for common patterns (AWS keys, generic tokens, passwords)
- Changed-file-only in fast mode
- Never print raw secret in output (redaction)
- Allowlist in `.fettle.toml`

**TDD contracts:**
```
test_detects_aws_key_pattern
test_detects_generic_api_key
test_detects_password_in_config
test_ignores_allowlisted_pattern
test_uses_gitleaks_when_available
test_falls_back_to_regex_when_gitleaks_missing
test_only_scans_changed_files_in_fast_mode
test_raw_secret_never_printed
test_blocks_by_default
test_binary_files_skipped
```

---

### WP-82 — Entry point wiring checker

Verify declared console scripts resolve to real modules/functions.

**Deliverables:**
- Parse `[project.scripts]` from `pyproject.toml`
- Resolve `module.path:function_name`
- Verify module importable and function exists
- Trigger when pyproject.toml or referenced module changes

**TDD contracts:**
```
test_valid_entry_point_passes
test_missing_module_fails
test_missing_function_fails
test_non_callable_attribute_warned
test_extras_entry_points_checked
test_invalid_toml_handled
test_monorepo_package_resolved
```

---

### WP-83 — Python install / build validation

Verify package installs correctly. Full/CI tier only.

**Deliverables:**
- Run `pip install -e .` (or `uv pip install -e .`)
- Detect: missing deps, broken imports, build script failures
- Never mutates repo (uses temp venv or `--dry-run` where possible)

**TDD contracts:**
```
test_successful_install_passes
test_missing_dependency_fails
test_build_script_error_reported
test_uses_profile_build_command
test_skipped_in_fast_and_changed_tier
test_does_not_mutate_repo
```

---

### WP-84 — Python type checking

Pyright/mypy integration, incremental on changed files.

**Deliverables:**
- Detect type checker from config/profile
- Run incrementally: changed files + direct importers
- Report errors with file/line + suggested fix
- Changed/full tiers only

**TDD contracts:**
```
test_detects_type_error
test_passes_clean_file
test_uses_pyright_when_configured
test_uses_mypy_when_configured
test_incremental_scopes_to_changed_plus_importers
test_skipped_in_fast_tier
test_missing_typechecker_produces_advisory
test_type_error_includes_suggested_fix
```

---

### WP-85 — Python test command discovery

Discover how to run tests for a Python project.

**Deliverables:**
- Detect test framework: pytest (from pyproject.toml, conftest.py), unittest
- Detect test directories: `tests/`, `test/`, `src/*/tests/`
- Store in profile: `test_command`, `test_roots`
- Support: `pytest`, `python -m pytest`, `tox`, `nox`

**TDD contracts:**
```
test_discovers_pytest_from_pyproject
test_discovers_pytest_from_conftest
test_discovers_test_directory
test_discovers_tox_configuration
test_no_test_framework_returns_none
test_custom_test_command_from_config_honored
```

---

## Phase 4: Targeted Tests + Confidence (WP-86 → WP-89)

### WP-86 — Targeted test selection

Run only tests covering changed files.

**Strategy stack:**
1. Direct: changed test file → run it
2. Testmon: `pytest-testmon` coverage mapping
3. Import graph: reverse dependency lookup
4. Fallback: full suite on config/lockfile change

**Deliverables:**
- `scripts/checkers/targeted_tests.py`
- Integration with pytest-testmon / pytest --picked
- Import graph reverse lookup from existing `import_graph.py`
- Confidence scoring per test selection

**TDD contracts:**
```
test_changed_test_file_selected_directly
test_testmon_mapping_selects_covering_tests
test_import_graph_selects_dependents
test_config_change_triggers_full_suite
test_lockfile_change_triggers_full_suite
test_no_mapping_falls_back_to_full
test_confidence_high_for_direct_test
test_confidence_medium_for_testmon
test_confidence_low_for_no_mapping
test_respects_tier_timeout_budget
```

---

### WP-87 — Test confidence and fallback rules

Determine when targeted tests are sufficient vs when full suite needed.

**Rules:**
- High confidence (direct test, testmon): run targeted only
- Medium confidence (import graph): run targeted, warn about possible gaps
- Low confidence (no mapping): defer to full suite
- Force full: CI mode, config change, new dependency

**Deliverables:**
- Confidence scoring system
- Fallback policy in config
- Deferred-to-full reporting in Stop hook
- `fettle check --full` prompt when confidence is low

**TDD contracts:**
```
test_high_confidence_runs_targeted_only
test_medium_confidence_runs_targeted_with_warning
test_low_confidence_defers_to_full
test_ci_mode_forces_full_suite
test_new_dependency_forces_full
test_deferred_warning_in_stop_hook
test_confidence_is_deterministic
```

---

### WP-88 — Last-failed and failure-first testing

Re-run failed tests first for faster feedback.

**Deliverables:**
- `pytest --lf` (last-failed) integration
- `pytest --ff` (failures-first) for full runs
- Track failures in result history
- Fast feedback: re-run known failures before broader selection

**TDD contracts:**
```
test_last_failed_rerun_first
test_failures_first_in_full_mode
test_no_previous_failures_runs_normally
test_failure_history_persisted
test_cleared_on_full_pass
```

---

### WP-89 — Parallel test execution

Run tests in parallel for speed.

**Deliverables:**
- Integrate `pytest-xdist` when available (`-n auto`)
- Detect: is xdist installed? does project support parallel?
- Fall back to sequential if not
- Report timing: "42 tests in 8s (parallel) vs estimated 45s (sequential)"

**TDD contracts:**
```
test_uses_xdist_when_available
test_falls_back_to_sequential
test_respects_project_xdist_config
test_reports_timing_comparison
```

---

## Phase 5: CI Feedback Loop (WP-90 → WP-93)

### WP-90 — CI failure ingestion

Read CI failures from GitHub Actions, classify, store.

**Deliverables:**
- `scripts/ci_ingest.py`
- Use `gh run list --status failure` + `gh run view --log-failed`
- Classify: lint | type | test | dependency | build | env | flaky
- Store in `.fettle/ci-history.jsonl`
- `fettle ci failures` command
- Redact secrets from stored CI logs

**TDD contracts:**
```
test_ingests_failed_run
test_classifies_pytest_failure
test_classifies_lint_failure
test_classifies_type_error
test_classifies_install_failure
test_classifies_env_specific
test_classifies_flaky_test
test_stores_to_history
test_deduplicates_repeated_failures
test_redacts_secrets_from_logs
test_handles_gh_cli_missing
test_handles_auth_failure
```

---

### WP-91 — CI diagnosis and local comparison

Explain failures, show local-vs-CI coverage gaps.

**Deliverables:**
- `fettle ci diagnose` — explain last failure + local reproduction command
- `fettle ci compare` — show what CI checks vs what Fettle checks locally
- Gap report: "CI runs pyright, Fettle does not check types locally. Add typecheck."

**TDD contracts:**
```
test_diagnose_explains_test_failure
test_diagnose_suggests_reproduction_command
test_compare_shows_uncovered_ci_checks
test_compare_shows_fully_covered_checks
test_handles_no_ci_history
test_actionable_recommendation_format
test_environment_mismatch_detected
```

---

### WP-92 — CI learning loop (advisory)

Auto-suggest new gates after repeated CI failures. Advisory only — never auto-enables blocking.

**Deliverables:**
- Pattern detection: 3+ failures of same class → suggest gate
- `fettle ci learn` command — show suggestions with evidence
- Accept/reject/suppress suggestions
- Suggestions expire when failures stop

**TDD contracts:**
```
test_suggests_after_3_repeated_failures
test_no_suggestion_below_threshold
test_suggestion_includes_evidence
test_does_not_auto_enable_blocking
test_user_can_accept_suggestion
test_user_can_suppress_suggestion
test_suggestions_expire_when_failures_stop
test_respects_custom_threshold
```

---

### WP-93 — Persistent result history

Shared storage for run results, enabling CI comparison, deferred hooks, and dashboard.

**Deliverables:**
- `.fettle/history.jsonl` — per-run result records
- Schema: timestamp, tier, findings[], duration, workspace, commit
- Pruning: keep last N runs or last 30 days
- Corruption recovery (truncated lines skipped)

**TDD contracts:**
```
test_stores_run_result
test_retrieves_recent_runs
test_prunes_old_entries
test_handles_corrupt_file
test_groups_by_workspace
test_includes_commit_sha
```

---

## Phase 6: Polyglot Adapters (WP-94 → WP-97)

### WP-94 — TypeScript / JavaScript adapter

**Wraps:** eslint/biome (lint), prettier/biome (format), tsc --noEmit (typecheck), vitest/jest (test), knip/depcheck (deps), npm ci / pnpm install (build)

**TDD contracts:**
```
test_detects_from_package_json
test_npm_vs_pnpm_vs_yarn_detected
test_lint_wraps_eslint_or_biome
test_format_wraps_prettier_or_biome
test_typecheck_wraps_tsc
test_test_wraps_vitest_or_jest
test_dependency_wraps_knip
test_build_wraps_npm_ci
test_missing_node_modules_advisory
```

---

### WP-95 — Rust adapter

**Wraps:** cargo clippy (lint), cargo fmt --check (format), cargo check (typecheck), cargo test (test), cargo audit/deny (deps), cargo build (build)

**TDD contracts:**
```
test_detects_from_cargo_toml
test_workspace_member_routing
test_lint_wraps_clippy
test_format_wraps_cargo_fmt
test_typecheck_wraps_cargo_check
test_test_wraps_cargo_test
test_dependency_wraps_cargo_audit
test_missing_toolchain_advisory
```

---

### WP-96 — Go adapter

**Wraps:** golangci-lint (lint), gofmt (format), go vet (typecheck), go test ./... (test), govulncheck (deps), go build ./... (build)

**TDD contracts:**
```
test_detects_from_go_mod
test_multi_module_routing
test_lint_wraps_golangci_lint
test_format_wraps_gofmt
test_test_wraps_go_test
test_dependency_wraps_govulncheck
test_missing_go_advisory
```

---

### WP-97 — Adapter integration tests

Fixture-repo integration tests for all adapters.

**Deliverables:**
- Committed fixture repos: Python single, Python monorepo, Node pnpm workspace, Rust workspace, Go module, mixed Python+JS
- Each fixture has known violations + clean state
- End-to-end: `fettle check --fast` / `--full` on each fixture

**TDD contracts:**
```
test_python_fixture_fast_check
test_python_fixture_full_check
test_node_fixture_fast_check
test_rust_fixture_fast_check
test_go_fixture_fast_check
test_polyglot_fixture_routes_correctly
test_unknown_stack_fixture_passes_gracefully
```

---

## Phase 7: Advanced Features (WP-98 → WP-103)

### WP-98 — Generated code / schema drift

Detect stale generated files when source schemas change.

**Deliverables:**
- Config: `[generated]` section maps source → output → command
- Detect source change without output change → warn
- Generic framework (not tied to specific generator)

**TDD contracts:**
```
test_drift_detected_when_schema_changes
test_no_drift_when_output_matches
test_generator_missing_produces_advisory
test_generated_file_direct_edit_warned
test_multiple_generators_supported
```

---

### WP-99 — Database migration safety (advisory)

Flag risky migration patterns. Python/Alembic + Django initially.

**Deliverables:**
- Detect: DROP TABLE/COLUMN, NOT NULL without default, data-destructive ops
- Advisory only (never blocking in v0.5.0)
- `alembic check` / `makemigrations --check` integration

**TDD contracts:**
```
test_detects_drop_column
test_detects_not_null_without_default
test_safe_migration_passes
test_advisory_by_default
test_alembic_check_integration
test_no_migration_framework_skips
```

---

### WP-100 — AI-agent optimized summaries

Enhanced output for AI coding assistants (beyond basic findings from WP-69).

**Deliverables:**
- Per-finding: suggested fix text, related findings linkage
- Session summary: "3 blocking, 2 advisory, 1 deferred. Run `fettle check --changed` to clear."
- Severity escalation hints: "This import error will also cause 5 type errors downstream."

**TDD contracts:**
```
test_suggested_fix_included
test_related_findings_linked
test_session_summary_format
test_escalation_hints_when_applicable
test_output_concise_under_500_chars_per_finding
```

---

### WP-101 — Health dashboard — metrics collection

Track quality metrics per run.

**Deliverables:**
- Store: timestamp, findings count by severity, duration, tier, commit
- `fettle report` — summary of last N runs
- Test count vs source file count ratio
- Findings-per-commit trend

**TDD contracts:**
```
test_stores_metrics_per_run
test_report_shows_recent_history
test_test_source_ratio_calculated
test_findings_trend_direction
test_handles_empty_history
```

---

### WP-102 — Health dashboard — drift detection

Alert when quality is degrading.

**Deliverables:**
- Detect: findings trending up over last 10 commits
- Detect: untested files accumulating
- Detect: check time increasing (tool degradation)
- Advisory output in `fettle report --trends`

**TDD contracts:**
```
test_detects_upward_findings_trend
test_detects_untested_file_accumulation
test_detects_increasing_check_time
test_stable_project_shows_no_drift
test_trend_requires_minimum_history
```

---

### WP-103 — Documentation and examples

Adoption docs for the full v0.5.0 feature set.

**Deliverables:**
- Updated README
- Install guide (Claude Code plugin, standalone CLI, CI)
- Config reference (`.fettle.toml` all sections)
- Hook setup guide
- CI integration guide
- Adapter development guide
- Sample outputs for AI agents
- Troubleshooting

---

## Dependency Graph

```
Phase 1 (Platform):
  WP-67 (profile) → WP-68 (workspaces) ─┐
  WP-69 (result schema)                  ├→ Phase 2
  WP-70 (tool runner)                    │
  WP-71 (git changeset)                  │
  WP-72 (environment/tools)              │
  WP-73 (config/policy) ────────────────┘

Phase 2 (Runner):
  WP-74 (runner core) → WP-75 (tier policy) → WP-76 (hooks)
  WP-77 (suppressions/baselines)

Phase 3 (Python):
  WP-78 (adapter protocol + Python) → WP-79..85 (individual checkers)

Phase 4 (Tests):
  WP-86 (targeted selection) → WP-87 (confidence) → WP-88 (last-failed) → WP-89 (parallel)

Phase 5 (CI):
  WP-90 (ingest) → WP-91 (diagnose) → WP-92 (learn)
  WP-93 (history store) ← used by 90,91,92 and Phase 7

Phase 6 (Polyglot):
  WP-94 (TS/JS) ─┐
  WP-95 (Rust)   ├→ WP-97 (integration tests)
  WP-96 (Go)  ───┘

Phase 7 (Advanced):
  WP-98 (generated code) ← needs 78
  WP-99 (migrations) ← needs 78
  WP-100 (AI output) ← needs 69
  WP-101 (metrics) ← needs 93
  WP-102 (drift) ← needs 101
  WP-103 (docs) ← needs everything

Phase 8 (Pre-Generation + Agent Guardrails) — NO deps on Phases 1–7:
  WP-105 (skill edit)       ─┐
  WP-106 (lean review)      ├→ WP-108 (lean debt)
  WP-107 (lean audit)       │
  WP-104 (subagent hook)    ←─ uses content from 105
  WP-109 (config protect)   — standalone
  WP-110 (destructive guard)— standalone
  WP-111 (loop detect)      — standalone
  WP-112 (commit message)   — standalone
  WP-113 (debug statements) — standalone
  WP-114 (scope creep)      — standalone
```

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Phase 1 takes too long (7 WPs before visible value) | WP-67+69+70+73 are small; prioritize getting `fettle check --fast` working with ruff early |
| Adapter protocol over-designed | WP-78 merges protocol + Python adapter — validated by real implementation |
| Polyglot scope creep | Phase 6 is optional for v0.5.0 ship; Python-first is the MVP |
| Test selection confidence is wrong | Conservative fallback (run full suite when uncertain); WP-87 addresses this |
| CI ingestion requires `gh` CLI auth | Advisory: "run `gh auth login` to enable CI insights" |
| Hook timeout blown by tests | Tests never in fast tier; changed tier has 90s budget; deferred reporting |
| Secret scanner false positives | Allowlist + baseline + expiring suppressions (WP-77, WP-81) |
| SubagentStart hook latency | JS only, <50ms, fail-open, no Python interpreter startup (WP-104) |
| Ladder too aggressive (YAGNI kills needed code) | Non-lazy carve-outs for security/validation/accessibility; advisory mode (WP-105) |
| Lean review subjective | Read-only, no auto-fix; human decides what to act on (WP-106) |
| Config protect false positives (legit config changes) | Advisory by default; explicit user instruction overrides; allow_patterns escape hatch (WP-109) |
| Destructive guard evasion (obfuscated commands) | Pragmatic regex, not exhaustive; advisory default means the warning still fires even on partial match (WP-110) |
| Loop detection triggers on intentional retries | Threshold 3 + window 7 is conservative; config-tunable; advisory-only, never blocks (WP-111) |
| Commit message validation too rigid | Advisory by default; conventional commit is opt-in; max_subject configurable (WP-112) |
| Debug print false positives in CLI code | Path exclusions for cli/, scripts/, main.py; WARNING not ERROR (WP-113) |
| Scope creep warning annoys on large legitimate refactors | Advisory only; resets on commit; configurable thresholds; never blocks (WP-114) |

---

## Phase 8: Pre-Generation Enforcement (WP-104 → WP-108)

> Inspired by Ponytail's "The Ladder" philosophy. Zero dependencies on Phases 1–7 — can ship independently as v0.4.x.

### WP-104 — SubagentStart Hook (Pre-Generation Injection)

Inject coding discipline into subagents that never see Fettle's main-session rules.

**Problem:** Claude Code spawns subagents (TaskCreate, Agent tool, workflows) that generate bloated code with no quality philosophy. Post-edit hooks then catch errors — wasting cycles fixing what should never have been written.

**Deliverables:**
- `hooks/subagent_inject.js` — SubagentStart hook (<50ms, JavaScript)
- Addition to `hooks/hooks.json` under new `"SubagentStart"` key
- Configuration: `[gates.subagent]` section in `.fettle.toml`
- Matcher: `FETTLE_SUBAGENT_MATCHER` env var (regex on `agent_type`)

**Behavior:**
1. Fires on every subagent spawn
2. Reads `[gates.subagent].enabled` from config (default: true)
3. If disabled → exit immediately
4. If `FETTLE_SUBAGENT_MATCHER` set → read stdin, match `agent_type`, inject only on match
5. If no matcher → inject into all subagents (no stdin needed)
6. Output: `{ hookSpecificOutput: { hookEventName: "SubagentStart", additionalContext: <text> } }`
7. Fail-open on all errors (never block agent spawn)

**Injected content (<500 tokens):**
```
Before writing new code, stop at the first rung that holds:
1. Does this need to exist? Speculative = skip. YAGNI.
2. Already in this codebase? Grep first. Reuse > rewrite.
3. Stdlib/platform does it? Use it.
4. Already-installed dep solves it? Never add a dep for what few lines do.
5. One-liner? Do that.
6. Only then: minimum code that works.

No unrequested abstractions. Deletion over addition. Shortest working diff.
NEVER simplify away: input validation, error handling, security, accessibility.
```

**Config schema:**
```toml
[gates.subagent]
enabled = true
injection_file = ""         # custom content path; default: built-in ladder
mode = "advisory"           # advisory | off
```

**TDD contracts:**
```
test_injects_ladder_into_subagent
test_respects_disabled_config
test_matcher_filters_by_agent_type
test_no_matcher_injects_into_all
test_fails_open_on_stdin_error
test_fails_open_on_missing_config
test_injection_under_500_tokens
test_custom_injection_file_loaded
test_timeout_does_not_hang_session
test_json_output_format_correct
```

---

### WP-105 — The Ladder in discipline-coding Skill

Prioritized decision framework for code generation — reduces output volume by forcing reuse-first thinking.

**Problem:** `discipline-coding.md` says "Check for existing patterns" but provides no prioritized hierarchy. The agent's default bias is toward writing new code.

**Deliverables:**
- Edit `~/.claude/skills/discipline-coding.md`: replace rules 1–3 with The Ladder
- Keep rules 4–15 (renumbered)

**New "Before Writing Code" section:**
```markdown
### Before Writing Code (The Ladder)
Stop at the first rung that holds:
1. **Does this need to exist?** Speculative need = skip it. YAGNI.
2. **Already in this codebase?** Grep for helpers, utils, types. Reuse > rewrite.
3. **Stdlib/platform does it?** Use it. (CSS > JS, DB constraint > app code, lru_cache > custom)
4. **Already-installed dep solves it?** Never add a dep for what few lines do.
5. **One-liner?** Do that.
6. **Only then:** Write the minimum code that works.

Two rungs work → take the higher one.

Non-lazy carve-outs (never simplify these away):
- Input validation at trust boundaries
- Error handling preventing data loss
- Security measures
- Accessibility basics
- Anything explicitly requested
```

**No code changes.** Skill file edit only.

---

### WP-106 — `/fettle:lean` Slash Command (Over-Engineering Diff Review)

Review current diff specifically for over-engineering — a dimension Fettle currently lacks entirely.

**Problem:** Fettle reviews for bugs/security/lint but cannot detect when code passes all rules yet is 5x more verbose than necessary.

**Deliverables:**
- `commands/lean.md` — slash command definition (~40 lines)

**Behavior:**
- Scope: current diff only (git diff + staged)
- Reviews ONLY for over-engineering (not bugs, security, performance)
- Format: `L<line>: <tag> <what>. <replacement>.`
- Tags: `delete:` `stdlib:` `yagni:` `shrink:` `dep:`
- End: `net: -<N> lines possible.` or `Lean already. Ship.`
- Does NOT apply fixes (read-only)

**Implementation:** Pure markdown command file. No Python code.

**TDD contracts (manual):**
```
test_reviews_current_diff_only
test_only_reports_over_engineering
test_uses_correct_tag_format
test_ends_with_net_summary
test_does_not_apply_fixes
test_ignores_security_relevant_code
```

---

### WP-107 — `/fettle:audit-lean` Slash Command (Repo-Wide Audit)

Scan entire repo for accumulated unnecessary complexity.

**Deliverables:**
- `commands/audit-lean.md` — slash command definition (~50 lines)

**Hunts for:**
- Dependencies that stdlib already provides
- Single-implementation interfaces/abstractions
- Factories with one product
- Wrappers that only delegate
- Files exporting one trivial thing
- Dead feature flags
- Hand-rolled stdlib (custom retry, debounce, LRU, etc.)

**Format:** Ranked by biggest cut first. End: `net: -<N> lines, -<M> deps possible.`

**Implementation:** Pure markdown command file. No Python code.

---

### WP-108 — `fettle:lean:` Comment Convention + Debt Tracking

Track deliberate simplifications and their upgrade triggers.

**Problem:** When you skip an abstraction intentionally, that decision and its ceiling evaporate. Nobody knows when to grow the simple version.

**Deliverables:**
- Convention: `# fettle:lean: <what>, upgrade when: <trigger>`
- `commands/lean-debt.md` — slash command (grep + report)
- Addition to `scripts/report.py`: count lean markers

**`/fettle:lean-debt` behavior:**
- Greps `fettle:lean:` comments (skipping node_modules/.git/.venv/build)
- Format: `<file>:<line> — <what>. upgrade: <trigger>.`
- Flags `no-trigger` items (markers without "upgrade when:" → rot risk)
- End: `<N> markers, <M> with no trigger.`

**Config:**
```toml
[lean]
convention = "fettle:lean:"
warn_no_trigger = true
```

**TDD contracts:**
```
test_greps_fettle_lean_comments
test_parses_ceiling_and_trigger
test_flags_no_trigger_markers
test_skips_excluded_directories
test_report_includes_lean_count
test_handles_ts_and_python_comments
```

---

### WP-109 — Config Protection Gate

Prevent the agent from weakening linter/formatter configs instead of fixing the code.

**Problem:** When an agent encounters a lint error it can't easily fix, its path of least resistance is to disable the rule or weaken the config. This silently degrades project quality. ECC identified this as a top agent anti-pattern.

**Deliverables:**
- Addition to `scripts/quality_gate.py` (or new `scripts/config_protect.py`)
- PreToolUse(Write|Edit) check on known config file patterns

**Protected files:**
- `.eslintrc*`, `eslint.config.*`
- `.prettierrc*`, `prettier.config.*`
- `biome.json`, `biome.jsonc`
- `.ruff.toml`, `ruff.toml`
- `pyproject.toml` sections: `[tool.ruff]`, `[tool.mypy]`, `[tool.pyright]`
- `.shellcheckrc`
- `rustfmt.toml`, `clippy.toml`
- `.editorconfig`
- `tsconfig.json` (strict-related fields)

**Behavior:**
1. On first creation of a config file → allow (agent is setting up the project)
2. On modification of an existing config file:
   - **advisory mode (default):** warn "Fix the code, don't weaken the linter. Disable: `[gates.config_protect].enabled = false`"
   - **enforce mode:** block (exit code 2)
3. Exception: if the user's message explicitly says "update the linter config", "disable rule X", or "relax the config" → allow
4. Exception: adding rules (making config stricter) → allow

**Detection logic:**
- File path matches protected pattern AND file already exists on disk
- For `pyproject.toml`: only trigger if diff touches `[tool.ruff]`, `[tool.mypy]`, etc. sections (not metadata/deps)
- Cannot reliably detect "stricter vs weaker" in all cases → advisory by default

**Config:**
```toml
[gates.config_protect]
enabled = true
mode = "advisory"           # advisory | enforce
extra_patterns = []         # additional file globs to protect
allow_patterns = []         # file globs to always allow
```

**TDD contracts:**
```
test_blocks_eslintrc_modification
test_allows_eslintrc_creation
test_blocks_ruff_toml_modification
test_pyproject_only_triggers_on_tool_sections
test_allows_when_user_explicitly_requests
test_advisory_mode_warns_not_blocks
test_enforce_mode_blocks
test_extra_patterns_respected
test_allow_patterns_override
test_adding_rules_allowed
```

---

### WP-110 — Destructive Command Guard

Block dangerous bash commands that are hard to reverse.

**Problem:** Agents use destructive operations as shortcuts — `rm -rf`, `git reset --hard`, `git push --force`, `DROP TABLE`. These can destroy work. Fettle's MCP trust gate only covers package installs, not destructive shell commands.

**Deliverables:**
- Addition to `scripts/mcp_trust_gate.py` (extend existing PreToolUse(Bash) hook)
- Or new `scripts/destructive_guard.py` if cleaner

**Blocked patterns (regex on command string):**
```
rm\s+(-[rR]f|--recursive.*--force|-f.*-[rR]|--force.*--recursive)
git\s+(reset\s+--hard|push\s+--force|push\s+-f|clean\s+-fd|checkout\s+\.\s*$)
git\s+branch\s+-D
DROP\s+(TABLE|DATABASE|SCHEMA)
TRUNCATE\s+TABLE
pkill\s+-9|kill\s+-9
chmod\s+(-R\s+)?777
dd\s+.*of=/dev/
mkfs\.
```

**Behavior:**
1. Parse bash command from hook stdin
2. Match against destructive patterns
3. On match:
   - **advisory (default):** warn "Destructive command detected: `<cmd>`. Consider a safer alternative."
   - **enforce:** block (exit code 2) with message "Blocked: `<cmd>`. Use `[gates.destructive].mode = advisory` to allow."
4. Handle evasion: quoted strings, subshells `$(...)`, pipe chains, `eval`, `xargs rm`

**Evasion handling (pragmatic, not exhaustive):**
- Normalize: strip quotes, expand simple `$()` subshells, split on `;`, `&&`, `||`, `|`
- Each segment checked independently
- Known limitation: cannot detect all obfuscation; advisory by default is the safety net

**Config:**
```toml
[gates.destructive]
enabled = true
mode = "advisory"
extra_patterns = []         # additional regex patterns to block
allow_commands = []         # specific commands to always allow (e.g., "rm -rf node_modules")
```

**TDD contracts:**
```
test_blocks_rm_rf
test_blocks_git_reset_hard
test_blocks_git_push_force
test_blocks_drop_table
test_allows_safe_rm
test_allows_git_push_no_force
test_handles_quoted_commands
test_handles_pipe_chains
test_handles_semicolon_chaining
test_advisory_warns_not_blocks
test_enforce_blocks
test_allow_commands_override
test_does_not_false_positive_on_grep_containing_rm
```

---

### WP-111 — Tool Loop Detection

Detect and warn when the agent is stuck calling the same tool with identical parameters.

**Problem:** Agents sometimes enter loops — calling the same tool with the same arguments repeatedly without progress. This wastes tokens and context window. ECC detects "same tool+params 3x in last 5 calls" which is a cheap, high-signal heuristic.

**Deliverables:**
- `scripts/loop_detect.py` — PostToolUse hook addition
- Ring buffer of last N tool calls (tool_name + content hash of params)
- Warning when duplicate threshold exceeded

**Behavior:**
1. After each tool use, record: `(tool_name, hash(params))` in session state
2. Keep ring buffer of last 7 calls
3. If same `(tool_name, hash)` appears >= 3 times in the buffer:
   - Emit warning: "Loop detected: `<tool>` called 3x with identical params. Consider a different approach."
4. Never blocks (advisory only — loops self-correct once the agent sees the warning)
5. Reset buffer on tool change (different tool name breaks the count)

**State management:**
- Use existing session state dir (`$XDG_STATE_HOME/fettle/<session_id>/`)
- Append-only JSONL file: `tool_calls.jsonl`
- Read last 7 lines on each call (cheap I/O)

**Config:**
```toml
[gates.loop_detect]
enabled = true
threshold = 3               # consecutive identical calls to trigger
window = 7                  # ring buffer size
```

**TDD contracts:**
```
test_no_warning_on_unique_calls
test_warns_after_3_identical_calls
test_different_params_resets_count
test_different_tool_resets_count
test_window_size_respected
test_custom_threshold_works
test_hash_is_deterministic
test_handles_large_params_efficiently
test_session_state_persists_across_calls
```

---

### WP-112 — Commit Message Validation

Enforce conventional commit format and quality at commit time.

**Problem:** Agents write lazy commit messages ("fix bug", "update code", "changes") or exceed line length limits. Since Fettle already hooks PostToolUse(Bash), detecting git commit commands is cheap.

**Deliverables:**
- Addition to existing PostToolUse(Bash) hook chain
- Pattern: detect `git commit` in bash command → validate message

**Validation rules:**
1. Conventional format: `<type>(<optional-scope>): <description>`
   - Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
2. Subject line <= 72 characters
3. Subject starts lowercase after colon
4. No period at end of subject
5. Body (if present) separated by blank line
6. `Co-Authored-By:` line preserved (never stripped)

**Behavior:**
- Extract commit message from `-m "..."` or heredoc or tmpfile
- If message fails validation:
  - **advisory (default):** warn with suggested fix
  - **enforce:** this is tricky post-commit; better to catch pre-commit via PostToolUse on the bash command before execution
- Alternative: fire on PreToolUse(Bash) when command starts with `git commit` → validate before execution

**Implementation note:** PreToolUse(Bash) is better here — can block the commit before it happens. The message is visible in the command string.

**Config:**
```toml
[gates.commit_message]
enabled = true
mode = "advisory"
types = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"]
max_subject_length = 72
require_conventional = true
```

**TDD contracts:**
```
test_valid_conventional_commit_passes
test_missing_type_fails
test_invalid_type_fails
test_subject_too_long_fails
test_missing_colon_space_fails
test_allows_scope_in_parens
test_body_with_blank_line_passes
test_co_authored_by_preserved
test_advisory_warns_not_blocks
test_enforce_blocks_bad_commit
test_handles_heredoc_message
test_handles_quoted_message
test_ignores_non_commit_bash_commands
```

---

### WP-113 — Debug Statement Detection

Catch leftover debug statements before they ship.

**Problem:** Agents scatter `console.log`, `debugger`, `breakpoint()`, `print()` debug statements during development and forget to remove them. These leak into production, pollute logs, and expose internals.

**Deliverables:**
- New semgrep rules added to `rules/llm-antipatterns.yml` (Python) and `rules/ts-antipatterns.yml` (TS/JS)
- Severity: WARNING (not blocking — some are intentional)
- Auto-fixable: yes (ruff can remove `breakpoint()`, semgrep can flag for deletion)

**Rules to add:**

**Python (`llm-antipatterns.yml`):**
```yaml
- id: debug-breakpoint
  pattern: breakpoint()
  message: "Leftover breakpoint() — remove before shipping."
  severity: WARNING
  fix: ""

- id: debug-pdb
  patterns:
    - pattern: import pdb
    - pattern: pdb.set_trace()
  message: "Leftover pdb debugger — remove before shipping."
  severity: WARNING

- id: debug-print-statement
  pattern: print(...)
  paths:
    exclude:
      - "cli/"
      - "scripts/"
      - "**/cli.py"
      - "**/main.py"
  message: "print() in non-CLI code — use logging or remove."
  severity: WARNING
```

**TypeScript/JS (`ts-antipatterns.yml`):**
```yaml
- id: debug-console-log
  pattern: console.log(...)
  paths:
    exclude:
      - "scripts/"
      - "**/cli.*"
  message: "Leftover console.log — remove or replace with structured logger."
  severity: WARNING

- id: debug-debugger-statement
  pattern: debugger
  message: "Leftover debugger statement — remove before shipping."
  severity: ERROR
```

**Rationale for severity:**
- `debugger` = ERROR (always wrong in committed code, halts execution in browser)
- `breakpoint()` / `pdb` = WARNING (always wrong but less catastrophic)
- `console.log` / `print()` = WARNING (sometimes intentional in CLIs/scripts, hence path exclusions)

**Config:**
```toml
[gates.lint]
# Existing config; debug rules inherit the lint gate's mode
# Path exclusions in the semgrep rules themselves
```

**TDD contracts:**
```
test_detects_breakpoint
test_detects_pdb_import
test_detects_pdb_set_trace
test_detects_console_log
test_detects_debugger_statement
test_excludes_cli_paths_for_print
test_excludes_scripts_for_console_log
test_debugger_is_error_severity
test_print_is_warning_severity
```

---

### WP-114 — Scope Creep Warning

Warn when a session touches too many files, suggesting the agent is drifting from the task.

**Problem:** Agents expand scope silently — what starts as "fix this bug" becomes "refactor 30 files." By the time the Stop hook fires, the damage is done. A lightweight warning at file-count thresholds catches drift early.

**Deliverables:**
- Addition to `scripts/quality_gate.py` (PostToolUse path) — check edit count after each edit
- Warning at configurable threshold (default: 15 files)
- Critical warning at second threshold (default: 25 files)
- Reports: file list and original task scope (if detectable from session start)

**Behavior:**
1. On every PostToolUse(Write|Edit), read edit tracking file count
2. If count crosses warning threshold → emit advisory:
   `"Scope check: 15 files modified this session. Is this still on-task? Consider committing current changes."`
3. If count crosses critical threshold → stronger advisory:
   `"Scope creep risk: 25 files modified. Strongly consider stopping, reviewing, and committing before continuing."`
4. Never blocks (advisory only — scope decisions are the user's)
5. Threshold resets on explicit commit (detected via PostToolUse(Bash) `git commit`)

**Config:**
```toml
[gates.scope_creep]
enabled = true
warning_threshold = 15      # first advisory
critical_threshold = 25     # second advisory
reset_on_commit = true      # count resets after git commit
```

**Implementation notes:**
- Fettle already tracks edited files in `EDIT_TRACKING_FILE` — just count lines
- Commit detection: already parsed in PostToolUse(Bash) for other gates
- ~15 lines of additional code in `quality_gate.py`

**TDD contracts:**
```
test_no_warning_below_threshold
test_warns_at_warning_threshold
test_critical_at_critical_threshold
test_resets_after_commit
test_custom_thresholds_from_config
test_disabled_config_skips_check
test_advisory_only_never_blocks
test_warns_only_once_per_threshold_crossing
```

---

### Phase 8 Dependency Graph

```
Phase 8 (Pre-Generation + Agent Guardrails):
  WP-105 (skill edit)       — standalone
  WP-106 (lean review)      — standalone
  WP-107 (lean audit)       — standalone
  WP-104 (subagent hook)    — uses content from 105
  WP-108 (lean debt)        — soft dep on 106 (same conventions)
  WP-109 (config protect)   — standalone (PreToolUse gate)
  WP-110 (destructive guard)— standalone (extends PreToolUse(Bash))
  WP-111 (loop detect)      — standalone (PostToolUse addition)
  WP-112 (commit message)   — standalone (PreToolUse(Bash))
  WP-113 (debug statements) — standalone (semgrep rules addition)
  WP-114 (scope creep)      — standalone (PostToolUse count check)

  No dependencies on Phases 1–7.
```

---

## Success Criteria

1. `fettle check --fast` provides sub-15s feedback on every edit
2. `fettle check --changed` catches dependency, format, type, and targeted test failures before push
3. `fettle ci diagnose` explains why CI failed and whether Fettle would have caught it
4. Works on any Python project without manual configuration
5. Extensible to other stacks via adapter protocol
6. Zero surprise CI failures for: lint, format, type, dependency, entry point issues
7. Subagents generate code following The Ladder (Phase 8, WP-104)
8. Over-engineering is reviewable via `/fettle:lean` (Phase 8, WP-106)
9. Agent cannot silently weaken linter configs (Phase 8, WP-109)
10. Destructive commands are flagged before execution (Phase 8, WP-110)
11. Leftover debug statements caught before commit (Phase 8, WP-113)
12. Scope drift is surfaced before it compounds (Phase 8, WP-114)
