# Fettle configuration

> One file drives everything. The same `.fettle.toml` powers agent hooks
> (Claude Code, Codex CLI, Gemini CLI, OpenCode), the CLI, pre-commit, CI,
> and the LSP server — set policy once, enforce it at every chokepoint.

Fettle reads a single optional `.fettle.toml` at your project root. Layering
(later wins): built-in defaults → `.fettle.toml` → environment variables.

A machine-readable schema is published at
[fettle.schema.json](fettle.schema.json) (generated from the built-in
defaults; a test keeps it current). Validate your config locally:

```bash
fettle config --validate
```

Unknown keys are warnings (they silently do nothing — the classic typo
failure mode); type mismatches are errors.

## Validation: no invalid config states (WP4)

Beyond types, validation enforces a dependency model so that a config which
validates behaves as written:

- **Per-gate modes** — each gate accepts only the modes its code honors
  (e.g. `gates.lean_review.mode` is `silent | advisory`; `enforce` there
  would silently act as advisory). An out-of-vocabulary mode is an **error**.
  Every blocking gate's blocking mode is spelled `enforce`; the tdd and
  ci_bootstrap gates also accept `strict` as a legacy alias.
- **Numeric ranges** — thresholds and windows are bounds-checked (e.g.
  `gates.coverage.threshold` must be 0–100). Out of range is an **error**.
- **Cross-field dependencies** — e.g. `extends.url` without a valid
  `extends.sha256` pin is an **error**; enabling
  `gates.architecture_boundaries` with no `rules` is a **warning** (the gate
  would be inert), as is enabling `gates.ui_colors` with an empty palette or
  `gates.lean_review.tier2` with a blank model.

`fettle doctor` runs the same validation against your project's
`.fettle.toml` and reports the first problem it finds.

## Central policy (`[extends]`, WP-144)

An org-wide policy file can be layered UNDER a repo's config
(defaults → org policy → repo `.fettle.toml` → env):

```toml
[extends]
url = "https://raw.githubusercontent.com/acme/policy/<commit>/fettle-org.toml"
sha256 = "9f2c…"   # content digest — the pin is mandatory
```

- **Digest-pinned**: the sha256 is verified on fetch and on every cache
  read; changed remote content is rejected until the pin is updated
  deliberately. Compute with `shasum -a 256 <file>`.
- **Never network in hooks**: hooks resolve the policy from cache only.
  `fettle policy sync` fetches (HTTPS only, 1 MiB cap); `fettle policy
  status` shows pin + cache state; `fettle doctor` warns when a configured
  policy isn't synced.
- **Offline-safe**: an unsynced or unreachable policy degrades to local
  config with a warning — enforcement never breaks because a server is down.
- One hop only: an org policy cannot itself contain `[extends]`.

## Telemetry (`[telemetry]`, WP-148)

Anonymous aggregate counters (decisions / fired / blocked / overridden /
tool errors) — **default off**, and only the org's digest-pinned central
policy (`[extends]`) can turn it on. `enabled = true` in a repo's own
`.fettle.toml` is ignored and surfaced by `fettle telemetry status`.

```toml
# In the ORG policy file (not the repo config):
[telemetry]
enabled = true
endpoint = "https://telemetry.example.com/ingest"   # https:// required
```

- `fettle telemetry status` — enabled? by whom? where would it go?
- `fettle telemetry show [--days N]` — the exact payload that would be sent
  (schema `fettle-telemetry/1`: integers + fettle version, nothing else —
  no code, paths, repo names, rule ids, or session ids).
- `fettle telemetry send [--days N]` — refused unless org-enabled;
  fire-and-forget with a 5 s timeout, failure never blocks anything.

## Example

