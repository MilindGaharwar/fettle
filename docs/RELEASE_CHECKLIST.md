# Release Checklist — finefettle

Mechanical steps for cutting a PyPI release. Steps 1–4 happen on a release
branch; 5–8 after it lands on main. Every step is evidence-checked, not
assumed.

## 1. Content freeze

- [ ] `CHANGELOG.md` `Unreleased` section finalized and renamed to the
      version + date.
- [ ] `pyproject.toml` `version` bumped.
- [ ] `fettle/__init__.py::__version__` bumped — **must match pyproject**
      (`tests/test_cli.py::test_version_metadata_aligned` enforces this).
- [ ] `uv build` succeeds; wheel filename version matches.

## 2. Quality gates on the release branch

- [ ] Full test suite green (`uv run pytest tests/ -q`).
- [ ] `uv run ruff check fettle tests` clean.
- [ ] `uv run fettle check --changed` clean.
- [ ] Completion evidence valid (`uv run fettle completion validate`).

## 3. Land via PR

- [ ] PR opened; **post-approval pushes: verify `headRefOid` on the PR
      matches the branch tip before relying on auto-merge.** Squash merges
      capture whatever the PR head was when checks finished — late pushes
      silently miss the cut (this stranded #15/#18's tails on 2026-08-24).
- [ ] If `mergeStateStatus` is `DIRTY`/`BLOCKED`: merge main into the
      branch and resolve — GitHub skips ALL checks on unmergeable PRs, so
      "no checks reported" means fix mergeability first, not retry.
- [ ] Squash-merged. Verify `origin/main` contains the release-commit
      content (`git show origin/main:CHANGELOG.md | head`).

## 4. Tag and publish

- [ ] `git tag v<X.Y.Z> origin/main && git push origin v<X.Y.Z>` — the
      `release.yml` workflow builds the wheel, generates SLSA provenance +
      CycloneDX SBOM, and publishes via PyPI Trusted Publishing.
- [ ] Watch the release workflow to completion; confirm the **publish job**
      succeeded (not just build).
- [ ] Confirm the new version is live on pypi.org/project/finefettle.

## 5. Post-release

- [ ] GitHub About/description refreshed if positioning changed.
- [ ] `docs/plan-index.md` next-actions still accurate.
- [ ] Announcement draft (README loop link + changelog anchor).

## Hazard notes

- **Never run `mutmut apply` on a working tree you will later `git add -A`**
  — an applied-but-unreverted mutant corrupted committed code for two
  releases' worth of survivor data (2026-08-25). Use a scratch checkout.
- **Lint autofixes must never touch `examples/` violating fixtures** —
  they are intentional (see improvement-plan hazard note).
- **Version strings live in exactly two places** (pyproject, `__init__`)
  plus test fixtures that derive from `fettle.__version__` — never
  hand-copy into new locations.
