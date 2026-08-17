# Installed Artifact Release Contract Implementation Plan

Status: proposed

## 1. Outcome

Make installed live-agent governance a release-blocking product contract. A
release may claim installed support for a host only when the exact wheel built
for publication has passed checkout-independent activation and transport tests,
and the public PyPI artifact has passed a post-publication canary.

This plan strengthens the existing release workflow. It does not replace the
installed bridge, make package installation mutate host settings, or treat a
source-checkout test as installed-artifact evidence.

## 2. User Story And Journey

As a developer installing Fettle from PyPI, I want the documented installation
and activation commands to invoke governance from the installed package, so that
I do not need to discover or maintain a source checkout.

The canonical journey remains:

```bash
pipx install finefettle
cd your-project
fettle init --dry-run
fettle init
fettle doctor
```

Installation provides the CLI. `fettle init` explicitly previews and activates
host governance. No package-manager operation silently changes host settings.

The applicable UX and UAT contracts already exist in
`docs/adoption-conversion.ux-spec.md` and
`docs/installed-bridge-uat-plan.md`. No visual UI specification is applicable.

## 3. Current State And Gap

The release workflow already:

- builds one wheel and sdist in the `build` job;
- installs the candidate wheel outside the checkout;
- runs `fettle init`, validates the bridge, and dispatches one normalized event;
- publishes the retained `dist` artifact through PyPI Trusted Publishing.

The remaining gaps are:

1. The smoke environment uses `venv` plus `pip`, not the documented `pipx`
   boundary.
2. Host-support claims are duplicated in prose rather than derived from one
   validated capability authority.
3. The release does not retain a machine-verifiable contract report binding the
   wheel digest, package version, executable, bridge, hosts, and observations.
4. No post-publication job installs the public PyPI artifact and verifies that
   its digest and behavior match the candidate.
5. Real-host evidence is documented manually and can become stale relative to a
   later release.
6. Publication is irreversible; a failed public canary therefore needs an
   explicit incident path and must block downstream GitHub release/support
   claims rather than pretending the PyPI upload never occurred.

## 4. Assumptions

- PyPI Trusted Publishing remains the publication mechanism.
- The build job remains the sole producer of release distributions.
- GitHub-hosted Linux can verify package, `pipx`, bridge, and synthetic transport
  contracts for all hosts.
- Authenticated real-host sessions may require separate protected or self-hosted
  runners. Missing access remains `blocked`, never `passed`.
- PyPI does not allow replacing an uploaded version. Public-canary failure
  requires yanking the bad version or publishing a corrective version after
  operator review.
- Host activation remains explicit through `fettle init`.

## 5. Design Decision

### Recommended: two-stage contract with one capability authority

1. **Candidate gate before publication:** install the exact wheel with `pipx`
   from its local path, activate every declared installed host in an isolated
   home, invoke each generated transport, and emit a digest-bound report.
2. **Public canary after publication:** install `finefettle==VERSION` from public
   PyPI into a clean environment, verify the downloaded wheel digest equals the
   candidate digest, rerun the activation contract, and only then create the
   GitHub release and expose complete installed-support claims.
3. **Capability authority:** store host support and required evidence classes in
   one reviewed manifest. Validate README/release claims against it; do not
   generate broad marketing prose automatically.

This preserves build-once publication while testing both the artifact and the
actual public distribution path.

### Alternatives rejected

- **README-only clarification:** cheap, but cannot prevent packaging regressions.
- **Public canary only:** detects failure after users can install it and provides
  no pre-publication protection.
- **Require live authenticated sessions for every release:** strongest signal,
  but brittle provider availability would make routine security and compatibility
  releases impossible. Live evidence should expire by host/runtime compatibility,
  while deterministic installed transport conformance blocks every release.
- **Run `fettle init` during `pipx install`:** surprising and unsafe because a
  package manager should not silently mutate unrelated host configuration.

## 6. Evidence Model

Add packaged `fettle/host-capabilities.json` with a strict schema and one record
per host:

