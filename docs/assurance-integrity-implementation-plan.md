# Assurance Integrity Implementation Plan

Status: AI-0 and AI-1 authorized; production implementation not authorized

UX contract: [assurance-integrity.ux-spec.md](assurance-integrity.ux-spec.md)

Historical baseline: [assurance-record-plan.md](assurance-record-plan.md)

## Objective

Make `fettle assurance --policy NAME` a strict authority boundary: it may
authorize a release only when every required result is canonical, complete,
valid for the exact subject, effective policy, and scope, and internally
consistent. Missing, malformed, stale, conflicting, or incorrectly bound
evidence remains a visible non-pass.

This program hardens the existing command and Assurance Record shape. It does
not add `fettle assess`, introduce another evidence schema, or alter producer
report formats.

## User Story And Flow

As a release owner, I want one evidence-linked decision for the exact change I
am releasing, so stale, forged, incomplete, contradictory, or misbound evidence
cannot authorize it.

```text
initialize policy -> diagnose producer readiness -> run evidence producers
    -> fettle assurance --policy NAME -> inspect decision and reasons
    -> rerun named producer or correct configuration -> reassess
```

The common path remains one non-interactive command. Human and JSON output come
from the same result, with exit 0 for policy PASS, 1 for a valid policy FAIL,
and 2 for configuration, environment, or malformed-authority errors.

## Authority Boundary

| Layer | Owns | Does not own |
|---|---|---|
| Assurance kernel | Subject, effective-policy and scope identity; artifact validation; cross-artifact consistency; applicability; completeness; policy decision; canonical Assurance Record | Producer execution or domain observations |
| First-party producers | Verify, CI, mutation, UAT, security, coverage, and agent-bridge observations | Release authorization |
| Extensions | Orchestration, graph views, LSP, compliance presentation, telemetry, and experimental capabilities | Authority unless separately graduated into the kernel |

The frozen `EvidenceArtifact` v1 contract remains the canonical observation
envelope. Domain reports retain their stronger invariants and are referenced,
not flattened or silently reinterpreted.

## Assumptions And Decisions

- Preserve unqualified `fettle assurance --json` compatibility and the current
  Assurance Record schema while hardening its evidence semantics.
- Do not add `--schema-version` until a concrete external consumer requires an
  incompatible record shape and a documented migration window exists.
- Existing raw producer reports and stamps remain readable diagnostics. A
  consequential PASS requires their canonical sidecar and domain validation.
- Invalid canonical evidence maps to `UNKNOWN`; valid canonical negative
  evidence maps to `FAIL`; only valid, complete, admitted positive evidence may
  map to `PASS`.
- Derive the subject and scope from Git and source snapshots. Caller-provided
  changed paths are never authoritative.
- Digest the effective layered policy returned by the canonical resolver, not
  only `.fettle.toml`.
- CI, UAT, mutation, and authorization applicability comes from policy and
  execution context. Artifact absence alone never establishes
  `NOT_APPLICABLE`.
- Security remains `UNKNOWN` for release authority until a canonical security
  producer exists. The retained raw security review may still explain findings.
- Preserve P80-P83 as historical delivery records. This successor program
  corrects their aggregate authority boundary rather than erasing completed
  work.

## Confirmed Integrity Gaps

| Gap | Current weakness | Required result |
|---|---|---|
| Mutation | `status = completed` can pass without the domain `passed` result | Validate the canonical wrapper and complete domain outcome |
| Verify | A revision-bound raw stamp can pass without its sidecar | Validate `fettle.verify` through the producer contract |
| CI | A revision-bound raw status can pass without its sidecar | Validate `fettle.ci` through the producer contract |
| Policy | Integrity considers `.fettle.toml` only | Bind the canonical effective layered policy |
| Scope | Supplied `changed_files` is accepted as proof | Derive and validate canonical repository scope |
| Provenance | Any parseable anchor passes | Verify chain, anchor prefix, commit, and post-anchor drift policy |
| UAT | Sidecar parsing omits full common-context validation | Validate artifact and UAT report/session reconciliation |
| Security | Unbound raw JSON can pass | Remain non-pass until canonical security evidence exists |
| Stages | Declared and emitted inventories differ | Freeze one tested stage inventory |
| Portability | Absolute root enters canonical content | Use repository-relative references and portable identities |
| Persistence | CLI does not invoke canonical persistence | Atomically persist the evaluated record without stale-success ambiguity |
| Adversary | Tests validators separately from final authority | Attack the complete `fettle assurance` decision path |

