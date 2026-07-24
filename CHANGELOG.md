# Changelog

## v1.0.0 — Enterprise Integration + SWEBOK Coverage

### Enterprise Features (v1.0 plan)
- **WP-L — Extended secret scanner**: Azure Storage, Azure AD, GCP Service Account,
  GCP API Key, Bearer Token patterns. Config: `boundary.extra_secret_patterns`.
- **WP-N — Provenance policy gate**: 4 modes (none/manifest/marker/commit) for
  AI-generated code disclosure. PostToolUse(Write), new files only.
- **WP-O — Artifact verification gate**: PreToolUse(Bash) blocks publish without
  signed/scanned evidence. Evidence bound to exact artifact identity + exit code.
- **WP-P — Security review command**: `/fettle:security-review` orchestrating ruff
  S-rules + semgrep p/owasp-top-ten with CWE references.
- **WP-Q — Threat model command**: `/fettle:threat-model` STRIDE template with
  auto-detected entry points, data stores, and auth mechanisms.
- **WP-R — PR review orchestration**: `/fettle:pr-review` aggregates quality scan +
  coverage + complexity + breaking-change detection.
- **WP-S — SonarQube adapter**: IntegrationAdapter protocol, quality gate + issues API.
- **WP-T — Black Duck/Polaris adapter**: CLI invocation, SARIF parsing, subprocess security.
- **WP-U — Pact adapter**: Broker API for contract verification status.
- **WP-V — Architecture boundary rules**: import direction enforcement from .fettle.toml rules.
- **WP-W — ADR + Architecture discipline skills** in Disciplines plugin.

### SWEBOK v4 Gap Coverage
- **WP-X1 — Technical debt dashboard**: TODO/suppression count, complexity trend, A-E rating.
- **WP-X2 — Deployment safety gate**: PreToolUse(Bash) verifies tests ran, health endpoint
  exists, no debug flags before deploy commands.
- **WP-X3 — Release gate**: CHANGELOG/semver enforcement on `git tag`.
- **WP-X4 — Mutation testing command**: wraps mutmut, changed files only, configurable threshold.
- **WP-X5 — Requirements traceability**: links spec files to tests via naming + markers.

### Infrastructure
- **IntegrationAdapter protocol**: shared 5-state result model (pass/fail/unavailable/
  misconfigured/not_enabled) with configurable fail-open/fail-closed.
- **Codebase rationalization**: deleted 11 dead modules + 6 orphaned tests (-1,585 lines).
- **JSON schema contract tests**: 16 tests validating dispatcher output against Claude Code schema.
- **TypeScript adapter tests**: 21 dedicated integration tests.
- **Worklog gate**: daily worklog enforcement at Stop hook.
- **CI fix**: resolved semgrep false positive on f-strings.

## v0.9.0 — Engineering Discipline Enforcement

- **WP-K — Branch coverage gate**: extends coverage_gate.py to check
  missing_branches from coverage.json. Only flags branches originating from
  edited lines. Config: `gates.coverage.minimum_branch_percent`.
- **WP-H — Function complexity limits**: new complexity_check.py with
  cyclomatic and cognitive complexity per modified function (stdlib ast only).
  Config: `gates.complexity.max_cyclomatic`, `max_cognitive`.
- **WP-J — Enhanced plan thresholds**: risk paths (auth/security/migration
  globs), module count, and line estimation independently trigger plan gate.
  Config: `gates.plan.risk_paths`, `module_threshold`, `line_threshold`.
- **WP-I — TDD phase enforcement**: detects test-before-implementation ordering.
  Advisory mode only in v0.9. Config: `gates.tdd`.
- **VS Code extension**: new `integrations/vscode/` launches LSP server for
  inline diagnostics in VS Code.

## v0.8.0 — Discipline Integration

- **WP-A — Surface lean findings**: lean_sniffers returns advisory (not just
  silent JSONL) when `gates.lean_review.mode = "advisory"`.
- **WP-B — Normalized advisory contract**: Advisory dataclass, persisted
  AdvisoryDeduplicator, format_advisories renderer, aggregator cross-check cap.
  Config: `gates.advisory`.
- **WP-B2 — Migrate lean_sniffers onto AdvisoryDeduplicator**: single dedup
  mechanism across all advisory output.
- **WP-C — Discipline link pilot**: loop_detect injects 2-sentence debugging
  reminder from discipline-debugging (or fallback). Config: `gates.discipline_link`.
