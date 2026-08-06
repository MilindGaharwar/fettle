# Contributing to Fettle

Fettle is a quality boundary, so changes should preserve visible failures,
stable host output, and advisory-first adoption.

## Development setup

Requirements: Python 3.11+, Git, and `uv`.

```bash
git clone https://github.com/MilindGaharwar/fettle.git
cd fettle
uv sync --extra dev
uv run fettle doctor
```

Install Semgrep when changing bundled rules or adapter Semgrep behavior:

```bash
uv sync --extra dev --extra semgrep
```

## Make a focused change

- Keep public behavior consistent across the CLI, hooks, configuration schema,
  tests, and documentation.
- Preserve the canonical result states: `pass`, `violation`, `tool_error`, and
  `unknown`. An unavailable analysis tool is not a pass.
- Keep host-specific wire output compatible; normalize behavior behind the
  dispatcher instead of changing every transport independently.
- Add both positive and clean fixtures for rule changes.
- Do not edit archived plans to describe current behavior. Update the README,
  active guides, changelog, or roadmap instead.

## Verify the change

Run the smallest relevant checks while iterating, then the full suite before a
pull request that changes behavior:

```bash
uv run --extra dev ruff check fettle tests
uv run --extra dev pytest
uv run fettle config --validate
uv run fettle check --changed
git diff --check
```

Documentation-only changes may use targeted contract tests instead of the full
suite, but examples, links, version metadata, and tested documentation claims
must still be verified. Changes to evaluation scenarios also require:

```bash
uv run --extra evals python3 scripts/evals_runner.py validate
```

## Pull requests

Explain the user-visible problem, the smallest solution, and the checks run.
Call out operational limitations and intentionally unsupported surfaces. Never
include credentials, private transcripts, proprietary source, or generated
`.fettle/` state in a pull request.

Security vulnerabilities follow [SECURITY.md](SECURITY.md), not the public issue
tracker.