```json
{
  "schema_version": "1",
  "hosts": {
    "opencode": {
      "claim": "supported-installed",
      "candidate_contract": "required",
      "public_canary": "required",
      "live_evidence": "required-for-claim",
      "live_evidence_max_age_days": 90
    }
  }
}
```

The manifest declares policy, not outcomes. Release reports provide outcomes.
Do not commit tokens, absolute runner paths, event bodies, prompts, or other
secrets.

The candidate and public reports use a versioned schema containing:

- package name and version;
- wheel filename, SHA-256 digest, and size;
- tested Python, OS, architecture, and `pipx` version;
- assertion that execution occurred outside the checkout;
- installed executable and interpreter identity, normalized to exclude ephemeral
  runner roots from cross-run equality;
- bridge manifest digest and package version;
- per-host registration and transport-conformance outcomes;
- `fettle doctor` result;
- live-evidence reference, host version, observation time, and validity state;
- overall state derived from every required criterion.

Missing, malformed, stale, blocked, skipped, contradictory, or indeterminate
required evidence is a non-pass. A synthetic event proves transport conformance,
not a real authenticated host session.

## 7. Work Packages

### WP1: Freeze schemas and claim semantics

Files:

- Add packaged `fettle/host-capabilities.schema.json`.
- Add `fettle/host-capabilities.json`.
- Add packaged `fettle/installed-artifact-contract.schema.json`.
- Update `docs/installed-governance-bridge.md`.
- Update `docs/adoption-conversion.ux-spec.md` with evidence-state wording if
  needed.

Tasks:

1. Define allowed claims: `supported-installed`, `contract-tested`, `clone-only`,
   `blocked`, and `unsupported`.
2. Define which candidate, public-canary, and live evidence each claim requires.
3. Define live-evidence expiry by host runtime compatibility, with 90 days as the
   initial upper bound rather than the sole validity rule.
4. Define strict report fields, bounded diagnostics, and secret exclusions.
5. Add valid, missing, malformed, stale, and contradictory fixtures.

Verification:

```bash
uv run pytest -q tests/test_host_capabilities.py
uv run ruff check fettle tests
```

Exit: support vocabulary and report validity are executable contracts, not prose.

### WP2: Implement capability and report validation

Files:

- Add `fettle/installed_artifact_contract.py`.
- Add `tests/test_installed_artifact_contract.py`.
- Add fixtures under `tests/fixtures/installed-artifact/`.

Tasks:

1. Load schemas and reject unknown fields or unsupported versions.
2. Validate wheel digest, version, environment, bridge, and per-host outcomes.
3. Derive the overall result from every criterion.
4. Reject expired or runtime-incompatible live evidence for
   `supported-installed` claims.
5. Emit bounded JSON and one actionable failure message.
6. Add a module CLI usable by release automation without importing source from
   the checkout under test.

Verification:

```bash
uv run pytest -q tests/test_installed_artifact_contract.py
uv run fettle check --changed
```

Exit: no incomplete report can validate or authorize a support claim.

### WP3: Create an installed-artifact conformance harness

Files:

- Add `scripts/installed_artifact_canary.py`.
- Add `tests/test_installed_artifact_canary.py`.
- Reuse `tests/fixtures/installed-artifact/`.

Tasks:

1. Accept an explicit wheel path, expected digest, output path, and isolated work
   root.
2. Refuse execution when the work root is inside the repository checkout.
3. Install the wheel through a pinned `pipx` version using `--pip-args` only when
   needed for local candidate installation.
4. Resolve the installed executable and prove its module path is inside the pipx
   environment, not the checkout.
5. Create an isolated home and repository with sentinel host settings.
6. Run `fettle init --dry-run`; prove no host or bridge writes occurred.
7. Run `fettle init`; prove unrelated settings remain and the bridge binds the
   pipx interpreter.
8. Invoke every generated host transport with a normalized violating fixture and
   require observable Fettle output or trace evidence.
