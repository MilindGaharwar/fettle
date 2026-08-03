# v1.6.1 → v1.7 — Consolidated Audit Remediation Plan

Status: PLANNED (2026-08-03). Supersedes the earlier GPT-only draft of this
document.

Sources:
1. **GPT full audit** (2026-08-03, @ 24d26a3) — 24 findings (5 High, 12 Medium, 7 Low).
2. **Opus audit** (2026-08-03, @ 24d26a3) — graded review; C1–C15 triaged in the
   earlier draft, carried forward here.
3. **Owner directives** (2026-08-03): (i) resolve the shellcheck PATH warning,
   (ii) refresh legacy slash-command instructions to the quarantined-rule
   workflow, (iii) **cross-environment parity**: the 17 guided workflows must be
   available in ALL supported environments, not Claude Code only.

Every finding below was **re-verified against HEAD (b02b305)** before planning.
HEAD is one docs-only commit past the audited revision.

---

## Part 1 — Triage

### 1a. Confirmed High (GPT H-findings — all verified live at HEAD)

| # | Finding | Verification against current code |
|---|---|---|
| H-01 | Quality gate reads legacy `hook_event`, missing normalized events | Confirmed. [fettle/quality_gate.py](../../fettle/quality_gate.py) L467 reads `data.get("hook_event", "")`; `run_check` (L563+) forwards `ctx.input.raw` unchanged. Real agent payloads carry `hook_event_name`, so `is_pre` is always False → **UX/planning/CI-bootstrap blocks silently downgrade to warnings** on PreToolUse. Stop enforcement partially survives only via the `stop_hook_active` fallback (Claude-shaped payloads). |
| H-02 | Capsule disabled by version manipulation | Confirmed. `resolve_env_capsule()` ([fettle/policy_capsule.py](../../fettle/policy_capsule.py) L158+) checks `version > CAPSULE_VERSION` **before** `verify()` and returns `(None, "")` = benign skew. A child that can write its capsule sets `fettle_capsule: 999` and escapes inherited policy. Design decision D-A1 was made for legit version skew; it is wrong whenever `FETTLE_POLICY_CAPSULE` is asserted — the child controls the file. |
| H-03 | MCP package gate bypassable via shell syntax | Confirmed. `PKG_INSTALL_RE`/`BARE_PKG_INSTALL_RE` boundary class is `(^|&&|\|\||;|\$\()` — **no `\n`** (note: `IPTABLES_MODIFY_RE` *does* include `\n`, proving the gap is an oversight). No coverage for `env pip`, `command pip`, `python -m pip`, `uv pip`, backtick substitution, pipes into `sh`. |
| H-04 | Dispatcher allowlist-path protection weaker than standalone | Confirmed. `_check_file_result()` compares the literal string `"~/.config/fettle/mcp-allowlist.json"`; no `expanduser`/`abspath`, no `_allowlist_path()` (so the `MCP_ALLOWLIST_PATH` override is unprotected on the dispatcher path), no resolved protected-path comparison. `check_file_tool()` does all of this — two divergent implementations. |
| H-05 | Displayed policy ≠ enforced policy | Confirmed. `fettle config --print-effective` uses [fettle/policy_layers.py](../../fettle/policy_layers.py) (defaults → org.toml → team.toml → repo → dir overrides). Runtime uses `load_config()` (defaults → digest-pinned remote `[extends]` → repo → env → capsule). **Neither includes the other's sources.** 41 production call sites use `load_config()`; the layered path is inspection-only. |

### 1b. Confirmed Medium/Low (GPT M/L-findings, new relative to earlier draft)

