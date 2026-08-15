# Fettle configuration

> `.fettle.toml` is the shared policy source for agent hooks, the CLI,
> pre-commit, CI, and the LSP server. Each surface supports a different subset
> of checks, so validate the specific surfaces you intend to enforce.

Fettle reads a single optional `.fettle.toml` at your project root, plus
optional org/team packs and scoped overrides — all resolved by **one
resolver** shared by every gate and by `fettle config` (v1.7.0, WP-20).

## Start safely

For a new repository, prefer generated advisory defaults over copying a large
configuration:

```bash
fettle init --dry-run
fettle init --profile solo
fettle config --validate
fettle config --explain
fettle doctor
```

Use `team` when you need shared plans and worklogs. Evaluate `enterprise` in a
test repository before relying on stricter delegation and evidence gates. A
gate should move to `enforce` only after its tools, recovery path, and signal
quality are known in your environment.

## Policy source precedence

Later sources win (the capsule may only tighten):

| # | Source | Location |
|---|--------|----------|
| 1 | Built-in defaults | shipped with fettle |
| 2 | Org pack | `$XDG_CONFIG_HOME/fettle/org.toml` |
| 3 | Team pack | `$XDG_CONFIG_HOME/fettle/team.toml` |
| 4 | Central policy | `[extends]` in the repo config (digest-pinned, cache-only) |
| 5 | Repo config | `.fettle.toml` at the project root (or `$FETTLE_CONFIG`) |
| 6 | Directory overrides | `.fettle.toml` in ancestor dirs of the gated file |
| 7 | Env override | `FETTLE_GATE_MODE` (emergency only) |
| 8 | Policy capsule | `FETTLE_POLICY_CAPSULE` — tighten-only, beats even env |

Directory overrides apply only to per-file gates (the resolver walks the
edited file's ancestors); commands that resolve without a file get root
scope. Org/team packs may set `_name = "acme"` for provenance display.
Inspect the result with `fettle config --print-effective` (exactly what
gates load) and `fettle config --explain` (which layer set each key).

## Workspace and adapter behavior

The lint hook discovers nested Python, JavaScript/TypeScript, Go, and Rust
projects from their native project markers and routes each edited file to the
most specific matching workspace. Checks run from that workspace root, so local
tool configuration and repository scripts take precedence over unrelated root
settings.

Language adapters expose lint, format, typecheck, test, build, and dependency
operations through one workspace-first contract. The post-edit hook currently
invokes lint; other workflows use the operations relevant to their surface.
Every adapter operation has an explicit result state: `pass`, `violation`,
`tool_error`, or `unknown`. Missing tools, timeouts, and malformed output must
not be interpreted as a pass.

`fettle verify` groups session edits by affected workspace and records each
workspace result in `.fettle/verify.json`. For Python workspaces it narrows to
convention-matched impacted tests when that mapping is non-empty; otherwise it
runs the discovered full test command. Deleted implementation and test files
still participate in workspace routing.

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

An org-wide policy file can be layered UNDER a repo's config (see the
precedence table above — it sits between the team pack and the repo file):

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
- **Offline operation**: hooks never fetch policy. If no valid cached policy is
  available, local behavior and warnings depend on the calling surface; verify
  required central policy with `fettle policy status` in CI.
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

## Integrations (`[integrations.*]`, WP-14b)

External tool adapters, run via `fettle integrations [sonarqube|blackduck|pact]
[--json]` — no name runs every *enabled* adapter. All default **off**; tokens
always come from env vars, never from config. Exit codes: `0` pass, `1`
findings/failure, `2` misconfigured or unavailable (also returned when a
disabled adapter is named explicitly). `fettle doctor` reports readiness for
each enabled adapter.

```toml
[integrations.sonarqube]
enabled = true
endpoint = "https://sonar.example.com"   # https:// required unless allow_insecure
project_key = "my-project"
token_env = "SONAR_TOKEN"                # env var holding the token
allow_insecure = false

[integrations.blackduck]
enabled = true
cli_path = "polaris"                     # Polaris CLI binary
token_env = "POLARIS_TOKEN"
scan_timeout_s = 300

[integrations.pact]
enabled = true
broker_url = "https://pact.example.com"  # https:// required unless allow_insecure
token_env = "PACT_BROKER_TOKEN"
allow_insecure = false
```

## Mutation evidence (`[mutation]`)

Fettle's Python mutation surface separates readiness, execution evidence, and
policy. It is disabled by default and requires `mutmut==2.5.1` plus explicit
source paths and test mappings where convention-based mapping is insufficient.

```bash
fettle mutation preflight --all --json
fettle mutation run --changed --json --output mutation-report.json
fettle mutation status --report mutation-report.json --json
```

- **Preflight** generates and canonicalizes the complete engine-detail corpus
  without treating project-test outcomes as calibration evidence. Rejected
  details or fingerprint collisions fail closed.
- **Changed runs** select source from an explicit merge base and are the normal
  advisory feedback path.
