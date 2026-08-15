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
- New contributors can start with the repository's
  [`good first issue`](https://github.com/MilindGaharwar/fettle/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22good%20first%20issue%22)
  backlog. Each starter issue must name its non-goals and verification commands.

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
uv run --extra evals python3 -m fettle.evals_runner validate
```

Changes to mutation behavior must follow the
[mutation quality playbook](docs/mutation-quality-playbook.md): fixtures first,
then preflight, narrow replay, and only then held-out full verification.

## Pull requests

Explain the user-visible problem, the smallest solution, and the checks run.
Call out operational limitations and intentionally unsupported surfaces. Never
include credentials, private transcripts, proprietary source, or generated
`.fettle/` state in a pull request.

Security vulnerabilities follow [SECURITY.md](SECURITY.md), not the public issue
tracker.

## Documentation

Write for the reader's next action:

- `README.md` explains the problem, differentiators, quick start, and honest
  product boundaries.
- `docs/README.md` routes users to task-specific guides.
- `docs/CONFIG.md` is the authoritative policy reference.
- `CHANGELOG.md` records shipped behavior; `docs/ROADMAP.md` records graduation
  triggers.
- `docs/archive/` and historical engagement notes preserve provenance and must
  not be rewritten as current instructions.

Avoid unverified exclusivity, performance, adoption, or security claims. Prefer
specific behavior that a user can reproduce.

## Release checklist

1. Keep `pyproject.toml`, `fettle/__init__.py`, and the first changelog heading
   on the same version.
2. Run the full tests, Ruff, Fettle CI, config validation, and `git diff --check`.
3. Build both sdist and wheel; install from the sdist in a clean environment.
4. Verify the console script, bundled rules, and all 17 workflow commands.
5. Push the reviewed commit, then push the matching `vX.Y.Z` tag. The release
   workflow performs OIDC publishing, provenance attestation, SBOM generation,
   and GitHub release creation.
