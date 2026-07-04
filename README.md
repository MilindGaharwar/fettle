# Fettle

> **fettle** *(v.)* — to trim and clean a rough casting fresh from the mold.
> *"In fine fettle"* — in excellent condition.

Quality enforcement for AI-assisted development. Fettle intercepts every code
mutation made by Claude Code, runs static analysis in real time, and surfaces
findings before they reach production — ruff linting, semgrep pattern matching,
and **incident-derived LLM-antipattern rules** layered into a defense model that
catches issues at the point of creation rather than in code review.

**Status: pre-release (v0.2.0-dev).** The codebase is being restructured for its
first public release — see [docs/ROADMAP.md](docs/ROADMAP.md) for the full plan,
work packages, and release slicing. Expect breaking changes until v0.2.0 is tagged.

## Why Fettle

AI coding assistants produce code fast — including fast copies of the same
failure patterns: swallowed exceptions, regex-parsed LLM output, HTTP clients
without timeouts, SQL built with f-strings, health checks that report perfect
when they have no data. Fettle's rules exist because each of these caused a
real incident somewhere. The long-term goal (`/fettle:learn`, v0.4.0) is a tool
that converts every new postmortem into a tested, cited rule automatically.

## What it does today

- **Per-edit scanning** — a PostToolUse hook runs ruff + semgrep on every Python
  file Claude writes or edits, with advisory / soft / enforce modes.
- **Project scan with baselines** — `quality_scan.py --root . --baseline FILE`
  reports only findings new since the baseline (incremental adoption).
- **Cross-file Stop gate** — import/contract resolution checks before a response
  is delivered.
- **Process gates** (being generalized in v0.3.0) — plan-before-edit, test-freshness,
  UX-spec, and package-install trust gates.
- **LLM-antipattern rule pack** — 9 semgrep rules targeting failure modes specific
  to AI-generated code (see `rules/llm-antipatterns.yml`).

## Rules catalog (semgrep)

| Rule | Severity | Catches |
|---|---|---|
| `regex-llm-output` | ERROR | Regex-parsing LLM output instead of structured tool use |
| `bare-except-swallow` | ERROR | `except: pass` swallowing all errors |
| `broad-except-no-reraise` | ERROR | `except Exception` without re-raise or logging |
| `missing-httpx-timeout` | ERROR | httpx clients without timeouts |
| `sql-fstring` | ERROR | SQL built with f-strings (injection) |
| `health-score-inversion` | ERROR | Health checks returning perfect on no data |
| `orphaned-queue-flag` | ERROR | Queue writes with no verified consumer |
| `datetime-now-pipeline` | WARNING | `datetime.now()` in pipeline code (breaks backfill) |
| `non-atomic-write-output` | WARNING | Non-atomic writes in pipeline output paths |

Plus ruff rule selections (`BLE001`, `S110`, `S608`, `S701` as errors; `SIM*`,
`UP*` as warnings) — see `rules/.ruff.toml`.

## Installation (pre-release)

Requires Python >= 3.10, plus `ruff` and (optionally) `semgrep` on PATH:

```bash
git clone https://github.com/MilindGaharwar/fettle ~/tools/fettle
uv tool install ruff
uv tool install semgrep   # optional; semgrep rules skipped if absent
```

Run a project scan directly:

```bash
python3 ~/tools/fettle/scripts/quality_scan.py --root . --json
```

Claude Code plugin installation with automatic hook wiring ships in v0.2.0
(WP-4/WP-6 in the roadmap).

## Enforcement modes

| Mode (`QUALITY_GATE_MODE`) | Behavior |
|---|---|
| `advisory` (default) | Findings displayed, never blocks |
| `soft` | Errors displayed prominently; edits still allowed |
| `enforce` | New errors block the edit |

Recommended rollout: baseline in advisory -> fix errors in soft -> steady-state
enforce. Suppress individual findings with `# noqa: RULE` (ruff),
`# nosemgrep: rule-id` (semgrep), or glob patterns in `.fettle-ignore`.

## License

MIT (c) Milind Gaharwar