- **Full runs** are scheduled/manual held-out verification. They support
  manifest-bound sharding and resumable fingerprint-keyed checkpoints, but an
  incomplete ledger cannot produce a score.
- **Baseline comparison** records survivor fingerprints from two independent,
  reproducible full reports on one revision. `new` and `existing` dispositions
  apply only to survivors; timeout, suspicious, skipped, and untested remain
  separate visible outcome classes.
- **Policy** keeps score, new survivors, untested outcomes, native timeouts, and
  suspicious outcomes distinct. `None` timeout/suspicious budgets are visible
  uncalibrated debt, not implicit acceptance.

```toml
[mutation]
enabled = true
mode = "advisory"              # promote only after measured reviewer feedback
engine = "mutmut"
paths = ["src/"]
exclude = ["tests/", "migrations/"]
base = "origin/main"
score_target = 80.0            # aspiration/policy target, not baseline history
minimum_scored_mutants = 10
max_new_actionable_survivors = 0
max_untested = 0
max_mutant_timeouts = 2        # omit to keep observed timeouts report-only debt
max_suspicious_mutants = 0
default_chunk_lines = 60
full_shards = 1

[mutation.test_mappings]
"src/entrypoint.py" = ["tests/test_entrypoint.py"]
```

Establish or check a baseline only from retained complete reports:

```bash
fettle mutation baseline check report-a.json report-b.json \
  --run-id RUN_A --run-id RUN_B --floor 70 --json
fettle mutation baseline establish report-a.json report-b.json \
  --run-id RUN_A --run-id RUN_B --floor 70 --json
```

The established file is `.fettle/mutation-baseline.json`. Commit it deliberately
if it is part of repository policy; `.fettle/` is commonly ignored because it
also contains runtime state. A baseline is a monotonic floor and identity record,
not a waiver for future survivors or evidence-integrity failures.

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
session_plans = true  # accept active session plans (.fettle/plans/) too —
                      # create one with `fettle plan start --title t --item step`,
                      # tick items with `fettle plan check <text>`

[gates.worklog]       # Stop requires a worklog entry — OFF by default
enabled = false
mode = "advisory"     # advisory | enforce
scope = "daily"       # daily: today's entry suffices | session: entry must be
                      # updated during THIS session; with an active session
                      # plan, Stop also surfaces planned-vs-done (advisory)

[gates.session_report] # Stop writes .fettle/reports/<session>.json — OFF by default
enabled = false       # files edited, claims held, plan progress, verify/CI
                      # stamps. Never blocks; read it via `fettle brief` or
                      # `fettle topology report`

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

[gates.mcp_trust]     # zero-trust package-install allowlist — OFF by default
enabled = false
allowlist_path = ""   # pin the allowlist file via policy; when set, the
                      # MCP_ALLOWLIST_PATH env override is IGNORED (an
                      # agent-writable env var must not redirect the trust
                      # root). Empty → env override or the default path.
                      # NOTE: command mediation is regex-based defense in
                      # depth, not a sandbox — pair it with [gates.destructive]
                      # enforce mode and OS-level controls for hard guarantees.

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
| `FETTLE_GATE_MODE` | Override enabled gate mode with `advisory`/`soft`/`enforce`, or request `off`. Delegated sessions also evaluate their capsule; validate strict capsule behavior with your runner before treating it as a security boundary. |
| `FETTLE_POLICY_CAPSULE` | Path to the tamper-evident policy capsule a parent handed this session (set by `fettle spawn`; merged monotonically — children can only tighten) |
| `FETTLE_PARENT_SESSION` | Spawning session id (set by `fettle spawn`; recorded on every trace entry for `fettle report --lineage`) |
| `FETTLE_PYTHON` | Interpreter used by the hook launcher (needs >= 3.11) |
| `FETTLE_STATE_DIR` | Base dir for per-session state (default `$XDG_STATE_HOME/fettle`) |
| `FETTLE_EDIT_TRACKING` | Override the per-session edit-tracking file path |
| `FETTLE_TRACE_DIR` | Override the trace directory |
| `FETTLE_LEAN_MAX_RUNTIME_MS` | Override the lean-sniffer wall-clock budget (default 200 ms; test harnesses pin a high value for determinism) |
| `FETTLE_LEAN_STATE_DIR` | Override the lean-review session state directory |
| `MCP_ALLOWLIST_PATH` | Override the MCP trust-gate allowlist path (default `~/.config/fettle/mcp-allowlist.json`). Inert when policy sets `[gates.mcp_trust].allowlist_path`. |

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
- **Per-project trace** (`.fettle/trace.jsonl`, override with
  `FETTLE_TRACE_DIR`) records detailed findings, hook metrics, and gate
  errors for the current repository.
- **Global decision trace** (`$XDG_STATE_HOME/fettle/trace.jsonl`, default
  `~/.local/state/fettle/trace.jsonl`) is the cross-repository audit log: one
  entry per hook decision with status, findings summary (file/line/code),
  session lineage, and capsule digest. Rotated automatically at ~5 MB. This
  store feeds `fettle explain`, `fettle report`, and `fettle insights`.