- **WP-D — Cooperative budget enforcement**: per-check deadline in HookContext,
  overrun logging, lean_sniffers honors dispatcher deadline.
- **WP-E — Bash structured audit**: privacy-first event logging (hash only by
  default, opt-in redacted capture). Config: `gates.bash_audit`.
- **WP-F — Diff coverage gate**: reads pre-existing coverage.json, staleness
  guard, advisory/enforce per mode. Config: `gates.coverage`.
- **WP-G — Shared discipline_link helper**: trigger-to-skill mappings ready for
  expansion after pilot metric passes.
- **hookEventName fix**: dispatcher now includes hookEventName in all output
  (fixes Claude Code Stop hook validation error).
- **bench/doctor PATH fix**: tools at ~/.local/bin found via _which() fallback.

## v0.7.0

- **WP-122 (partial) — Git-installable Python package**: console entry points,
  bundled rule resources, and `python -m fettle`. PyPI publication is deferred
  because that project name belongs to an unrelated package.
- **WP-123 — GitHub Action and reusable workflow**: advisory/enforce modes,
  SARIF output, and pull-request annotations.
- **WP-125 — LSP diagnostics**: `fettle lsp` publishes ruff and semgrep findings
  to editors over stdio JSON-RPC.
- **WP-126 (partial) — policy layering**: defaults, organization, team,
  repository, and directory-scoped configuration with `fettle config --explain`.
  Cryptographic bundle signing remains open.
- **OpenCode integration**: translates OpenCode tool/session lifecycle events
  into the existing dispatcher protocol while preserving Claude Code support.

## v0.6.0 arc

- **WP-124 (pulled forward) — pre-commit integration**: published
  `.pre-commit-hooks.yaml` with `fettle-check` (changed-files quality scan)
  and `fettle-rules-validate` (project rule packs must pass `--validate`);
  consumer snippet in `templates/pre-commit-config.yaml`. Same policy at the
  commit chokepoint regardless of editor/agent.
- **WP-133 (scaffold) — behavioral eval lab** (`evals/`,
  `scripts/evals_runner.py`): quorum-inspired, slimmed. Scenario dirs with
  prompt/setup_files/checks; three-valued verdicts; static side CI-safe
  (`evals_runner.py validate` + fake-runner unit tests), live side
  (`claude -p`) trusted-operator only. Two seed scenarios: hook-catches-debug-statement,
  plan-gate-nudges-multifile.
- **WP-116 — Rule-pack integrity gates** (`tests/test_rule_integrity.py`):
  every rule in every pack must have a `fire/` and a `silent/` fixture under
  `tests/fixtures/rulepacks/<pack>/<rule-id>/` — fixture-less rules fail the
  suite. Mutation check proves `--validate` catches the duplicate-key defect
  class that shipped in v0.4.0; generated project rules must validate too.
  46 fixtures added (23 rules × fire/silent). **Immediately caught a dead
  rule**: `string-built-sql-ts` never fired — semgrep's ellipsis does not
  match inside template literals; rewritten as `pattern-regex` (also covers
  SQL templates assigned to variables).
- **WP-117 — Tool-version canary CI leg**: ubuntu job against newest semgrep
  (`continue-on-error`, non-blocking) to surface upstream behavior changes
  early; pinned legs stay authoritative.
- **WP-119 — Ratchet workflow** (`scripts/ratchet.py`): evidence-based
  rule promotion/demotion. `fettle ratchet status` shows per-rule mode,
  fire count, FP rate, and promotion eligibility. `promote` only succeeds
  when a rule has ≥5 fires and ≤20% FP rate (aggregated from trace JSONL
  and false-positive stamps). `demote` requires a reason. `sync`
  re-aggregates without changing modes. Makes advisory-first a measured
  product feature instead of a convention. (21 tests)
- **WP-120 — Suppressions with expiry and owner**
  (`scripts/suppressions_v3.py`): structured suppression model with
  `# fettle:ignore[rule-id] reason=... owner=@handle until=YYYY-MM-DD`
  inline comments and `.fettle/suppressions.json` file-level entries.
  Expired suppressions become findings themselves; ownerless suppressions
  flagged in reports. CLI: `fettle suppressions {list|add|remove|report|expired}`.
  (28 tests)
- **WP-121 — Loaded-rules health telemetry**
  (`scripts/health_telemetry.py`): every hook run can log rules
  loaded/skipped per config source into trace (`record_loaded_rules`);
  `check_health` detects zero-rule packs and drops; `doctor_check()`
  discovers expected packs from `rules/*.yml` and asserts health.
  Standalone CLI for debugging. (16 tests)

