# Stage 11 — WP-147 Supply-Chain Posture

Date: 2026-08 · Scope: enterprise plan WP-147 · Commit: see below

## What shipped

**Producer side (release.yml):**
1. **SLSA provenance + Sigstore signing** — `actions/attest-build-provenance@v2`
   on every `dist/*` artifact in the build job (`id-token: write` +
   `attestations: write`). One native action gives both; verification is
   `gh attestation verify <file> --repo MilindGaharwar/fettle`.
2. **CycloneDX SBOM per release** — generated from the smoke venv (the exact
   wheel that ships + its empty runtime dependency set), `--output-reproducible`,
   kept in a separate `sbom/` artifact so the PyPI publish step only ever sees
   real distributions.
3. **GitHub release job** — new `release` job (needs: publish) attaches
   `dist/*` + the SBOM to a GitHub release with `--verify-tag
   --generate-notes`, so the SBOM is *published*, not buried in a workflow
   artifact.

**Consumer side (`fettle doctor --verify-hashes`):**
4. **`fettle/supply_chain.py`** — `PINNED_TOOLS` canonical home (init_cmd
   re-exports; ci.yml/release.yml/gitlab template mirror the same pins).
   `verify_record()` checks every installed file against the sha256 the wheel's
   RECORD captured at install time — offline, stdlib-only
   (`importlib.metadata` + `hashlib.file_digest`). The trust anchor is pip's
   own hash-verified install.
5. **Severity model**: RECORD hash mismatch = tampering = *required* doctor
   failure (exit 1). Version drift from the pin = warning. Tool not installed
   as a Python distribution in this environment (e.g. uv tool installs) =
   reported as skipped — surfaced, never silently omitted.

## Design decisions

- **Native attestation over standalone cosign** — one maintained action,
  OIDC-only (no keys to manage), provenance stored in the repo's attestation
  log, and the verify story is a single `gh` command.
- **RECORD verification over a checked-in wheel-hash manifest** — wheels are
  per-platform; pinning artifact hashes in-repo would mean a manifest per
  platform per version. RECORD verification is platform-independent, needs no
  maintenance, and detects the actual threat (post-install tampering).
- **SBOM from the smoke venv, not the build env** — the build env contains
  pytest/ruff/semgrep/build noise; the smoke venv is precisely "finefettle and
  what it drags in" (nothing — stdlib-only, which the SBOM now proves).
- **SBOM command verified locally before shipping** — `cyclonedx-py
  environment <python> --output-reproducible -o <file>` exercised in a temp
  venv first; release.yml is tag-triggered and can't be dry-run (lesson from
  the v1.3.0 release incident).

## Verification

- `tests/test_supply_chain.py` — 13 tests: pin canonicity (2), RECORD
  verification via real on-disk fake distributions incl. tamper/missing/no-
  RECORD (4), doctor-check severity contract (5), CLI/doctor wiring (2... 3).
- Live run caught real drift immediately: this venv's ruff distribution is
  0.15.21 vs the 0.15.20 pin → `[warn] supply:ruff version drift`.

## Follow-ups

- Workflow changes take effect on the next tag (v1.3.1+); verify the
  attestation + SBOM + GitHub release on that run before trusting the chain.
- WP-148 (opt-in telemetry) is the last v1.3.x item — next stage.