## Work Packages

### AI-0: Freeze Acceptance Semantics

Files: this plan, `docs/assurance-integrity.ux-spec.md`,
`docs/assurance-record-plan.md`, and `docs/plan-index.md`.

- Define subject, policy, scope, applicability, completeness, and validity
  mappings without changing the record's public shape.
- Freeze one stage inventory and the producer-to-dimension mapping.
- Record raw-report compatibility as diagnostic-only at the authority boundary.
- Add the integrity BDD scenarios before behavior changes.

Verification: `uv run fettle spec lint` and `uv run fettle completion validate`.

Estimate: 1 day.

### AI-1: Add Final-Boundary Regression Fixtures

Files: `tests/test_assurance_record.py`,
`tests/test_assurance_adversary.py`, and
`tests/fixtures/assurance_integrity/`.

- Add completed-but-failed mutation, missing sidecar, forged anchor,
  wrong-source, wrong-policy, wrong-scope, unsupported-producer, partial,
  superseded-pass, and clone-location fixtures.
- Exercise `build_assurance_record`, policy evaluation, and the CLI rather than
  only individual validators.
- Confirm each new test fails for the intended authority weakness before the
  implementation changes.

Verification: `uv run pytest tests/test_assurance_record.py
tests/test_assurance_adversary.py tests/test_cli.py -q`.

Estimate: 1-2 days.

### AI-2: Establish Strict Consumer Context

Files: `fettle/assurance.py`, `fettle/source_snapshot.py`,
`fettle/changeset.py`, `fettle/config.py`, and focused tests for those modules.

- Resolve a committed or working source snapshot through existing snapshot
  APIs; fail visibly when it cannot be built.
- Derive repository-relative scope and its canonical digest.
- Resolve and digest the effective layered policy once per assessment.
- Build one `EvidenceValidationContext` per admitted producer from those exact
  identities.
- Reject absolute paths, escapes, duplicate occurrences, and conflicting
  artifact identities.

Verification: focused source, changeset, config, and assurance tests.

Estimate: 2 days.

### AI-3: Harden Verify And CI Consumption

Files: `fettle/assurance.py`, `fettle/verify_gate.py`, `fettle/ci_gate.py`,
and their existing tests.

- Expose or reuse producer-owned canonical validation without duplicating its
  rules in the aggregator.
- Treat raw stamps as diagnostics only.
- Preserve a valid negative result as `FAIL`; map absent or invalid canonical
  evidence to `UNKNOWN` with the exact rerun command.

Verification: assurance, verify-gate, and CI-gate test suites.

Estimate: 1-2 days.

### AI-4: Harden Mutation And UAT Consumption

Files: `fettle/assurance.py`, `fettle/mutation_test.py`,
`fettle/uat/reconcile.py`, and their existing tests.

- Require a complete, canonical mutation wrapper and successful domain result;
  distinguish product violation from tool error.
- Require canonical UAT report evidence, exact report/session bindings,
  complete reconciliation, and no unresolved evaluator result.
- Ensure newer conflicting evidence supersedes an older pass deterministically.

Verification: assurance, mutation contract, UAT artifact, session, and
reconciliation tests.

Estimate: 2-3 days.

### AI-5: Harden Provenance, Authorization, And Security

Files: `fettle/assurance.py`, `fettle/evidence_ledger.py`, and focused tests.

- Use `verify_chain()` and `verify_anchor()` and bind the anchor to the assessed
  commit.
- Distinguish unanchored, drifted, and tampered provenance.
- Derive authorization applicability from explicit session/delegation context.
- Keep raw security reports explanatory but non-authoritative until a separate
  canonical producer work item is approved.

Verification: ledger, capsule, security, assurance, and adversary tests.

Estimate: 1-2 days.

### AI-6: Persist The Portable Record