## v0.4.2 — Go post-edit check (2026-07-16)

- **Go route** (`scripts/post_edit_go.py`, registered in the dispatcher for
  `.go` edits): semgrep runs the new built-in `rules/go-antipatterns.yml`
  (empty-error-swallow, debug-print, sql-string-concat, http-client-no-timeout)
  plus project rules from `.fettle/rules/`; golangci-lint runs when the anchor
  root has a `go.mod`. Enforce mode blocks on ERROR findings.
  End-to-end test proves a project-local Go rule (e.g. DVA3's
  `no-direct-kafka-produce`) fires through the hook (`tests/test_post_edit_go.py`).

## v0.4.1 — Rule config fixes + anchored semgrep scans (2026-07-16)

- **Fix: `ts-antipatterns.yml` was invalid** — duplicate `pattern-not-inside` keys
  (`unawaited-promise`) and `patterns` + sibling `pattern-not-inside`
  (`fetch-without-timeout`) made semgrep reject the whole config, silently
  disabling **all** TS/JS checks. Also fixed AND-vs-OR misuse: `empty-catch-block`,
  `string-built-sql-ts`, `regex-llm-output-ts` used `patterns:` (AND) where
  `pattern-either:` (OR) was intended and could never fire.
- **Fix: TS rule precision** — the resurrected rules measured ~9,000 findings on a
  23-file UI5 app. `unawaited-promise` now targets known promise-returning APIs
  (fetch/axios) instead of every statement-level call (semgrep OSS has no type
  inference), and ignores `.then()`/`.catch()` chains. `regex-llm-output-ts` is
  path-scoped to `agents/`, `pipeline/`, `llm/` like its Python counterpart.
  Same app now: 2 findings, both true positives (`tests/test_ts_rules.py`).
- **Project-local rules** (`scripts/project_rules.py`): projects extend the
  built-in rule packs via `.fettle.toml` — `[rules] extra_dirs` adds project
  semgrep rule files (default `.fettle/rules/`), `promise_apis` extends
  `unawaited-promise` with project-specific promise-returning APIs (validated
  identifiers only; rule generated and cached under `.fettle/generated/`).
  Both post-edit hooks pass the extra configs to semgrep.
- **Noise audit** of `llm-antipatterns.yml` on three real codebases: rules
  confirmed precise when scans are correctly anchored (mis-anchored scans
  defeated `paths.exclude` — same class of bug as the hook anchoring fix).
- **Fix: path-filter anchoring** (`scripts/semgrep_util.py`): semgrep ≥ 1.136
  resolves `paths.include`/`exclude` against the git project root; files outside a
  git repo silently escaped path-scoped rules and exclusions. Both hooks
  (`post_edit.py`, `post_edit_ts.py`) now scan via `anchored_semgrep_args()` —
  git root, else session cwd, else file dir — with `--project-root .`.
- **Tests** (`tests/test_semgrep_anchor.py`): every file under `rules/` must pass
  `semgrep --validate` (catches dead-config regressions), plus anchoring contract
  tests. Test harnesses in `test_rules.py`/`test_debug_detect.py` pin
  `--project-root` for non-git tmpdirs.

## v0.4.0 — Intelligence + Extensibility (2026-07-07)

- **TypeScript/JS rules** (`rules/ts-antipatterns.yml`): 5 semgrep rules for TS/JS
- **Cross-review** (`review.py`): provider-agnostic LLM code review
- **SARIF output** (`sarif.py`): GitHub code scanning format
- **Result caching** (`cache.py`): skip re-scanning unchanged files
- **Autofix** (`autofix.py`): safe ruff fixes with trace logging
- **Checker protocol** (`checker.py`): formal ABC for tool plugins (Ruff, Semgrep built-in)
- **Policy engine** (`policy.py`): central decision point for hook behavior
- **Event model** (`event.py`): typed FettleEvent replaces raw JSON
- **Install UX** (`install.py`): `fettle install config|hooks|ignore|all|status`
- **TS hook** (`post_edit_ts.py`): wired in hooks.json for TS/JS files

## v0.3.0 — Foundation for v0.3/v0.4 roadmap