```toml
[gates.lint]          # ruff + semgrep per edit — ON by default
enabled = true
mode = "advisory"     # advisory | soft | enforce

[gates.plan]          # multi-file edits require a recent plan — OFF by default
enabled = false
threshold = 3         # block at N+ implementation files without a plan
plan_dir = "docs"
max_age_hours = 1

[gates.ux_spec]       # frontend edits require a UX spec — OFF by default
enabled = false

[gates.ui_colors]     # hardcoded-color warnings — OFF by default
enabled = false
allowed_hex = ["#2563eb"]   # your brand palette

[gates.docs]          # git push requires a doc update after impl edits — OFF by default
enabled = false
mode = "enforce"      # advisory | enforce ("soft" is a deprecated alias for enforce)

[gates.spec_audit]    # changed strategy/spec docs require current semantic audit — OFF by default
enabled = false
audit_path = "docs/spec-audit.md"
base_ref = "main"        # CI compares committed changes with this branch
spec_patterns = ["docs/*spec*.md", "docs/**/*spec*.md", "docs/*strategy*.md", "docs/**/*strategy*.md"]

[gates.tests]         # untested-code Stop gate + pre-commit warning — OFF by default
enabled = false

[gates.tdd]           # test-before-implementation ordering — OFF by default
enabled = false
mode = "advisory"     # advisory | enforce — enforce BLOCKS impl edits with no prior test edit
                      # ("strict" is accepted as a legacy alias for enforce)
accept_preexisting_tests = true

[gates.complexity]    # per-function complexity ceilings — advisory by default
enabled = true
mode = "advisory"     # advisory | enforce
max_cyclomatic = 10
max_cognitive = 15

[gates.coverage]      # diff coverage at Stop — OFF by default
enabled = false
mode = "advisory"     # advisory | enforce
threshold = 80        # line coverage % for changed lines (0–100)
minimum_branch_percent = 0   # branch coverage (0 = disabled)

[gates.bdd]           # living-spec scenario coverage (see fettle spec) — OFF by default
enabled = false
mode = "advisory"     # advisory | enforce

[gates.claims]        # claim-before-work in fettle worktrees — OFF by default
enabled = false
mode = "advisory"     # advisory | enforce

[gates.agent_spawn]   # nested agent launches must use `fettle spawn` — ON, advisory
enabled = true
mode = "advisory"     # advisory | enforce — enforce blocks launches composed
                      # with hook-bypass flags (--dangerously-skip-permissions,
                      # --yolo, --full-auto) or FETTLE_GATE_MODE=off

[gates.verify]        # test suite verified green before Stop (fettle verify) — OFF by default
enabled = false
mode = "advisory"     # advisory | enforce
scope = "impacted"    # impacted (edited files → tests by name) | full
timeout_s = 120       # 1–3600; timeouts surface as unverified, never silently
parallel = false      # pytest-xdist when available

[gates.ci]            # remote CI verified green after push (fettle ci wait) — OFF by default
enabled = false
mode = "advisory"     # advisory | enforce
timeout_s = 900       # 1–7200; max wall time `fettle ci wait` polls for a verdict
poll_s = 15           # 1–300; seconds between remote polls

[worktrees]           # per-work-item worktree root (fettle worktree …)
root = ".fettle/worktrees"
require = false       # true → main-worktree edits to non-exempt paths are gated
                      # (honors gates.claims.mode; WP-162)
exempt_paths = ["docs/**", "**/*.md"]

[uat]                 # agentic UAT (fettle uat …)
surfaces = ["auto"]   # auto-detect, or explicit: ["cli", "api", "web", "library"]
app_url = ""          # running instance for api/web surfaces
start_command = ""    # or how to start it (e.g. "npm run dev")
runner = "claude"     # agent runner driving the session
timeout_s = 1800      # 1–86400
mode = "report"       # report only (gating arrives after evidence accrues)

[severity]
error_rules = ["BLE001", "S110", "S608", "S701"]
warning_prefixes = ["SIM", "UP"]

[paths]
ruff_config = ""      # empty → Fettle's bundled rules/.ruff.toml
trace_dir = ".fettle" # per-project findings/metrics log (gitignore it)
```

## Environment variables

| Variable | Effect |
|---|---|
| `FETTLE_GATE_MODE` | Emergency override: `advisory`/`soft`/`enforce` set the mode of enabled gates; `off` disables every gate — **cannot weaken a delegated policy capsule** |
| `FETTLE_POLICY_CAPSULE` | Path to the tamper-evident policy capsule a parent handed this session (set by `fettle spawn`; merged monotonically — children can only tighten) |
| `FETTLE_PARENT_SESSION` | Spawning session id (set by `fettle spawn`; recorded on every trace entry for `fettle report --lineage`) |
| `FETTLE_PYTHON` | Interpreter used by the hook launcher (needs >= 3.11) |
| `FETTLE_STATE_DIR` | Base dir for per-session state (default `$XDG_STATE_HOME/fettle`) |
| `FETTLE_EDIT_TRACKING` | Override the per-session edit-tracking file path |
| `FETTLE_TRACE_DIR` | Override the trace directory |
| `FETTLE_LEAN_MAX_RUNTIME_MS` | Override the lean-sniffer wall-clock budget (default 200 ms; test harnesses pin a high value for determinism) |
| `FETTLE_LEAN_STATE_DIR` | Override the lean-review session state directory |
| `MCP_ALLOWLIST_PATH` | Override the MCP trust-gate allowlist path (default `~/.config/fettle/mcp-allowlist.json`) |

## Automation recipes (WP-163)

Governed self-evolution runs on a schedule you own — recipes, not a daemon.
The sensing and drafting steps are autonomous; anything that changes policy
(`fettle rules promote`, `fettle ratchet promote`) stays a human command.

```cron
# Weekly digest: friction, emerging failure signatures, rule candidates,
# ungoverned sessions (read-only)
0 9 * * 1  cd /path/to/repo && fettle insights --days 7

# Weekly proposal drafting: repeated failure signatures become quarantined
# rule proposals in rules/proposed/ — never loaded by gates until promoted
5 9 * * 1  cd /path/to/repo && fettle learn --from-trace --auto-save

# Nightly supply-chain drift check
0 2 * * *  cd /path/to/repo && fettle doctor --verify-hashes
```

Review loop: `fettle rules list` → complete any evidence-brief patterns →
`fettle rules promote <id>` → load via `[rules].extra_dirs` → let
`fettle ratchet` accumulate fire/FP evidence before `ratchet promote`
moves it from advisory to enforce.

## State model

- **Per-session state** (edit tracking, plan-gate counters, browser-test marker)
  lives under `$XDG_STATE_HOME/fettle/<session_id>/` — concurrent agent
  sessions never see each other's state.
- **Per-project trace** (`.fettle/trace.jsonl`) records findings, metrics, and
  gate errors — the raw material for `fettle report`.