| # | Finding | Verification |
|---|---|---|
| M-01 | `learn` rule_id path traversal | Confirmed. `_save_rule()` interpolates `rule_id` into paths unvalidated ([fettle/learn.py](../../fettle/learn.py) L124+). Same risk in the proposed-rules path. |
| M-02 | VS Code extension shell injection | Confirmed. `execSync(\`command -v ${candidate}\`)` (extension.ts L38) + `terminal.sendText` with interpolated paths (L162, L174). `FETTLE_PYTHON`/workspace paths reach a shell string. |
| M-04 | Verification stamp reusable across sessions | Confirmed. `.fettle/verify.json` freshness = stamp mtime vs `edits.jsonl` mtime; no session ID, commit SHA, or verified-file-set binding ([fettle/verify_gate.py](../../fettle/verify_gate.py)). |
| M-06 | `fettle doctor` exit code discarded | Confirmed. [fettle/cli.py](../../fettle/cli.py) L361: `subprocess.run(cmd, check=False)` — return code dropped; CLI always exits 0. |
| M-07 | PyYAML undeclared runtime dep | Confirmed. `fettle/evals_runner.py` L31 `import yaml`; `pyproject` declares zero runtime deps (pyyaml is dev-only). Clean wheel → `fettle evals` ImportError. |
| M-08 | CI doesn't run Ruff or coverage | Confirmed. ci.yml installs ruff but never runs `ruff check`; no coverage tooling. **3 live ruff findings**: `E741` ×2 (tests/test_semantic.py:110,193), `F401` (tests/test_uat_surfaces.py:11). |
| M-09 | Python 3.11/3.13 advertised, only 3.12 tested | Confirmed (ci.yml L32, release.yml L28). |
| M-10 | Release omits `fettle/tests/` | Confirmed. release.yml L45: `pytest tests/ -q`. Note: WP-14's test move resolves this at the root. |
| M-11 | Reproducibility gaps | **Partially confirmed** — audit overstated: ci.yml pins `ruff==0.15.20` and semgrep. Real gaps: pytest/pyyaml float; `fettle-reusable.yml` installs unpinned ruff/semgrep; release build/SBOM tools float; actions pinned by `@vN` tag not SHA; `uv.lock` ignored. |
| M-12 | VS Code extension over-advertises | Confirmed. Activates for 5 languages, LSP lints Python only; `lintOnSave`/`lintOnOpen`/`showComplexity` settings never read. |
| L-01 | `explain` missing file/line | Confirmed — post_edit detailed findings don't consistently carry location fields. |
| L-02 | Two trace stores under-documented | Confirmed (project findings trace vs global audit trace). |
| L-05 | Legacy `templates/ci-fettle.yml` references files init never creates | Confirmed. |
| L-06 | Evals scenario paths not containment-checked | Confirmed; requires explicitly running an untrusted scenario — low. |
| L-07 | `Typing :: Typed` with no type-check gate | Confirmed. |

### 1c. Already fixed at HEAD (no action)

| Audit claim | Reality at b02b305 |
|---|---|
| L-03 pre-commit template pins v1.3.0 | Now pins **v1.6.0** |
| L-04 GitLab template pins v1.3.0 | Now pins **v1.6.0** |

### 1d. Refuted or corrected (audits wrong — no action)

Carried from the earlier draft, all re-confirmed:

| Audit claim | Reality |
|---|---|
| claims_gate / complexity_check / dispatcher_aggregate / dispatcher_registry untested | All tested (test_work_items, test_complexity, test_output_schema+, registry pins across ≥5 files) |
| Replace setup.py with `package-data` | Infeasible — `rules/` is outside the package tree |
| GPT M-11 "unpinned Ruff in CI" | ci.yml pins ruff==0.15.20 (reusable workflow is the real gap) |
| Opus "1901/1716 test counts" | 1,723 pass / 4 skip at the tracked 24d26a3 baseline |

### 1e. Accepted as designed (document, don't change)

- quality_gate 15s subprocess timeout + fail-open (fail-visible design).
- `_find_cargo_toml` `while d != "/"` — Windows not a declared platform.
- Config sprawl / cli.py size — recorded debt, not scheduled.
- M-05 (budgets observational): partially accepted. Full deadline enforcement
  is over-engineering for a patch; WP-13 (lazy imports) removes the main
  overrun cause. Re-measure after; revisit only if overruns persist.

---

## Part 2 — Owner directives (verified)

### D1 — shellcheck warning
`shellcheck` is genuinely absent on this machine (`which shellcheck` → not
found). It is a **system binary**, not a Python tool, so it does not belong in
`PINNED_TOOLS` (uv-managed). CI installs it on ubuntu only. Locally, shell-gate
tests skip. Fix = install locally **and** make the product path actionable
(doctor hint + optional installer support). See WP-16.

