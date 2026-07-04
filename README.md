# Fettle

> **fettle** *(v.)* — to trim and clean a rough casting fresh from the mold.
> *"In fine fettle"* — in excellent condition.

Quality enforcement for AI-assisted development. Fettle intercepts every code
mutation made by Claude Code, runs static analysis in real time, and surfaces
findings before they reach production — ruff linting, semgrep pattern matching,
and **incident-derived LLM-antipattern rules** layered into a defense model that
catches issues at the point of creation rather than in code review.

**Status: v0.2.0** — first public release: core lint gates, portable and
configurable. See [docs/ROADMAP.md](docs/ROADMAP.md) for what's next
(generalized process gates in v0.3.0, the intelligence layer in v0.4.0).

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
- **Process gates, opt-in** (being generalized in v0.3.0) — plan-before-edit,
  doc-update-before-push, test-freshness, UX-spec, and package-install trust
  gates. All default **off**; enable per project in `.fettle.toml`.
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

Requires Python >= 3.11, plus `ruff` and (optionally) `semgrep` on PATH:

```bash
git clone https://github.com/MilindGaharwar/fettle ~/tools/fettle
uv tool install ruff
uv tool install semgrep   # optional; semgrep rules skipped if absent
```

Run a project scan directly:

```bash
python3 ~/tools/fettle/scripts/quality_scan.py --root . --json
```

### As a Claude Code plugin (hooks wire automatically)

```bash
claude plugin marketplace add MilindGaharwar/fettle
claude plugin install fettle@fettle-marketplace
```

Then run `python3 ~/.claude/plugins/*/fettle/scripts/doctor.py` (or
`scripts/run.sh doctor.py` from the repo) to verify the environment.

## Enforcement modes

Set per project in `.fettle.toml` (see [docs/CONFIG.md](docs/CONFIG.md)):

```toml
[gates.lint]
mode = "advisory"   # advisory | soft | enforce
```

| Mode | Behavior |
|---|---|
| `advisory` (default) | Findings displayed, never blocks |
| `soft` / `enforce` | Error-severity findings block with a mandatory fix directive (the two modes are equivalent in v0.2; stricter pre-edit blocking for `enforce` lands with the v0.3.0 gate generalization) |

`FETTLE_GATE_MODE` is the emergency env override (`advisory`/`soft`/`enforce`,
or `off` to disable every gate).

Recommended rollout: baseline in advisory -> fix errors in soft -> steady-state
enforce. Suppress individual findings with `# noqa: RULE` (ruff),
`# nosemgrep: rule-id` (semgrep), or glob patterns in `.fettle-ignore`.

## License

MIT (c) Milind Gaharwar
