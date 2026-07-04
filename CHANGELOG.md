# Changelog

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
