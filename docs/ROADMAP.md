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
| v0.4.0 | Cross-review, TS rules, checker protocol, install UX | WP-14..WP-16 | **Shipped** |
| v0.4.1 | Rule config repair, anchored scans, precision, project-local rules | — (hotfix arc) | **Shipped** |
| v0.4.2 | Go post-edit check (built-in pack + project rules) | — (hotfix arc) | **Shipped** |
| v0.5.0 | Adaptive enforcement platform (profiles, tiers, adapters, CI loop, dispatcher) | WP-67..WP-115 | **Shipped** (see [WORKPACKAGES-v050.md](WORKPACKAGES-v050.md)) |
| v0.6.0 | **Trust & precision** — the harness proves itself | WP-116..WP-121 | **Shipped** |
| v0.7.0 | **Reach** — same policy at every chokepoint | WP-122..WP-126 | **Shipped with distribution exceptions** |
| v0.8.0 | **Discipline integration** — advisory contract, link pilot, budget, audit, coverage | WP-A..WP-G | **Shipped** |
| v0.9.0 | **Engineering discipline enforcement** — branch coverage, complexity, plan thresholds, TDD | WP-H..WP-K | **Shipped** |
| v1.0.0 | **Enterprise integration** — security review, threat model, deploy safety, debt dashboard, adapters, SWEBOK gaps | WP-L..WP-X5 | **Shipped** |
| v1.1.0 | **Governance & agent audit** — compliance mapping, audit trail, cross-repo promotion | WP-127..WP-132 | Planned |

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

---

## Enterprise arc — v0.6.0 → v0.8.0

> Goal: state-of-the-art, general-purpose, enterprise-grade quality harness for
> agentic development. Grounding incident: v0.4.0 shipped an invalid TS rule file
> that silently disabled every TS/JS check for a full release, and its
> `unawaited-promise` rule measured **9,058 findings on a 23-file app** before
> precision work brought it to 2 true positives. The arc exists so neither
> failure class can recur — and so the fix generalizes beyond one laptop.

### v0.6.0 — Trust & precision (the harness proves itself)

- **WP-116 — Rule-pack integrity gates.** Enforced mechanically in CI: every
  `rules/**/*.yml` passes `semgrep --validate` (shipped in v0.4.1 — extend to
  learned/ and generated rules); every rule has ≥ 1 firing and ≥ 1 silent fixture
  (test fails on fixture-less rules); mutation check — corrupt a rule file in a
  fixture copy, assert the integrity suite goes red. *An invalid config that
  loads 0 rules is an ERROR, never a silent pass.*
- **WP-117 — Tool-version canary matrix.** CI legs run the full suite against
  semgrep N and N+1 and golangci-lint N and N+1. Catches upstream behavior
  changes (e.g. semgrep 1.136 re-anchoring `paths.include` to the git root)
  the week they ship, not months later. Doctor probes report tool versions
  against a tested-versions manifest.
- **WP-118 — Noise benchmark (`fettle bench`).** Pinned real-code corpus per
  language; findings-per-KLOC tracked per rule per release; release blocks if a
  rule regresses past its noise budget. Institutionalizes the manual
  measure-on-real-code step that caught the 9k-finding flood.
- **WP-119 — Ratchet workflow.** `fettle ratchet status` — per-rule TP/FP evidence
  aggregated from trace JSONL; `fettle ratchet promote <rule>` — advisory → enforce
  only when measured; `fettle ratchet demote` requires the same evidence standard.
  Makes advisory-first a product feature instead of a convention.
- **WP-120 — Suppressions with expiry and owner.** `# fettle:ignore[rule-id]
  reason=... owner=@handle until=YYYY-MM-DD`; expired or ownerless suppressions
  become findings themselves; `fettle suppressions report` for review meetings.
- **WP-121 — Loaded-rules health telemetry.** Every hook run logs rules
  loaded/skipped per config source into trace; `doctor` asserts expected counts;
  a drop to zero in any pack raises a blocking config error.

### v0.7.0 — Reach (same policy at every chokepoint)