9. Run `fettle doctor` and require the expected installed capability states.
10. Emit the schema-valid report atomically.

Verification:

```bash
uv run pytest -q tests/test_installed_artifact_canary.py tests/test_installed_bridge.py
```

Exit: the documented installation boundary is reproduced without a checkout.

### WP4: Make candidate conformance release-blocking

Files:

- Update `.github/workflows/release.yml`.
- Update `tests/test_release_workflow.py`.

Tasks:

1. Pin `pipx` in the release build job.
2. Compute and retain SHA-256 digests immediately after `python -m build`.
3. Replace the inline bridge smoke block with the conformance harness against the
   exact local wheel.
4. Validate the candidate report against capability policy.
5. Upload distributions, digest manifest, candidate report, and SBOM as separate
   immutable artifacts.
6. Make `publish` depend on candidate report success.
7. Keep the existing venv/sdist resource tests where they prove distinct
   packaging behavior.

Verification:

```bash
uv run pytest -q tests/test_release_workflow.py tests/test_installed_artifact_contract.py
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/release.yml")'
```

Exit: PyPI publication cannot start without successful exact-wheel pipx evidence.

### WP5: Verify public PyPI delivery

Files:

- Update `.github/workflows/release.yml`.
- Update `scripts/installed_artifact_canary.py`.
- Update `tests/test_release_workflow.py`.

Tasks:

1. Add `public-canary` after `publish` with bounded retry for PyPI propagation.
2. Download `finefettle==VERSION` from public PyPI without dependency or HTTP
   caches.
3. Verify the public wheel SHA-256 equals the build job's retained digest.
4. Install through clean `pipx` and rerun the same conformance harness.
5. Validate the public report against capability policy.
6. Make GitHub release creation depend on `public-canary` success.
7. Retain candidate and public reports even when the canary fails.

Verification:

```bash
uv run pytest -q tests/test_release_workflow.py tests/test_installed_artifact_canary.py
```

Exit: the public package, not merely a local wheel, reproduces installed governance.

### WP6: Add public-canary incident handling

Files:

- Add `docs/runbooks/public-package-canary-failure.md`.
- Update `.github/workflows/release.yml`.
- Update `SECURITY.md` only if the failure involves a security defect.

Tasks:

1. On public-canary failure, prevent GitHub release creation and support-claim
   publication.
2. Open or update a bounded GitHub Actions summary naming version, digest,
   failed criterion, artifact links, and recovery owner.
3. Require explicit operator approval before yanking a PyPI version; never automate
   deletion or replacement.
4. Document corrective-release steps and how to restore claims only after a new
   public canary succeeds.
5. Add a quarterly drill using a synthetic failed report, not a real bad release.

Verification:

```bash
uv run pytest -q tests/test_release_workflow.py tests/test_installed_artifact_contract.py
```

Exit: a published defect is visible, contained, and cannot become a clean release.

### WP7: Bind documentation claims to capability evidence

Files:

- Add `fettle/capability_claims.py`.
- Add `tests/test_capability_claims.py`.
- Update `README.md`.
- Update `docs/README.md`.
- Update release-note checks in `.github/workflows/release.yml`.

Tasks:

1. Parse only explicitly marked support tables and installation claims.
2. Validate each claimed host and installation mode against
   `fettle/host-capabilities.json` plus the release report.
3. Fail on unsupported, stale, or broader-than-evidence claims.
4. Keep prose authored by humans; generate only compact status tables if doing so
   reduces duplication without degrading readability.
5. State consistently that `pipx install` installs and `fettle init` activates.
6. Require release notes to distinguish `supported-installed`,
   `contract-tested`, and blocked live evidence.

Verification:

```bash
uv run pytest -q tests/test_capability_claims.py tests/test_release_workflow.py
```

Exit: contradictory checkout requirements or unsupported host claims fail CI.

### WP8: Establish live-host evidence lifecycle

Files:

