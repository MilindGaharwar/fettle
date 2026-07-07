# Fettle Roadmap

> **fettle** *(v.)* — foundry term: to trim and clean a rough casting fresh from the
> mold. Also: *"in fine fettle"* — in excellent condition. Fettle does both to
> AI-generated code.

This roadmap is committed before implementation begins and updated as releases ship.

## Release plan

| Release | Theme | Work packages | Status |
|---|---|---|---|
| v0.2.0 | Core lint gates — portable, configurable, installable | WP-0..WP-6 | **Shipped** |
| v0.3.0 | Process gates + intelligence foundation | WP-7..WP-13 | **Shipped** |
| v0.4.0 | Cross-review provider, effectiveness loop, TypeScript rules | WP-14..WP-16 | Planned |
| v0.5.0 | SARIF, caching, autofix, install UX | WP-17..WP-20 | Planned |

Every release ships with green tests on macOS + Linux CI and an updated CHANGELOG.

## Work packages

### v0.2.0 — Core

- **WP-0 — Repo bootstrap & scrub (done in the initial commit).** Clean import, MIT,
  this roadmap, permanent `scripts/scrub_audit.sh` guard.
- **WP-1 — Portability & fail-visible foundation.** Shared interpreter launcher
  (`$FETTLE_PYTHON` → `python3` with a ≥3.10 check and a readable error), cargo via
  PATH, no silent tool failures (stderr warning + `gate_error` trace event),
  `scripts/doctor.py` self-check, fix `quality_scan.py` baseline-path crash.
- **WP-2 — Config & session state.** `.fettle.toml` per repo (stdlib tomllib;
  defaults → file → env). `[gates]` per-gate enable, `[severity]` single source
  (replaces in-code ERROR_RULES + `QUALITY_GATE_MODE`), `[paths]`, `[review]`,
  `[mcp]`. Session-scoped state under `$XDG_STATE_HOME/fettle/<session_id>/` keyed by
  the hook's `session_id` — no shared `/tmp` state.
- **WP-3 — Core edit-gate hardening.** post_edit + quality_scan on the config severity
  source; every rule carries `metadata: {origin, citation}`.
- **WP-4 — Authoritative hooks.json.** All hooks wired in the plugin itself
  (PreToolUse/PostToolUse/Stop → quality_gate; PostToolUse(Write|Edit) → post_edit;
  Stop → stop_quality_gate; PreToolUse(Bash) → mcp_trust_gate, config-disabled until
  v0.3.0), explicit timeouts. Enforcement follows the install — no global settings
  wiring required.
- **WP-5 — Test suite repair.** Retarget the 48 tests that invoke pre-consolidation
  script paths at `quality_gate.py` stdin events; de-hardcode machine paths; CI matrix
  (ubuntu + macos, pinned ruff/semgrep).
- **WP-6 — Docs & release.** README rewrite, CHANGELOG, marketplace metadata,
  tag v0.2.0. Verify via clean-machine install following README only.

### v0.3.0 — Process gates

- **WP-7 — Opinionated gates become opt-in config.** `[gates.plan]` (threshold,
  plan_glob, max_age), `[gates.ux_spec]`, `[gates.ui_colors]` (allowed_hex). Every
  block message names the config key that controls it.
- **WP-8 — Plan lifecycle reconciliation.** `/fettle:plan-activate` / `plan-complete`
  stamp status front-matter on `docs/<name>-plan.md`; the plan gate reads that;
  `plan_validator.py` required methods (TDD/INTEGRATION/REGRESSION/LIVE) config-driven.
- **WP-9 — Test stamping & Stop gates portability.** Configurable test patterns,
  session-scoped browser marker, `import_graph` dynamic-import allowlist from config.
- **WP-10 — MCP/package trust gate as safe opt-in.** Allowlist at
  `$XDG_CONFIG_HOME/fettle/mcp-allowlist.json`; documented threat model.

### v0.4.0 — Intelligence layer

- **WP-11 — Provider-agnostic cross-review.** Default provider: headless `claude -p`
  (runs on the user's Claude subscription — no API key); optional OpenAI-compatible
  endpoint from config. `/fettle:review` command.
- **WP-12 — `/fettle:learn` (flagship).** Incident text → LLM drafts a semgrep rule +
  a violating fixture + a clean fixture + citation → fixtures verified against semgrep
  (one automated repair round) → **human approval required** → lands in
  `rules/learned/` with citation metadata and a generated test. The tool that gets
  smarter after every postmortem.
- **WP-13 — Effectiveness loop.** Metrics from Fettle's own trace (+ optional
  best-effort Claude Code transcript parsing, flag-guarded); false-positive stamps;
  `/fettle:report`; auto-flag rules that never fire (retire candidates) or are always
  suppressed (recalibrate candidates).

### v0.5.0

- **WP-14 — TypeScript/JS rule pack.** Empty `catch {}`, unawaited promises, fetch
  without timeout/abort, string-built SQL, regex-parsing LLM output; post_edit
  dispatch for `.ts/.tsx/.js/.jsx`; fixtures + tests.

## Dependency graph

```
WP-0 → WP-1 → WP-2 ─┬→ WP-3 ─┬→ WP-5 → WP-6 ─────────── v0.2.0
                    ├→ WP-4 ─┘
                    ├→ WP-7 ─┬→ WP-8
                    │        └→ WP-9 ──┐
                    ├→ WP-10 ──────────┼──────────────── v0.3.0
                    ├→ WP-11 → WP-12 ──┤
                    │          WP-13 ◄─┘ (needs WP-3,9)  v0.4.0
                    └→ (WP-3,WP-7) → WP-14 ────────────── v0.5.0
```

## Design principles

- **Advisory by default.** Opinionated gates (plan/UX/UI/MCP) default off; core lint
  gates default advisory; every block message names its disable key. An enforcement
  tool that locks its user out gets uninstalled.
- **A broken gate must be loud.** Tool failures surface as warnings and trace events,
  never as silent passes.
- **Rules carry receipts.** Every rule has origin + citation metadata; `/fettle:learn`
  rules cite the incident that created them.
- **Single config source.** `.fettle.toml` — no scattered env vars or in-code tables.
- **No shared global state.** Per-session state dirs keyed by the hook `session_id`.

## Risk register (abridged)

| Risk | Mitigation |
|---|---|
| Per-edit semgrep latency feels broken | timeouts in hooks.json, `--metrics=off`, changed-file-only, advisory default |
| Enforce-mode locks the user out | advisory defaults, disable-key in every message, `FETTLE_GATE_MODE=off` escape hatch |
| False-positive storms | trace dedup, FP stamps feeding WP-13, fixtures-verified rules only |
| Silent self-failure | WP-1 fail-visible policy + `doctor` |
| Private-string leakage | `scripts/scrub_audit.sh` as a permanent CI job |
| `claude -p` interface drift | one thin wrapper module, doctor version probe, graceful degradation |