### D2 — legacy slash-command content
Confirmed: 19 `${CLAUDE_PLUGIN_ROOT}/scripts/run.sh <module>.py` invocations
across the 17 `commands/*.md`. `commands/learn.md` instructs `--auto-save`
into `rules/learned/` — predates the v1.5 quarantine workflow
(`rules/proposed/` + `fettle rules promote`; proposed rules are never
gate-loaded, pinned by test). The command docs bypass the quarantine by
design-lag. See WP-17.

### D3 — cross-environment workflow parity (product directive)
Current docs (README L192+, docs/README L29+) explicitly label the 17
workflows "Claude Code plugin only". Owner directive: **all capabilities in
all environments**. Every target agent has a native custom-command mechanism:

| Environment | Mechanism | Location |
|---|---|---|
| Claude Code | plugin commands (exists today) | `commands/*.md` |
| VS Code Copilot | prompt files (`/name` in chat) | `.github/prompts/<name>.prompt.md` |
| Codex CLI | custom prompts (`/name`) | `~/.codex/prompts/<name>.md` |
| Gemini CLI | custom commands (`/fettle:<name>`) | `~/.gemini/commands/fettle/<name>.toml` |
| OpenCode | command files (`/fettle-<name>`) | `~/.config/opencode/command/` or project `.opencode/command/` |

Strategy: keep `commands/*.md` as the **single canonical source** (agent-
neutral after WP-17), add a generator that renders + installs per-agent
variants via `fettle init` (and a new `fettle workflows install` subcommand),
and bundle `commands/` into the wheel (same `setup.py` mechanism as
`rules/` → `fettle/_rules/`) so PyPI installs get them too. See WP-18.
This is new product surface → lands in **v1.7.0**, not the hardening patch.

---

## Part 3 — Work packages

### Release A — v1.6.1 "Hardening" (security + correctness patch)

Execution order within the release; WP-1..WP-8 are release blockers.

**WP-1 — Block-reason propagation (Opus C1) · CRITICAL, ~1 line + tests**
`run_check`: `context = hso.get("additionalContext") or hso.get("permissionDecisionReason") or output.get("reason", "")`.
Tests assert the real finding text reaches `CheckResult.block(...)`.

**WP-2 — Normalized hook contract in quality_gate (H-01) · HIGH**
`run_check` builds a canonical payload: take `ctx.input.raw`, overwrite/insert
`hook_event: ctx.input.hook_event_name` (and `tool_name`/`tool_input` from the
normalized input) before handing to the subprocess. Keep `main()` reading
`hook_event` for the standalone/legacy path; also accept `hook_event_name` as
fallback in `main()` for robustness.
Tests: end-to-end dispatcher tests for PreToolUse/PostToolUse/Stop through
**each** agent translator (claude, codex, gemini, opencode conformance
fixtures) asserting UX/plan blocks actually block on Pre and the Stop
tests-gate fires. This is the regression class the suite structurally missed.

**WP-3 — Capsule fail-closed on asserted version skew (H-02) · HIGH**
In `resolve_env_capsule()`: when `ENV_VAR` is set, unsupported schema version
is a **blocking error** (`(None, reason)`), not benign skew. D-A1 is revised:
skew tolerance applied only when no capsule is asserted (i.e., never — env
unset returns early). Keep the "update fettle in the child environment"
guidance inside the block reason.
Tests: version=999 blocks; version-newer + valid digest still blocks (child
cannot self-upgrade schema); malformed/missing/tampered continue to block.