- Add `.github/workflows/host-conformance.yml`.
- Add `docs/runbooks/host-conformance.md`.
- Add `tests/test_host_conformance_workflow.py`.
- Store retained reports as workflow artifacts, not hand-edited pass flags.

Tasks:

1. Run hosts sequentially so terminal outcomes are never shared.
2. Use protected environments for authenticated runners and no secrets in
   artifacts.
3. Bind each observation to package digest, host version, event vocabulary, and
   session evidence.
4. Classify unavailable authentication/provider/runtime as `blocked`.
5. Re-run on host-version changes, bridge changes, before broad support claims,
   and at least every 90 days.
6. Feed only validated retained references into release capability reports.

Verification:

```bash
uv run pytest -q tests/test_host_conformance_workflow.py
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/host-conformance.yml")'
```

Exit: live support claims have fresh, host-specific, non-inferred evidence.

### WP9: End-to-end release rehearsal

Files:

- Update `docs/installed-bridge-uat-plan.md`.
- Add a dated report under `docs/uat/` after execution.
- Update the applicable completion manifest under `docs/completion/`.

Tasks:

1. Build one candidate wheel and record its digest.
2. Run local pipx candidate conformance outside the checkout.
3. Exercise a non-production package index or disposable package name to rehearse
   publication and public retrieval without consuming a real version.
4. Run a synthetic public-canary failure and verify containment.
5. Run available real hosts independently and preserve blockers.
6. Verify README and release-note claim checks against the reports.
7. Run the complete repository quality and completion gates.

Verification:

```bash
uv run pytest -q
uv run ruff check fettle tests
uv run fettle check --changed
uv run fettle config --validate
uv run fettle completion validate
git diff --check
```

Exit: candidate, retrieval, failure, claim, and recovery paths all have retained
evidence before the production workflow is relied upon.

## 8. Blast Radius

| Surface | Risk | Control |
|---|---|---|
| PyPI release latency | Public propagation and pipx add time | Bounded retries and explicit job timeouts |
| Release availability | Provider outage blocks a release | Separate deterministic candidate gate from expiring live-host evidence |
| Support claims | Stale evidence overstates support | Machine policy plus report validation |
| User host settings | Canary could touch real configuration | Isolated HOME/XDG roots and sentinel preservation tests |
| Secrets | Authenticated host evidence could leak data | Protected runners, bounded reports, no prompts/event bodies |
| Artifact identity | Rebuild could differ from tested wheel | One build producer, digest manifest, artifact transfer only |
| Bad public upload | PyPI version cannot be replaced | Block GitHub release, retain evidence, operator-controlled yank/corrective release |
| Existing clone mode | Installed logic could disturb checkout setup | Preserve clone-mode tests and branch explicitly in harness assertions |

## 9. Success Criteria

The initiative is complete only when:

1. The exact wheel sent to PyPI passes local-path `pipx` activation outside the
   checkout.
2. The public PyPI wheel digest equals the candidate digest.
3. The public artifact passes the same bridge and transport contract.
4. Every installed-support claim is admitted by validated, fresh evidence.
5. Missing or blocked real-host evidence cannot become `supported-installed`.
6. Dry-run performs no host writes; init preserves unrelated settings.
7. A simulated public-canary failure blocks GitHub release creation and produces
   an actionable retained report.
8. Full tests, Ruff, workflow parsing, Fettle quality scan, and completion
   validation pass.

## 10. Sequencing And Estimate

Recommended sequence: WP1 -> WP2 -> WP3 -> WP4 -> WP5 -> WP6 -> WP7 -> WP8 ->
WP9.

Estimated engineering effort: 5-8 focused days, excluding waits for authenticated
host access and one production release observation.

Do not combine WP8 provider troubleshooting with candidate artifact work. The
deterministic installed contract should converge independently before live-host
evidence is refreshed.

## 11. Approval Gate

Approval of this plan authorizes implementation work only. Tagging, publishing,
yanking, changing protected environments, using authenticated host accounts, or
creating a GitHub release each requires separate explicit approval.
