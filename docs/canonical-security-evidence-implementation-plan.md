# Canonical Security Evidence Implementation Plan

Status: CS-0-CS-5 authorized and implemented; CS-6 remains evidence- and approval-gated

UX contract: [canonical-security-evidence.ux-spec.md](canonical-security-evidence.ux-spec.md)

## Objective

Graduate the existing security review into a first-party canonical evidence
producer so `[assurance.release.production]` can require security `PASS` without
weakening Assurance Integrity's fail-closed boundary.

## Assumptions And Decisions

- Keep `python -m fettle.security_review`; no second security command or schema.
- Preserve raw JSON compatibility and the 0/1/2 exit contract.
- Treat Ruff and Semgrep observations as external scanner inputs, but treat
  Fettle's bounded orchestration, completeness decision, bindings, and artifact
  construction as the authoritative producer boundary.
- A clean result requires both configured tools to complete. Findings are a
  valid canonical `violation`; missing tools, timeouts, malformed output, and
  persistence failures are non-authoritative `tool_error` outcomes.
- Replace the network-resolved `p/owasp-top-ten` input with an immutable,
  installed ruleset identity before allowing canonical `PASS`. A mutable remote
  alias cannot support reproducible policy binding.
- Derive source and changed scope from repository state. The caller's `--path`
  narrows execution only when it is repository-relative, contained, and covered
  by the canonical scope; it is never accepted as identity by assertion.
- Atomically retain `.fettle/security-review.json` and
  `.fettle/security-review.evidence.json`; invalidate stale authority before a
  new attempt.
- Add all six documented production criteria only after the producer passes its
  technical gates. Enforcement still waits for 20 real shadow assessments and
  explicit operator approval.

## Alternatives

| Approach | Benefit | Cost or risk | Decision |
|---|---|---|---|
| Omit security or allow `UNKNOWN` | Fastest release | Weakens the documented production contract | Rejected |
| Wrap the current mutable Semgrep registry scan | Smallest code change | Policy can drift without source changes; results are not reproducible | Rejected |
| Pin and package the scanner policy, then emit EvidenceArtifact v1 | Reproducible and consistent with existing producers | Adds package data and focused validation code | Selected |

## Work Packages

### CS-0: Freeze Contract And Policy Identity

Files: this plan, `docs/canonical-security-evidence.ux-spec.md`,
`docs/plan-index.md`, and the installed Semgrep policy resource.

- Select and record the exact Semgrep ruleset content and digest.
- Define the producer, report, scope, policy, completeness, and recovery
  projections.
- Confirm no canonical payload contains absolute paths or secret material.

Verification: documentation links, package-data check, and policy digest fixture.

### CS-1: Add Failing Producer Contract Tests

Files: `tests/test_security_review.py`, `tests/test_assurance_integrity.py`, and
focused fixtures under `tests/fixtures/security_evidence/` if needed.

- Cover clean, findings, missing tool, timeout, malformed scanner JSON, wrong
  source, wrong policy, wrong scope, wrong producer, tamper, stale replacement,
  and clone portability.
- Exercise the final Assurance security dimension, not only helper functions.

Verification: focused tests fail for the intended missing authority behavior.

### CS-2: Produce Canonical Security Evidence

Files: `fettle/security_review.py` and the installed Semgrep policy resource.

- Normalize scanner output to repository-relative portable paths.
- Derive source snapshot, revision, effective-policy digest, and canonical scope.
- Emit `fettle.security.review` EvidenceArtifact v1 with a bounded summary
  payload and producer implementation/ruleset identity.
- Retain the raw report and sidecar atomically; invalidate stale sidecars before
  execution and on any write failure.

Verification: `uv run pytest tests/test_security_review.py -q`.

### CS-3: Consume Security Evidence At The Assurance Boundary

Files: `fettle/assurance.py` and `tests/test_assurance_integrity.py`.

- Validate the raw report's canonical reference and exact evidence context.
- Map valid `pass` to `PASS`, valid `violation` to `FAIL`, and every invalid or
  indeterminate state to `UNKNOWN`.
- Add the accepted sidecar as a parent of the Assurance Record artifact.

Verification: focused assurance and adversary tests.

### CS-4: Configure Shadow Production Policy

Files: `.fettle.toml`, `docs/plan-index.md`, and a new append-only shadow
assessment log under `docs/engagement/`.

- Configure authorization, policy integrity, security, behavior, independence,
  and provenance exactly as documented.
- Keep the policy observational; do not add a release workflow gate yet.
- Record assessment subject, outcome, dimension differences, classification,
  and evidence references for each real change.

Verification: configuration validation and a fail-closed local production
assessment with missing prerequisites.

### CS-5: Technical Verification And Dogfood

Files: tests and UAT record only as failures require.

- Run focused producer, Assurance, adversary, and CLI suites.
- Run the complete test, Ruff, configuration, completion, and Fettle gates.
- Build the wheel and verify source-tree and isolated installed-wheel behavior.
- Perform the CLI journey for clean, findings, missing-tool, stale, and tampered
  states after the required review break.

Verification:

```bash
uv run pytest tests/test_security_review.py tests/test_assurance_integrity.py tests/test_assurance_adversary.py tests/test_cli.py -q
uv run pytest -q
uv run ruff check fettle tests
uv run fettle config --validate
uv run fettle completion validate
uv run fettle check --changed
uv build
```

### CS-6: Shadow Graduation And Release

Files: shadow assessment log, UAT record, completion evidence, and release
artifacts.

- Collect 20 real assessments from distinct qualifying changes; fixtures and
  repeated unchanged runs do not count.
- Classify every difference as intentional hardening or defect and resolve all
  unexplained differences.
- Present the evidence for explicit operator approval.
- Only after approval, add the release enforcement hook, merge through protected
  `main`, tag `v1.13.1`, and monitor the trusted-publishing workflow through the
  public PyPI canary and GitHub release.

Verification: 20 accepted rows, operator decision, required PR checks, release
workflow success, and public `finefettle==1.13.1` installation.

## Blast Radius

- Security CLI output persistence and package resources.
- Source, effective-policy, and changed-scope identity calculations.
- Assurance security status and Assurance Record parent references.
- Repository production policy and later release enforcement.
- Release wheel contents and installed-artifact checks.

`kgraph impact .fettle.toml` currently reports a stale index and only the config
file itself. Refresh the index and rerun impact queries for each runtime file
before CS-1 implementation; do not rely on the stale result.

## Success And Stop Conditions

- No canonical security false pass in contract or adversary tests.
- A valid finding remains `FAIL`; tooling uncertainty remains `UNKNOWN`.
- The policy and ruleset are immutable, installed, and digest-bound.
- Equivalent clones produce portable equivalent bindings.
- The raw report remains compatible.
- All technical gates and installed-wheel UAT pass.
- Stop before enforcement or release if fewer than 20 real assessments exist,
  any difference is unexplained, or operator approval is absent.

## Estimate

Engineering: 3-5 days. Graduation: the time required to observe 20 real
qualifying changes; it cannot be compressed with synthetic repetition.