Files: `fettle/assurance.py`, `fettle/cli.py`, `tests/test_assurance_record.py`,
and `tests/test_cli.py`.

- Remove absolute checkout identity from canonical digest content while
  preserving useful local display context outside it.
- Persist `.fettle/assurance-record.evidence.json` atomically after assessment.
- Represent the persisted assessment with `EvidenceArtifact` v1 and parent
  references to every accepted canonical producer artifact.
- Ensure failed persistence cannot leave an older record appearing current.
- Preserve command syntax, JSON compatibility, human/JSON agreement, and exit
  codes.

Verification: CLI contract, portability, interrupted-write, stale-record, and
round-trip evidence tests.

Estimate: 2 days.

### AI-7: Record-Level Adversary And Dogfood

Files: `tests/test_assurance_adversary.py`, `examples/assurance-record/`,
`README.md`, `CHANGELOG.md`, and milestone completion evidence.

- Route every adversarial case through the final policy decision.
- Prove equivalent clones produce the same canonical digest.
- Assess Fettle's own final change from the source tree and an installed wheel.
- Run the full repository suite and required quality gates.
- Collect at least 20 shadow assessments and classify every changed v1 decision
  as intentional hardening or a defect before enforcement graduation.

Verification:

```bash
uv run pytest tests/test_assurance_record.py tests/test_assurance_adversary.py tests/test_cli.py -q
uv run pytest -q
uv run ruff check fettle tests
uv run fettle config --validate
uv run fettle check --changed
uv run fettle completion validate
uv run fettle assurance --policy production
```

Estimate: 2 days plus the shadow-observation window.

## Sequencing And Blast Radius

```text
AI-0 contract -> AI-1 failing boundary tests -> AI-2 shared context
    -> AI-3 verify/CI + AI-4 mutation/UAT + AI-5 provenance/auth/security
    -> AI-6 persistence and CLI -> AI-7 dogfood and graduation
```

Runtime blast radius includes the Assurance Record, verify and CI canonical
validation, mutation and UAT report consumers, source snapshots, effective
configuration, Git scope discovery, provenance, CLI output, and persisted
evidence. Producer report formats are outside scope. The pre-plan `kgraph`
impact query reported only the changed planning files, but its index was stale;
refresh the index and rerun impact analysis before AI-1 implementation.

Estimated engineering effort: 11-16 days plus shadow observation.

## Graduation Gates

- Zero false passes in the record-level adversary suite.
- Missing or invalid canonical producer evidence never produces PASS.
- Valid negative producer evidence remains FAIL rather than UNKNOWN.
- Subject, effective policy, scope, producer, and occurrence conflicts are
  visible and non-pass.
- Equivalent clone locations produce the same canonical record digest.
- Human and JSON policy decisions agree and existing JSON consumers remain
  compatible.
- Persistence is atomic and cannot expose a stale record as current.
- Focused tests, full tests, Ruff, configuration validation, Fettle quality
  scan, completion validation, source-tree dogfood, and installed-wheel UAT pass.
- Twenty shadow assessments contain no unexplained decision differences.
- Operator explicitly authorizes enforcement and closure.

## Deferred First-Party UAT Package

After Assurance Integrity graduates, evaluate a separately versioned
`finefettle-uat` first-party distribution. Core should consume its canonical
UAT evidence like any other producer; the package should own hermetic startup
and readiness, deterministic fixtures and fault injection, process cleanup,
incremental checkpoints, browser/model probes, diagnostics, independent
artifacts, and adaptive risk-guided exploration.

The measurable promise is: cover every discovered reachable workflow and state
within the declared persona, environment, fixture, and budget matrix; report
blocked, uncovered, and unknown areas explicitly; and compare defect discovery
against skilled humans. It must not claim coverage of unknowable workflows.

Do not require containers initially. A process-based runtime contract is the
smallest adequate boundary; container providers require a demonstrated
isolation or reproducibility need.

No extraction or new UAT enforcement is authorized by this plan.

## Program Constraint

Until Assurance Integrity graduates, do not start unrelated feature programs.
Maintenance and defects continue. Any exception must show that it reduces false
assurance, improves evidence validity, or materially improves explanation of a
trust decision.