**WP-4 — MCP trust gate hardening (H-03 + H-04) · HIGH**
(a) *Path parity*: one shared `_file_denial_reason(file_path, allowlist)` with
full resolution (expanduser + abspath + `os.path.realpath` for symlinks,
compare to `_allowlist_path()`, resolved + raw protected prefixes).
`check_file_tool` and `_check_file_result` both delegate. Parity test over a
path matrix (literal `~` form, expanded absolute, symlink spelling,
env-override path).
(b) *Command detection*: add `\n` and `|` to the boundary class in ALL package
regexes (iptables already has `\n`); recognize wrapper prefixes (`env`,
`command`, `sudo -E`, `nohup`, `xargs`), `python[3] -m pip`, `uv pip install`,
`uv tool install`. When a package-manager token appears in a position the
matcher cannot classify (inside `$(...)`/backticks), **default-deny in enforce
mode** with an "ambiguous command" reason. Adversarial corpus test (audit's
bypass list + variants). Docs honesty note: regex mediation is
defense-in-depth, not a sandbox — recommend enforce mode + bash_audit
together.
(c) *Env redirect (Opus 1.2)*: new `[gates.mcp_trust].allowlist_path` config
key (schema + DEFAULTS). When set via policy, `MCP_ALLOWLIST_PATH` env is
ignored; doctor surfaces an active env override.

**WP-5 — Claims integrity (Opus C3, GPT M-03) · HIGH**
`_save_claims`: tmp + `os.replace`. `claim_item`/`release_item`: `fcntl.flock`
on a sibling `claims.lock` around the read-modify-write. Multiprocess
contention test: exactly one winner.

**WP-6 — Trace growth (Opus C4/C8) · HIGH**
Opportunistic `rotate_trace()` from `log_decision` (size-stat threshold
~5 MB); bounded reverse tail-read for `get_recent_decisions`; doctor
trace-size probe.

**WP-7 — Verification stamp binding (M-04) · HIGH**
Stamp gains `session_id`, `head_sha`, `dirty_digest` (hash of
`git status --porcelain` output), and the resolved `impacted` file list.
Stop gate requires: same session, same HEAD (or stamp newer than last edit
AND same session), edited files ⊆ verified scope (empty scope = full suite =
always superset). Tests: cross-session stamp rejected; post-stamp edit
rejected; full-suite stamp accepted.

**WP-8 — learn rule-id validation (M-01) · MEDIUM**
Require `^[a-z0-9][a-z0-9-]{0,63}$`; reject otherwise (fall back to the
timestamp-generated id); assert each resolved destination stays inside
`rules/learned|proposed/` and `tests/fixtures/learned/`. Traversal tests.

**WP-9 — VS Code extension exec hygiene (M-02) · MEDIUM**
Replace `execSync` string interpolation with argv-array process APIs for
interpreter resolution; pass paths to terminals via escaped args or use the
Task/ProcessExecution API instead of `sendText` command strings.

**WP-10 — doctor exit propagation (M-06) · MEDIUM, 2 lines**
`sys.exit(proc.returncode)` in `cmd_doctor`; CLI-level test.

**WP-11 — PyYAML boundary (M-07) · MEDIUM**
Declare a `finefettle[evals]` extra containing pyyaml; `fettle evals` gives a
clear "pip install 'finefettle[evals]'" error when missing. Clean-wheel smoke
test in release.yml imports the module.

**WP-12 — Endpoint validation batch (Opus 1.4/1.6/1.7) · MEDIUM**
telemetry + cross_review: `urlsplit`-based https-or-loopback validation
(kills `http://localhost@attacker.com`); ci_gate slug regex
(`^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`) before URL interpolation.

**WP-13 — Lazy dispatcher registry (Opus 3.1) · MEDIUM (perf)**
Importlib-on-first-call shim; CheckSpec shape unchanged; measure with
`fettle bench` before/after; addresses the M-05 overrun cause.

**WP-14 — Carried from earlier draft · MEDIUM/LOW**
Remove `verify_bundle` stub (C6); quality_gate lazy `_init_state` guard (C10);
dedicated capsule_guard tests (C15); test-layout move `fettle/tests/` →
`tests/` + update every suite invocation (C9 — also closes GPT M-10).

**WP-14b — Wire integration adapters to the CLI (C14) · MEDIUM**
**DECIDED (2026-08-03): wire, don't remove** — the adapters are used by
developers. They already expose `run_command(config, cwd)` + `main()` +
`format_integration_report()`; what's missing is product surface:
- New subcommand `fettle integrations [sonarqube|blackduck|pact] [--json]`
  (no name = run all enabled; exit 0 pass / 1 fail / 2 misconfigured, matching
  the standing exit contract). ~40 lines in cli.py.