- **WP-122 — Packaging & distribution (partial).** Git-installable wheel and
  console script shipped; clone-into-`~/.claude/plugins` remains supported.
  PyPI publication is deferred because the `fettle` project name is owned by
  an unrelated package. Signed artifacts, SBOM, and update checks remain open.
- **WP-123 — GitHub Action / reusable workflow (shipped).** First-class CI surface: one
  action running the same checks as the hooks, SARIF upload to code scanning,
  PR annotations. Replaces the copy-paste `ci-fettle.yml` template.
- **WP-124 — Pre-commit integration.** Published `.pre-commit-hooks.yaml`;
  identical rule resolution (project-root anchoring, `.fettle/rules/`) as hooks
  and CI — one policy, three chokepoints. *(Pulled forward: shipped with the
  v0.6.0 arc — `fettle-check` + `fettle-rules-validate` hooks + consumer
  template.)*
- **WP-125 — Editor diagnostics (LSP, shipped).** Serve findings as LSP diagnostics so
  humans see what agents see; reuse the dispatcher and cache; no new analysis.
- **WP-126 — Policy layering with provenance (partial).** Org pack → team pack → repo
  `.fettle.toml` → directory overrides; `fettle config --print-effective` shows
  which layer set every value; org packs distributable as signed bundles that
  repos consume read-only. Layer discovery, merging, path overrides, and CLI
  provenance are shipped; cryptographic bundle signing remains open.

### v0.8.0 — Governance & agent audit (enterprise operability)

- **WP-127 — Compliance mapping.** Rule metadata gains standard IDs (SDLC-L1,
  OWASP, CWE) alongside origin/citation; `fettle report --standard sdlc-l1`
  emits per-repo gate-satisfaction evidence — the artifact auditors ask for.
- **WP-128 — Agent audit trail.** Per-session/per-PR digest from trace: what the
  agent attempted, what was blocked, which advisories were ignored, attribution
  fields. Direct evidence for `agent-boundaries` and `ai-generated-code-policy`.
- **WP-129 — Incident-to-rule pipeline hardening.** `/fettle:learn` output must
  pass WP-116 integrity gates automatically: auto-generated fixture pair, shadow
  mode by default, human review step, promotion via WP-119 ratchet. Closes the
  loop: incident → rule → measured → enforced.
- **WP-130 — Cross-repo rule promotion.** A rule proven in one repo (ratchet
  evidence attached) can be proposed into the org pack with its fixtures and
  noise-benchmark results; registry file with provenance.
- **WP-131 — Air-gapped & data-boundary mode.** Offline deterministic runs
  (no metrics, no registry fetches), proxy support, LLM review strictly opt-in
  with endpoint pinning — zero code exfiltration by default; documented threat
  model for the harness itself.
- **WP-132 — Observability export.** Trace events exportable as OpenTelemetry
  spans/metrics; dashboard-ready: findings trend, gate latency budgets vs
  actuals, suppression debt, ratchet coverage.
- **WP-133 — Behavioral eval lab (`evals/`).** Shape adopted from
  superpowers-evals/quorum, radically slimmed: scenario dirs with
  prompt/setup_files/checks, three-valued verdicts (pass/fail/indeterminate),
  static side CI-safe (schema validation + fake-runner tests), live side
  (`claude -p`) trusted-operator only. Proves the step rule fixtures cannot:
  that gate messages actually change agent behavior. *(Scaffold pulled
  forward: runner + 2 seed scenarios shipped with the v0.6.0 arc; scenario
  corpus and baselines grow here.)*

### Enterprise-arc dependency graph

```
WP-116 ─┬→ WP-117
        ├→ WP-118 ─→ WP-119 ─┬→ WP-120           v0.6.0
        └→ WP-121            │
WP-122 ─┬→ WP-123            │
        ├→ WP-124            ├────→ WP-129 → WP-130
        ├→ WP-125            │                    v0.7.0 / v0.8.0
        └→ WP-126 ─→ WP-127 ─┴→ WP-128
WP-131, WP-132 — independent, any time after WP-122
```

Sequencing rationale: **trust before reach** (a harness distributed everywhere
must first be unable to fail silently), **reach before governance** (audit
evidence is only credible when the same policy fires at every chokepoint).

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
