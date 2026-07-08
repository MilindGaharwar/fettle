# CI enforcement plan — the gate that can't be skipped

Status: ACTIVE — 2026-07-08.

Fettle's hooks guard the inner loop, but they are advisory and easy to
skip, and each adopting repo hand-rolls its own CI — so a repo can ship
without the checks Fettle provides. This makes CI a first-class, generated
Fettle capability: one command produces a workflow that runs Fettle's gates
non-negotiably on every push/PR.

Design decisions:

- Build on the v0.4.0 surface, don't reinvent: extend `cli.py` (check/
  config/baseline/doctor) with a `ci` command; the secret scan becomes a
  Python checker reusing `result.py`/`report.py`; the workflow generator
  lands in `install.py` beside the existing hooks/config/ignore installers.
- The scrub audit graduates from a bash one-liner to a proper scanner:
  built-in secret patterns (API keys, tokens, cloud keys, private keys)
  PLUS a repo-configurable private-string list from `.fettle.toml`. The
  same detector runs in the hook, `fettle ci`, and generated workflows —
  one source of truth.
- Baseline-aware and fast, or it gets `[skip ci]`-bypassed: the quality
  gate fails only on findings NEW vs the committed baseline; the secret
  scan is regex over tracked files (sub-second). Never fail a repo for
  pre-existing debt.
- Generated, not copy-pasted: `fettle ci init` writes a correct workflow so
  every adopting repo inherits the secret scan for free — nobody hand-rolls
  a CI that forgets it.

## WP-1 Secret & private-string scanner

`scripts/secret_scan.py`: `scan_text(text, private_patterns)` (pure) and
`scan_repo(root, cfg)` over tracked files. Detects hardcoded secrets
(high-entropy `api_key=`/`token=`/`secret=` assignments, cloud access-key
IDs, `-----BEGIN … PRIVATE KEY-----`, `sk-…` tokens) and repo-configured
private strings (`[secret_scan].private_patterns` in `.fettle.toml`).
Skips obvious non-secrets (`your-…`, `<…>`, `changeme`, empty values,
`os.environ`/`getenv` reads, and environment-variable *names*). Wired as
`fettle check --secrets`; nonzero exit on real hits.

| # | Task | Method | Verify by |
|---|------|--------|-----------|
| 1 | Tests for `scan_text` using synthetic fixtures only: a documentation-style fake cloud key (`AKIAIOSFODNN7EXAMPLE`), a `-----BEGIN PRIVATE KEY-----` block, and a caller-supplied private pattern are each flagged; `os.environ.get("SOME_API_KEY")`, `key = "your-key-here"`, `token = ""`, and an env-var name are NOT; the entropy threshold flags a 40-char random string but not a dictionary word | TDD | `uv run --with pytest python -m pytest tests/test_secret_scan.py` green |
| 2 | Implement `scan_text` + `scan_repo` (git-tracked files, honors `.fettle-ignore`) + `--secrets` wiring into `cli.py check` | BUILD | task 1 tests pass |
| 3 | Regression — the scanner must not become a false-positive machine that gets disabled: a caller-supplied private-pattern list flags matching text while a scan of text with no secrets and no matching patterns returns none/zero (no data → clean, never a false hit or a crash) | REGRESSION | both a planted synthetic key AND the empty/no-data case asserted in tests/test_secret_scan.py |
| 4 | End-to-end `scan_repo` over a temp git repo: one file with a planted synthetic key + one clean file → exactly one finding with the correct path/line | INTEGRATION | `uv run --with pytest python -m pytest tests/test_secret_scan.py -k integration` |
| 5 | Run `python scripts/secret_scan.py --root .` on the Fettle repo itself: exits 0 (clean), and after planting a temp file containing `AKIAIOSFODNN7EXAMPLE` it exits nonzero and names that file; temp file removed | LIVE | clean run exits 0; planted-key run exits nonzero with the path |

## WP-2 `fettle ci` command + workflow generator

`scripts/ci.py`: `run_ci(root)` runs the enforced sequence — secret scan →
quality gate (baseline-aware) → plan validation (if plans present) →
tests — returning an aggregate pass/fail with one report. `cli.py` gains
`ci` (reproduce CI locally) and `ci init` (write
`.github/workflows/fettle.yml`). The generated workflow pins tool versions
and invokes `fettle ci`, so every adopting repo runs the same gates.

| # | Task | Method | Verify by |
|---|------|--------|-----------|
| 1 | Tests: `run_ci` on a clean temp repo returns pass; a planted synthetic secret makes it fail with the secret-scan finding surfaced; a new lint error over baseline fails; the generated workflow YAML parses and invokes `fettle ci` | TDD | `uv run --with pytest --with pyyaml python -m pytest tests/test_ci.py` green |
| 2 | Implement `run_ci` (compose secret_scan + quality_scan-vs-baseline + plan_validator + pytest) + `cli.py` `ci`/`ci init` + workflow template in `install.py` | BUILD | task 1 tests pass |
| 3 | Regression — a generated CI must never silently omit the secret scan, and CI must fail closed: the emitted workflow always contains the secret-scan step, and `run_ci` returns failure (not pass) if the secret scanner raises rather than skipping it | REGRESSION | workflow-content + fail-closed assertions in tests/test_ci.py |
| 4 | `fettle ci` over a temp repo wired end-to-end (clean → exit 0; planted synthetic key → nonzero) through the real compose path, not mocks | INTEGRATION | `uv run --with pytest python -m pytest tests/test_ci.py -k integration` |
| 5 | Run `python scripts/cli.py ci` at the Fettle repo root — reproduces CI locally and exits 0; run `python scripts/cli.py ci init --dry-run` and confirm the emitted YAML names the secret-scan + gate steps and parses under a YAML loader | LIVE | `ci` exits 0; `ci init --dry-run` prints a workflow naming both steps |

## Out of scope

- Replacing Fettle's own hand-tuned `.github/workflows/ci.yml` — the
  generator targets adopting repos; migrating Fettle's own CI is separate.
- Git-history secret scanning (working tree / tracked files only);
  dedicated tools own deep-history scans.
- Auto-remediation of found secrets — detection + fail is the contract.