- `[integrations.sonarqube|blackduck|pact]` sections in `config.DEFAULTS`
  (enabled=false, endpoint, project_key/broker_url, token_env, fail_mode) —
  **currently absent from DEFAULTS and the JSON schema**, so this includes
  config_schema.py updates + `docs/fettle.schema.json` regeneration
  (anti-drift test enforces this).
- docs/CONFIG.md section; doctor probe when an integration is enabled but
  misconfigured.
- Tests: cmd-level tests with mocked adapters (exit codes, --json shape);
  schema round-trip. test_integrations.py keeps covering adapter internals.

**WP-15 — Fix the 3 live ruff findings** (E741 ×2 test_semantic, F401
test_uat_surfaces) — trivial; precedes CI enforcement in Release B.

**H-05 stopgap** — add a warning banner to `config --print-effective` naming
the sources it does NOT include (remote/env/capsule) until WP-20 lands.

### Release B — v1.6.2 "CI truth" (foldable into v1.6.1 if cheap)

**WP-B1 — CI enforcement (M-08)**: blocking `ruff check fettle tests` job;
coverage run (`pytest --cov=fettle --cov-branch`) with a threshold aligned to
the `.fettle.toml` coverage gate; publish the report.
**WP-B2 — Python matrix (M-09)**: 3.11/3.12/3.13 blocking, 3.14 canary
(non-blocking).
**WP-B3 — One canonical suite command (M-10)**: after WP-14's test move it is
`pytest tests/ -q` everywhere — grep ALL workflows + pre-commit + docs
(standing rule from the v1.3.0 release incident).
**WP-B4 — Pinning (M-11)**: pin pytest/pyyaml in workflows; pin
fettle-reusable.yml tools; pin build/SBOM tools in release.yml; pin
third-party actions by commit SHA; track `uv.lock`; drop the unnecessary
`pull-requests: write` permission in the reusable workflow.
**WP-B5 — Type-check honesty (L-07)**: add a non-blocking mypy/pyright job and
promote later, or drop the `Typing :: Typed` classifier — pick one.

### Release C — v1.7.0 "Workflows Everywhere" (owner directives D1–D3)

**WP-16 — shellcheck story (D1)**
(a) Immediate: `brew install shellcheck` locally (unblocks local shell-gate
tests). (b) Product: `fettle init --install-tools` and `doctor --fix` learn a
`SYSTEM_TOOLS` tier (shellcheck via brew/apt detection — best-effort; when no
package manager, the doctor warn line gains the exact per-OS install command).
(c) CI: install shellcheck on the macOS runner too, so both OSes exercise
shell paths.

**WP-17 — Command content refresh (D2) — precondition for WP-18**
Rewrite all 17 `commands/*.md`:
- Replace every `${CLAUDE_PLUGIN_ROOT}/scripts/run.sh X.py` (19 occurrences)
  with the corresponding `fettle <subcommand>`; verify each against the CLI
  parser during the pass.
- `learn.md`: align with quarantine — output goes to `rules/proposed/`
  (status: proposed), then `fettle rules list/promote`; keep the
  semgrep-verify step against the proposed file. Route `--auto-save`'s direct
  `rules/learned/` write through `rules/proposed/` too (one release with a
  deprecation warning on the old behavior).
- `mcp-approve.md`/`mcp-revoke.md`: verify against the current allowlist
  scheme (incl. WP-4c `allowlist_path` key).
- Anti-drift test: no `CLAUDE_PLUGIN_ROOT` in commands/; every referenced
  `fettle` subcommand exists in the CLI parser (same pattern as the
  schema-drift test).

**WP-18 — Cross-environment workflow distribution (D3)**
New `fettle/workflows.py` + `fettle workflows install
[--agent all|claude|vscode|codex|gemini|opencode] [--project|--user]`:
- Canonical source: `commands/*.md`, bundled into the wheel via the setup.py
  copy as `fettle/_commands/` (mirroring `rules/` → `_rules/`); extend
  `_resources.py` with `commands_dir()`.
