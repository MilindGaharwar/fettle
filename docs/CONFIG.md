# Fettle configuration

Fettle reads a single optional `.fettle.toml` at your project root. Layering
(later wins): built-in defaults → `.fettle.toml` → environment variables.

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

## State model

- **Per-session state** (edit tracking, plan-gate counters, browser-test marker)
  lives under `$XDG_STATE_HOME/fettle/<session_id>/` — concurrent Claude Code
  sessions never see each other's state.
- **Per-project trace** (`.fettle/trace.jsonl`) records findings, metrics, and
  gate errors — the raw material for the effectiveness report (v0.4.0).
