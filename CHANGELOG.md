# Changelog

## Unreleased

- Stop-hook cross-file checks no longer flood real projects with false
  positives (61 findings on one AlphaAgent response, 2026-07-07):
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

Fixes surfaced by dogfooding the project scan on a real repo (AlphaAgent):

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
