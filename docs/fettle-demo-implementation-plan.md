# Fettle Demo And Installed Init Plan

## User Story

As a prospective user, I want the installed wheel to configure my detected
agent host and demonstrate Fettle without a clone, project, network, or API key,
so that installation immediately proves a complete working loop.

## Assumptions

- Host presence is represented by the existing host configuration directory.
- The installed bridge remains the canonical wheel-mode transport.
- Demo verification must exercise behavior independently of its detector and repair.
- Published Git history is rewritten separately after implementation verification.

## Decisions And Tradeoffs

- Use package resources and the existing versioned bridge rather than recreating
  source-checkout paths. This preserves current host contracts and ownership checks.
- Use a Python-standard-library demo rule and `unittest` verifier rather than Ruff
  or Semgrep. This guarantees offline, cross-platform execution within the budget.
- Keep the fixture as package data under `fettle/_demo_fixture`; do not generate
  it in code, because wheel contents must provide auditable demonstration inputs.

## Blast Radius

- Packaging: `setup.py`, `pyproject.toml`, wheel contents.
- Installed setup: `fettle/bridge.py`, `fettle/init_cmd.py`, init tests.
- CLI and docs: `fettle/cli.py`, new demo module and fixture, README, CLI tests.
- Release confidence: candidate-wheel installation in an isolated environment
  and clean Linux container.

## Work Packages

1. Add wheel-content assertions for bridge and demo resources; build and inspect the wheel.
2. Make installed bridge resources explicit and fail visibly when required assets are absent.
3. Add the fixture, deterministic four-stage runner, CLI dispatch, and failure tests.
4. Put `pipx install finefettle` and `fettle demo` in the README's first code block.
5. Run focused and full tests, Fettle scan, isolated-wheel smoke, and container UAT.
6. Rewrite targeted Git metadata in a fresh mirror, verify unchanged trees, and force-push with leases.

## Success Criteria

- `pipx install <wheel> && fettle init` publishes a valid bridge and configures a
  detected host without source-checkout files.
- `fettle demo` succeeds outside a repository, offline, in under 20 seconds.
- Two demo runs have byte-identical stdout; a failed verifier exits non-zero.
- Windows, macOS, and Linux paths use only `pathlib`, `tempfile`, `shutil`, and the
  current Python interpreter; CI retains the existing Windows bridge gate.
- The wheel contains every bridge and demo resource consumed at runtime.