### New modules
- **Result taxonomy** (`scripts/result.py`): PASS, VIOLATION, TOOL_ERROR, CONFIG_ERROR, SKIPPED. Finding dataclass with tool/severity/path/line/code/message/fixable.
- **Path resolver** (`scripts/paths.py`): centralized resolution, traversal protection, repo boundary checks, symlink safety.
- **CLI** (`scripts/cli.py`): `fettle check`, `fettle config --print-effective`, `fettle explain`, `fettle baseline`, `fettle doctor`.
- **Trace** (`scripts/trace.py`): persistent JSONL logging of all hook decisions.
- **Explain** (`scripts/explain.py`): human-readable explanation of last hook decision.
- **Baseline** (`scripts/baseline.py`): snapshot violations for incremental enforcement.
- **Learn** (`scripts/learn.py`): LLM-generated semgrep rules from incident descriptions.
- `pyproject.toml`: package metadata + console script `fettle`.
- 3 new slash commands: `/fettle:learn`, `/fettle:explain`, `/fettle:baseline`.
- `rules/learned/` directory for incident-derived rules.
- 33 new tests (test_result, test_paths, test_trace, test_baseline, test_learn, test_cli).

### GPT 5.5 audit
- `docs/AUDIT-GPT55.md`: independent code audit with prioritized TODO.

## Unreleased

- Stop-hook import checks understand src-layout packages (`src/<pkg>/`)
  and skip dependencies declared in pyproject/requirements even when no
  .venv exists to probe (ephemeral `uv run --with` envs) — a second
  round of import false positives on real-world project layouts.
- Stop-hook cross-file checks no longer flood real projects with false
  positives:
  `stop_quality_gate.py` discovers the project root by walking up to
  `pyproject.toml`/`setup.py`/`.git` instead of using the edited file's own
  directory; `check_imports` recognizes packages installed in the project's
  `.venv` (the hook's interpreter can't import them); `check_contracts`
  accepts `from pkg import submodule` without an `__init__` re-export.

- Removed `effectiveness_report.py`: it depended on a private logging tool
  no public install has; the tool's name joined the scrub-audit pattern.
  The effectiveness loop returns in v0.4.0 built on Fettle's own trace files.
- Rust/shell gate tests now run on ubuntu CI (cargo + shellcheck installed);
  cargo is resolved from PATH instead of a hardcoded Linux toolchain path.
- README documents the seven plugin slash commands.

## v0.2.1 (2026-07-04)

Fixes surfaced by dogfooding the project scan on a real multi-package repo:

- `quality_scan.py` findings and baselines now use root-relative paths, so a
  committed baseline matches on CI and other machines. Legacy absolute-path
  baselines are normalized on load and keep working.
- `.fettle-ignore` patterns now actually filter project-scan findings (they
  were only applied to the file count).
- File discovery prunes hidden dirs, `node_modules`, `venv`, `build`, `dist`
  (a `.venv` inflated the scanned-file count 40x).
- The project scan reads `[severity]` from `.fettle.toml` instead of
  hardcoded rule sets — CONFIG.md's "single source" claim is now true.
- New test suite for `quality_scan.py` (10 tests: baselines, portability,
  ignores, severity config, exit codes).

## v0.2.0 (2026-07-04)

First public release. Fettle began as a private quality-enforcement plugin;
this release makes it portable, configurable, and installable.

### Added
- `.fettle.toml` per-repo configuration: per-gate enables, severity single
  source, paths, review provider (docs/CONFIG.md).
- Session-scoped state under `$XDG_STATE_HOME/fettle/<session_id>/` — no
  cross-session interference.
- Portable interpreter launcher (`scripts/run.sh`) and `scripts/doctor.py`
  environment self-check.
- Authoritative plugin hook wiring (`hooks/hooks.json`) across PreToolUse /
  PostToolUse / Stop — enforcement installs with the plugin.
- Rule metadata (`origin`, `citation`) on every semgrep rule.
- CI (ubuntu + macos), permanent private-string scrub audit.

### Changed
- Opinionated process gates (plan, UX-spec, UI colors, doc-before-push,
  tests, MCP trust) are now **opt-in** and default off; the core lint gate
  defaults to advisory. Every block message names the config key that
  disables it.
- The legacy `QUALITY_GATE_MODE` env var is gone; mode lives in
  `.fettle.toml` (`[gates.lint].mode`, `[gates.docs].mode`) with
  `FETTLE_GATE_MODE` as the emergency override (`off` disables all gates).
- Fail-visible policy: missing or failing analysis tools emit warnings and
  `gate_error` trace events instead of silently passing.
- Python floor: 3.11 (stdlib tomllib).

### Fixed
- Baseline save crash on bare filenames.
- Test suite: 163 passed / 0 failed (was 53 failures against
  pre-consolidation script paths).