- Renderers: VS Code prompt files (`.github/prompts/fettle-<name>.prompt.md`
  with frontmatter description), Codex prompts (`~/.codex/prompts/`), Gemini
  TOML commands (`~/.gemini/commands/fettle/<name>.toml`), OpenCode command
  markdown. Idempotent — overwrite only marker-owned files; same merge
  discipline as `init_codex`/`init_gemini`.
- `fettle init` auto-installs for detected agents; doctor gains a
  workflows-installed probe.
- Docs: README + docs/README reworded — these are **Fettle workflows**,
  available in every supported environment; table lists per-host invocation
  (`/fettle:quality` vs `/fettle-quality` per host naming rules).
- Tests: renderer golden files per agent; init idempotency; clean-wheel
  bundling smoke test (`commands_dir()` resolves in a clean venv).
- Verify Codex/Gemini/OpenCode command formats against current official docs
  at implementation time (formats evolve; capability matrix in the work note,
  same discipline as stage13).

**WP-19 — Product/doc alignment (P3 leftovers)**
VS Code selectors/settings match implemented behavior (M-12: remove unused
settings + non-Python selectors, or implement them); explain findings carry
file/line (L-01); document both trace stores (L-02); deprecate/remove
`templates/ci-fettle.yml` (L-05); evals scenario containment (L-06); correct
the README "tool-free suite" claim; document policy source precedence.

**WP-20 — Policy resolution unification (H-05) · HIGH, design doc first**
One canonical resolver: defaults → org (layered org.toml and/or remote
`[extends]` — precedence decision needed) → team → repo → directory(for-path)
→ env → capsule. Used by dispatcher, CLI, LSP, CI, and standalone gates.
`config --print-effective [--path FILE]` shows exactly what a gate receives;
parity test (inspection == runtime). **DECIDED (2026-08-03): fold the
org.toml/team.toml/directory layers into `load_config`** as supported runtime
behavior. Resulting canonical precedence:
defaults → org.toml → team.toml → remote `[extends]` → repo → directory
(for-path) → env → capsule (tighten-only). `policy_layers.py` becomes the
provenance/explain engine over the same resolver rather than a parallel
loader. Directory overrides apply only on path-scoped resolution (gates pass
the target file); pathless callers get root-scope config. Scheduled in v1.7
because it can change behavior at 41 call sites — too risky for the patch;
the v1.6.1 stopgap banner covers the interim. Ships behind its own design doc
with a migration note in CHANGELOG (repos using org.toml/team.toml gain
runtime enforcement — previously silently inspection-only).

---

## Part 3.5 — Effort estimate

Sizing: **S** ≈ ≤50 changed lines, few tests · **M** ≈ 50–250 lines, focused
test file · **L** ≈ 250–600 lines or cross-cutting · **XL** ≈ multi-slice,
design doc first. Test counts are new tests, additive to the ~1,900 suite.

