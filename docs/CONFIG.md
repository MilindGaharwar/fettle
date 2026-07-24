# Fettle configuration

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
mode = "soft"         # advisory | soft | enforce

[gates.spec_audit]    # changed strategy/spec docs require current semantic audit — OFF by default
enabled = false
audit_path = "docs/spec-audit.md"
base_ref = "main"        # CI compares committed changes with this branch
spec_patterns = ["docs/*spec*.md", "docs/**/*spec*.md", "docs/*strategy*.md", "docs/**/*strategy*.md"]

[gates.tests]         # untested-code Stop gate + pre-commit warning — OFF by default
enabled = false

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
| `FETTLE_GATE_MODE` | Emergency override: `advisory`/`soft`/`enforce` set the mode of enabled gates; `off` disables every gate |
| `FETTLE_PYTHON` | Interpreter used by the hook launcher (needs >= 3.11) |
| `FETTLE_STATE_DIR` | Base dir for per-session state (default `$XDG_STATE_HOME/fettle`) |
| `FETTLE_EDIT_TRACKING` | Override the per-session edit-tracking file path |
| `FETTLE_TRACE_DIR` | Override the trace directory |
| `FETTLE_LEAN_MAX_RUNTIME_MS` | Override the lean-sniffer wall-clock budget (default 200 ms; test harnesses pin a high value for determinism) |
| `FETTLE_LEAN_STATE_DIR` | Override the lean-review session state directory |
| `MCP_ALLOWLIST_PATH` | Override the MCP trust-gate allowlist path (default `~/.config/fettle/mcp-allowlist.json`) |

## State model

- **Per-session state** (edit tracking, plan-gate counters, browser-test marker)
  lives under `$XDG_STATE_HOME/fettle/<session_id>/` — concurrent Claude Code
  sessions never see each other's state.
- **Per-project trace** (`.fettle/trace.jsonl`) records findings, metrics, and
  gate errors — the raw material for the effectiveness report (v0.4.0).