| WP | Item | Size | Scope (files / new tests) |
|---|---|---|---|
| 1 | Block-reason propagation | **S** | quality_gate.py (1 line) / 2–3 tests |
| 2 | Normalized hook contract | **M** | quality_gate.py run_check + main fallback / ~12 e2e tests (3 events × 4 agents) |
| 3 | Capsule skew fail-closed | **S** | policy_capsule.py / 4–5 tests |
| 4 | MCP hardening (a+b+c) | **L** | mcp_trust_gate.py refactor + config key + schema / adversarial corpus ~25 tests + parity matrix |
| 5 | Claims flock + atomic write | **M** | work_items.py / 4–5 tests incl. multiprocess |
| 6 | Trace rotation + tail-read | **M** | trace.py, doctor.py / 6–8 tests |
| 7 | Verify-stamp binding | **M** | verify_gate.py / 6–8 tests |
| 8 | learn rule-id validation | **S** | learn.py / 4 tests |
| 9 | VS Code exec hygiene | **M** | extension.ts / manual + compile check (no test harness yet — see WP-B5 note) |
| 10 | doctor exit propagation | **S** | cli.py (2 lines) / 1 test |
| 11 | PyYAML `[evals]` extra | **S** | pyproject, evals_runner import guard, release.yml smoke / 2 tests |
| 12 | Endpoint validation | **S** | telemetry.py, cross_review.py, ci_gate.py / 6 tests |
| 13 | Lazy registry | **M** | dispatcher_registry.py / 2 tests + bench numbers |
| 14 | Stub removal, state guard, capsule_guard tests, test-move | **M** | 4 small items; test-move touches ci.yml/release.yml/pre-commit/docs |
| 14b | **Wire integration adapters to CLI** | **M** | cli.py +~40, config.py DEFAULTS, config_schema.py, schema regen, CONFIG.md, doctor / ~10 tests |
| 15 | 3 ruff fixes | **S** | 2 test files / — |
| — | H-05 stopgap banner | **S** | cli.py cmd_config / 1 test |
| **v1.6.1 subtotal** | | **~2 L, 7 M, 8 S** | ~90–110 new tests |
| B1 | CI ruff + coverage jobs | **S–M** | ci.yml / threshold calibration run |
| B2 | Python matrix 3.11–3.13 (+3.14 canary) | **S** | ci.yml, release.yml / fix any version breaks found |
| B3 | Canonical suite command | **S** | grep-all-workflows pass (mostly done by WP-14 test-move) |
| B4 | Pinning (actions SHA, tools, uv.lock) | **M** | 4 workflow files, .gitignore, action.yml |
| B5 | Type-check honesty | **M** | non-blocking mypy job + triage of first-run findings (unknown volume — the one true wildcard here) |
| **v1.6.2 subtotal** | | **~2 M, 3 S** | CI-config heavy, low code risk |
| 16 | shellcheck SYSTEM_TOOLS tier | **M** | init_cmd.py, doctor.py, ci.yml (macOS) / 4–5 tests |
| 17 | Command content refresh (17 files) | **M** | commands/*.md rewrite + learn.py proposed-routing + anti-drift test / 3–4 tests |
| 18 | Cross-environment workflow distribution | **XL** | new workflows.py (~300 lines), 4 renderers, setup.py bundling, _resources.py, init wiring, doctor probe, README/docs / ~25 tests + golden files + live verify in ≥2 hosts |
| 19 | Product/doc alignment batch | **M** | extension package.json/ts, post_edit locations, CONFIG.md, templates / 5–6 tests |
| 20 | Policy resolver unification | **XL** | design doc + config.py/policy_layers.py merge, 41 call sites audited, path-scoped resolution, parity tests / ~20 tests |
| **v1.7.0 subtotal** | | **2 XL, 3 M** | the two XLs each warrant their own design doc + review cycle |

Relative overall effort: v1.6.1 ≈ v1.7.0 > v1.6.2. The v1.6.1 blockers
(WP-1…8) are ~60% of that release's effort; WP-4's adversarial corpus and
WP-2's 4-agent e2e matrix are the bulk of the new test writing.

## Part 4 — Sequencing & release gates

| Release | Contents | Gate |
|---|---|---|
| v1.6.1 "Hardening" | WP-1…15 (incl. 14b) + H-05 stopgap banner | Full suite + new adversarial/parity/e2e tests + remote CI green + independent re-review of WP-2/3/4 diffs |
| v1.6.2 "CI truth" | WP-B1…B5 | Matrix green on 3.11/3.12/3.13; coverage report published |
| v1.7.0 "Workflows Everywhere" | WP-16…20 | Live verification in ≥2 agent hosts (Claude + one other); doctor probes green; docs parity check |

Standing rules apply: version-bump checklist, no tagging without explicit
approval, remote CI green after every push (`gh run watch --exit-status`).

## Part 5 — Re-audit acceptance criteria

Adopted from the GPT audit §16 (all 15 criteria), plus:

16. All 17 workflows invocable in Claude Code, VS Code, Codex, Gemini, and
    OpenCode, from both a git checkout and a clean PyPI install.
17. No `CLAUDE_PLUGIN_ROOT` reference remains in canonical command sources;
    the anti-drift test enforces CLI-subcommand existence.
18. `fettle doctor` on a machine with brew/apt offers an actionable
    shellcheck install path; CI runs shell gates on both OSes.
