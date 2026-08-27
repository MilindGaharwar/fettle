# State Consistency Contracts Implementation Plan

Status: PROPOSED; implementation requires package-by-package acceptance

Related documents:

- [UX and UAT contract](state-consistency.ux-spec.md)
- [Fettle evolution implementation plan](fettle-evolution-implementation-plan.md)
- [Fettle roadmap](ROADMAP.md)
- [Configuration reference](CONFIG.md)

## 1. Outcome

### User Story

As an application developer or test engineer, I want to declare a business
state mutation and every surface that must reflect it, so Fettle can detect
cross-view divergence, stale reads, missing propagation, and temporal overwrite
without treating infrastructure failure or intentional snapshots as defects.

### User Flow

```text
identify one high-value business fact
              |
              v
declare owner, mutation, canonical read, observers, and consistency model
              |
              v
lint contract and adapter capabilities
              |
              v
run isolated mutation -> canonical read -> observer checks -> cleanup
              |
              v
review converged, divergent, stale, unknown, or tool-error evidence
              |
              v
repair application or contract, rerun, and retain advisory history
              |
              v
graduate only after precision, runtime, and flake thresholds pass
```

## 2. Problem Definition And Vocabulary

The program uses `state divergence` as the umbrella category. Findings use the
narrowest evidenced label:

| Label | Meaning |
|---|---|
| `cross-view-state-inconsistency` | Two declared current-state observers disagree after a successful mutation |
| `stale-read` | An observer retains a superseded value beyond its declared consistency deadline |
| `temporal-state-divergence` | An older operation or response overwrites a newer committed value |
| `duplicate-source-of-truth` | Static or declared ownership evidence shows multiple independently writable owners; advisory until confirmed |
| `missing-invalidation` | Suggested diagnosis only when repository-owned evidence explicitly proves the invalidation dependency |
| `consistency-tool-error` | The runner or adapter failed, timed out, or produced malformed evidence |
| `unknown` | Canonical expected state or required comparison could not be established |

Findings separate observation from diagnosis. Fettle reports that two surfaces
diverged; it does not claim a cache bug solely because one value was stale.

## 3. Assumptions And Boundaries

1. Arbitrary business semantics cannot be inferred reliably from source code.
   Explicit repository-owned contracts are authoritative.
2. The canonical read establishes expected state after the mutation. A mutation
   response alone is insufficient unless the contract explicitly makes it the
   canonical read and tests that choice.
3. At most one logical writable owner is declared for one fact. Replicas,
   projections, local component state, and immutable snapshots are observers.
4. Intentional snapshots and bounded eventual consistency are first-class and
   must not be forced into immediate equality.
5. Core Fettle remains Python 3.11+ with no new runtime dependency. Browser and
   property-based integrations remain optional extras or repository commands.
6. No application, browser, container, or network action runs in normal edit
   hooks. Consistency execution is minutes-world CLI/CI work.
7. Contracts reference argv arrays or named adapters. They do not embed shell
   strings, Python expressions, JavaScript, SQL, or credentials.
8. Secret values are supplied by environment or repository-native credential
   mechanisms and are never serialized into contracts or retained evidence.
9. Contract runs use unique test identities and deterministic cleanup. A
   contract that cannot isolate or safely retry its mutation cannot graduate.
10. P33 result integrity governs all outcomes. P35 recorded overrides are a
    prerequisite for enforcement. P38 traceability is required before executed
    consistency evidence can satisfy a specification obligation.
11. Static duplicate-state heuristics are advisory. They cannot prove semantic
    equivalence or writable ownership in the general case.
12. The first implementation targets API and CLI command adapters. Browser
    journeys reuse the optional UAT/Playwright substrate only after core
    contracts are stable.

## 4. Decisions And Tradeoffs

| Decision | Alternative rejected | Reason |
|---|---|---|
| Explicit contracts | Infer relationships from matching field names | Names do not prove identity, ownership, or expected propagation |
| Canonical read after mutation | Trust mutation response as expected value | Accepted writes may not persist, normalize, or commit |
| Repository-owned adapters | Build a universal UI/API DSL | Reuses native test setup and avoids an unsafe expression language |
| Declarative orchestration kernel | Require every team to hand-write only E2E tests | Enables consistent evidence and reporting without replacing native tests |
| Four consistency models | Assume immediate equality | Avoids false positives for projections and snapshots |
| Fingerprints and redacted summaries | Persist raw values and payloads | Minimizes sensitive-data exposure while preserving comparison evidence |
| Advisory static heuristics | Block duplicate-looking state automatically | Static ownership inference is incomplete and framework-specific |
| Stateful generators as optional | Add Hypothesis to core dependencies | Preserves zero-dependency core and lets repositories choose generators |
| Start API/CLI, add browser later | Lead with browser automation | Separates semantic contracts from selector and environment flakiness |

## 5. Proposed Contract

The exact serialization is frozen in SC1 before execution code. A representative
shape is:

```yaml
fettle-consistency: v1
id: customer-name-propagates
title: Customer name propagates to checkout
scope:
  - app/customer/**
  - app/checkout/**
fact: customer.display_name
owner: customer-service
consistency:
  model: immediate
  deadline_ms: 30000
  poll_interval_ms: 1000
setup:
  adapter: commands.create_test_customer
mutation:
  adapter: commands.rename_customer
  retry_safe: false
canonical_read:
  adapter: commands.read_customer
observers:
  - id: checkout
    surface: api
    adapter: commands.read_checkout_customer
comparator:
  kind: normalized
cleanup:
  adapter: commands.delete_test_customer
redaction:
  retain_values: false
```

Contract identity covers canonical serialization, referenced adapter manifests,
comparator configuration, and consistency policy. Runtime secrets and generated
test values do not alter contract identity but are excluded from retained data.

## 6. Canonical Data And Result Model

SC1 defines immutable, versioned records for:

- `ConsistencyContract`: identity, fact, owner, source scope, adapters,
  comparator, consistency model, bounds, redaction, and cleanup policy.
- `AdapterManifest`: stable name, argv template or native-test reference,
  required inputs, output grammar, capability, timeout, and implementation
  digest.
- `OperationEvidence`: operation ID, phase, start/end, exit, bounded output
  digest, produced observation fingerprint, and error state.
- `Observation`: observer, surface, normalized type, redacted summary,
  fingerprint, timestamp, and provenance.
- `ConsistencyRun`: source revision, contract/policy/adapter digests, mutation,
  canonical observation, observer outcomes, cleanup, and final state.
- `ConsistencyOutcome`: `converged`, `divergent`, `stale`, `temporal_divergence`,
  `not_applicable`, `unknown`, `tool_error`, or `config_error`.

Canonical encoding follows existing graph-contract rules: UTF-8, normalized
repository-relative paths, stable key/order semantics, full SHA-256 identities,
unknown-field rejection where digest semantics could change, and bounded text.

## 7. Authoritative Activity Sequence

| ID | Activity | Depends on | Estimate | State |
|---|---|---|---:|---|
| SC0 | UX/UAT contract and implementation plan | P33 | 1-2 days | Complete when accepted |
| SC1 | Freeze contract, adapter, evidence, and result schemas | SC0, P33 | 3-5 days | Complete |
| SC2 | Add contract discovery, lint, list, and init template | SC1 | 3-5 days | Complete |
| SC3 | Build bounded API/CLI execution kernel | SC2 | 5-8 days | Complete |
| SC4a | Add exact/normalized immediate/eventual evaluator | SC3 | 4-6 days | Complete |
| SC4b | Add snapshot, monotonic, and temporal schemas/evaluation | SC4a | TBD | Proposed |
| SC5 | Add cross-view web/UAT adapter | SC3, SC4 | 5-8 days | Proposed |
| SC6 | Add optional stateful sequence generation | SC3, SC4 | 5-8 days | Proposed |
| SC7 | Add duplicate-state and invalidation heuristics | SC1, measured corpus | 5-8 days | Evidence-gated |
| SC8 | Bind specs, reports, and changed-scope CI selection | P35 complete, P38 complete, SC4 | 5-8 days | Blocked on P35 -> P38 |
| SC9 | Advisory pilot and graduation decision | SC5-SC8 as applicable | 20+ repositories or 30 qualifying runs | Evidence-gated |

```text
SC0 UX/UAT
  |
  v
SC1 contracts --> SC2 authoring --> SC3 execution --> SC4 evaluation
                                      |                 |
                                      +--> SC5 web -----+
                                      +--> SC6 stateful-+
SC1 + measured corpus --------------------> SC7 heuristics
P35 + P38 + SC4 --------------------------> SC8 CI/traceability
SC5-SC8 evidence -------------------------> SC9 graduation
```

No activity is authorized merely because it appears here. SC1 should be the
first package considered for acceptance. SC3 and later require a separate
proposal review after real contract fixtures validate SC1/SC2 ergonomics. SC8
is a separate blocked track: this program does not implement or bypass P35 or
P38, and specification/CI binding cannot begin until both have graduated.

## 8. Work Packages

### SC1: Canonical Contracts And Adversarial Fixtures

Goal: freeze semantics before building runners or framework integrations.

Primary files:

- `fettle/consistency_types.py` (new)
- `fettle/consistency_contract.py` (new)
- `tests/test_consistency_types.py` (new)
- `tests/test_consistency_contract.py` (new)
- `tests/fixtures/state_consistency/contracts/` (new)

Implementation slices:

1. Define immutable records and versioned canonical JSON encoding.
2. Define adapter-reference grammar without executable implementation.
3. Define immediate, bounded-eventual, immutable-snapshot, and monotonic
   semantics, including valid deadlines and polling bounds.
4. Define exact, normalized, subset, set, numeric-tolerance, and named-predicate
   comparator manifests without executing predicates.
5. Reject duplicate observer IDs, missing canonical read, multiple owners,
   inline secrets, shell strings, path escapes, unknown fields, unsafe retry,
   unbounded deadlines, and cleanup contradictions.
6. Add adversarial Unicode, path, insertion-order, oversized-output, malformed,
   secret-bearing, snapshot, eventual, and temporal fixtures.

Acceptance:

- Identical semantic input has the same identity across process and checkout.
- Invalid contracts fail before any executable action.
- A snapshot contract is distinguishable from a current-state equality contract.
- A monotonic contract declares a typed order or repository-owned predicate and
  rejects any observer transition that moves backward in that order; equality
  is allowed unless the contract explicitly requires strict progress.
- Unknown fields cannot silently alter digest or execution semantics.
- SC1 introduces no subprocess, browser, network, or application execution.

Verification:

```bash
uv run python -m pytest tests/test_consistency_types.py tests/test_consistency_contract.py -q
uv run python -m ruff check fettle/consistency_types.py fettle/consistency_contract.py tests/
fettle check --changed
```

### SC2: Discovery And Authoring UX

Goal: make contracts easy to create and validate without guessing application
semantics.

Primary files:

- `fettle/consistency_contract.py`
- `fettle/consistency_cli.py` (new)
- `fettle/cli.py`
- `fettle/_templates/consistency-contract.yml` (new)
- `fettle/_resources.py`
- `MANIFEST.in`
- `tests/test_consistency_cli.py` (new)
- `tests/test_resources.py`
- `docs/CONFIG.md`

Implementation slices:

1. Discover contracts by marker and schema, not filename alone.
2. Add `init`, `list`, and `lint` with stable human and JSON output.
3. Generate one commented example with unresolved placeholders; never infer
   owner, observer, credentials, or consistency model.
4. Report first-time, filtered-empty, valid, invalid, offline-capability, and
   stale-schema states from the UX contract.
5. Package the template in wheel and sdist smoke tests.

Acceptance:

- A new repository can generate and lint a template without optional extras.
- Lint performs no mutation or application startup.
- Every error includes contract location, consequence, and correction.
- Human output is usable with `NO_COLOR=1`; JSON is stable and deterministic.

### SC3: Bounded API And CLI Execution Kernel

Goal: execute repository-owned operations while preserving fail-visible
evidence and deterministic cleanup.

Primary files:

- `fettle/consistency_runner.py` (new)
- `fettle/tool_runner.py`
- `fettle/environment.py`
- `fettle/consistency_cli.py`
- `tests/test_consistency_runner.py` (new)
- `tests/fixtures/state_consistency/apps/` (new)

Implementation slices:

1. Resolve adapter argv and working directory inside the repository.
2. Generate unique run/subject IDs without exposing them in telemetry.
3. Execute setup, mutation, canonical read, observers, and cleanup as explicit
   phases with independent deadlines and bounded outputs.
4. Parse versioned JSON observations and reject malformed or oversized output.
5. Run cleanup after success, failure, timeout, or cancellation; represent
   cleanup failure separately without overwriting the primary result.
6. Record source revision, dirty-tree identity, policy, contract, adapter, and
   command digests in a portable evidence bundle.

Acceptance:

- Mutation failure cannot produce observer consistency evidence.
- Missing/malformed canonical evidence is `unknown` or `tool_error`, never pass.
- Paths, argv, environment, time, output, and process groups are bounded.
- Retries occur only for phases declared safe.
- A seeded mini-application reproduces one real stale-read defect.

### SC4: Comparison And Consistency Evaluation

Implementation status: SC4a is complete for the frozen v1 exact/normalized and
immediate/eventual schema. Snapshot, monotonic, and two-operation temporal
evaluation are deferred to SC4b and require a separate schema review.

Goal: turn observations into deterministic outcomes without guessing root cause.

Primary files:

- `fettle/consistency_compare.py` (new)
- `fettle/consistency_runner.py`
- `fettle/finding.py`
- `tests/test_consistency_compare.py` (new)
- `tests/test_consistency_runner.py`

Implementation slices:

1. Implement typed built-in comparators over canonical observation values.
2. Evaluate immediate consistency after canonical state is established.
3. Evaluate bounded eventual consistency with declared polling and deadline.
4. Evaluate immutable snapshots against capture predicates, not current values.
5. Evaluate monotonic and two-operation temporal probes.
6. Emit observed labels separately from optional likely-cause hints.

Acceptance:

- Equal values of incompatible types do not compare accidentally.
- Eventual convergence records duration and does not emit an intermediate
  violation.
- Deadline expiry emits stale/divergent evidence with the last observation.
- An older delayed response overwriting a newer value is reproducible.
- Comparator failure is not represented as application divergence.

### SC5: Cross-View Web And UAT Adapter

Goal: exercise the mutation and observers through user-visible browser journeys
while reusing the optional Playwright/UAT substrate.

Primary files:

- `fettle/uat/consistency.py` (new)
- `fettle/uat/session.py`
- `fettle/uat/surfaces.py`
- `fettle/consistency_runner.py`
- `tests/test_uat_consistency.py` (new)
- `tests/fixtures/state_consistency/web_app/` (new)

Implementation slices:

1. Define named repository-owned browser journeys with role/label/text locators.
2. Require the mutation journey to observe a successful user outcome.
3. Navigate or reload before observers so shared in-memory component state does
   not falsely satisfy the test unless the contract explicitly tests it.
4. Support session-bound and fresh-session observers as distinct modes.
5. Capture bounded traces/screenshots only on explicit retention policy and
   redact configured fields before persistence.
6. Add manual fallback instructions when browser automation is unavailable.

Acceptance:

- Update Screen A -> navigate Screen B -> observe persisted value runs against
  the real application boundary, not mocked component state.
- Ambiguous/missing accessible locators are `tool_error`, not stale-read.
- Keyboard-only, `NO_COLOR`, browser restart, reload, and offline states have
  explicit UAT evidence.
- Browser adapter remains an optional extra and does not change core install.

### SC6: Stateful Sequence Testing

Goal: detect order-dependent and race-sensitive divergence beyond fixed
journeys.

Primary files:

- `fettle/consistency_sequences.py` (new)
- `fettle/consistency_runner.py`
- `tests/test_consistency_sequences.py` (new)
- `docs/CONFIG.md`

Implementation slices:

1. Define a small operation vocabulary: setup, mutate, observe, reload,
   invalidate, restart, delay, and cleanup.
2. Support deterministic seeded sequences in core without a generator library.
3. Add an optional Hypothesis adapter supplied through a development/test extra.
4. Shrink or minimize failing sequences while retaining original evidence.
5. Enforce operation count, wall time, generated subject count, and cleanup
   bounds.
6. Include write-read, write-reload-read, cross-API read, restart-read,
   A-then-B-delayed-A, and concurrent-observer seed sequences.

Acceptance:

- Every failure records a deterministic seed and minimized rerun.
- A race fixture is found by at least one retained deterministic sequence.
- Generator exhaustion or shrink failure cannot become a pass.
- Stateful testing remains advisory and outside the blocking PR path initially.

### SC7: Duplicate-State And Invalidation Heuristics

Goal: identify likely architectural risks before runtime evidence, without
claiming semantic proof.

Primary files:

- `fettle/consistency_static.py` (new)
- `rules/state-consistency.yml` (new only for evidenced patterns)
- `tests/test_consistency_static.py` (new)
- `tests/fixtures/state_consistency/static/` (new)

Candidate signals:

- Server-derived props copied into writable local state without a declared
  synchronization boundary.
- Query or entity mutation without an associated invalidate/update operation in
  supported framework APIs.
- The same declared fact mapped to multiple write adapters.
- Persisted derived values where the contract declares computation from a
  canonical owner.
- Observer adapters that read a store different from the declared owner without
  a consistency model.

Acceptance:

- Every heuristic has fire, silent, malformed, and held-out fixtures.
- Findings say `possible duplicate state` or `possible missing invalidation`.
- Promotion requires measured precision above 95% on at least 100 reviewed
  findings per framework; otherwise the rule remains opt-in or is removed.
- Static findings never substitute for runtime consistency evidence.

### SC8: Specification, Report, And CI Binding

Goal: connect consistency evidence to governed behavior and run only relevant
contracts in CI.

Primary files:

- `fettle/spec_model.py`
- `fettle/spec_audit.py`
- `fettle/semantic.py`
- `fettle/report.py`
- `fettle/changeset.py`
- `.github/workflows/consistency.yml` (new if separate execution is justified)
- `tests/test_spec_audit.py`
- `tests/test_semantic.py`
- `tests/test_report.py`

Implementation slices:

1. Allow active scenarios to reference consistency contract IDs through stable
   markers without changing existing GWT grammar silently.
2. Bind executed outcomes to source revision, spec/scenario, contract, policy,
   adapters, and evidence ID.
3. Select contracts by changed governed scope; run a scheduled full set.
4. Report convergence latency, divergence, unknown, tool errors, flakes,
   overrides, and stale evidence separately.
5. Route enforcement exceptions through P35's actor/reason/expiry schema.
6. Keep contract execution advisory until SC9 graduation.

Acceptance:

- A declared but unexecuted contract counts as linked, not verified.
- Failed, skipped, stale, or superseded evidence cannot satisfy a scenario.
- Changed-scope selection is conservative and reports uncertainty.
- CI artifacts are bounded, redacted, retained, and independently reproducible.

### SC9: Pilot And Graduation

Goal: decide from evidence whether each surface and contract class is useful
enough to enforce.

Pilot requirements:

1. At least 20 representative repositories or 30 qualifying advisory runs,
   including API, CLI, and web where supported.
2. At least five seeded divergence controls: duplicate writable state, missing
   invalidation, stale local state/closure, delayed old response, and intentional
   snapshot negative control.
3. At least three runs per contract class to measure flakes and runtime.
4. Human review of every reported divergence and tool error.

A qualifying run has an immutable source revision, valid contract and policy
digests, pinned adapter implementations, complete bounded evidence, successful
cleanup, and a manually assigned expected outcome. Cancelled, stale,
superseded, malformed, and infrastructure-failed runs remain visible but are
excluded from the precision denominator and reported separately.

Graduation thresholds:

- Seeded-defect recall: 100% for the supported contract class.
- False-block rate: below 1% over at least 30 qualifying deterministic runs,
  calculated as manually confirmed clean runs reported non-pass divided by all
  manually confirmed clean qualifying runs.
- False-pass rate: zero across the required seeded-defect controls, calculated
  as seeded divergent runs reported converged divided by all valid seeded
  divergent runs.
- Tool-error and unknown states remain visible and reproducible.
- p95 immediate contract runtime below 60 seconds; changed-scope CI remains
  outside or parallel to the 12-minute blocking critical path until proven.
- Browser flake rate below 2% across three environments before any enforcement.
- Cleanup success above 99%; any leaked test data blocks graduation.
- Security review finds no retained secrets, command injection, path escape, or
  uncontrolled network execution.

## 9. Testing Strategy

### Contract And Parser Tests

- Valid minimal and full contracts.
- Every missing required field and unknown field.
- Duplicate IDs, observers, and owners.
- Unicode normalization, path separators, insertion order, and checkout path.
- Inline secret, shell metacharacters, path escape, oversized values, and deep
  nesting.
- Immediate, eventual, snapshot, and monotonic boundary values.

### Runner Contract Tests

- Success, non-zero, signal, timeout, missing binary, malformed JSON, empty
  output, oversized output, cancellation, and cleanup failure for every phase.
- Mutation succeeds but canonical read fails.
- Canonical read succeeds but one observer fails.
- Required and optional observers differ.
- Dirty tree changes during a run and evidence becomes stale.
- Environment variables are allowlisted and redacted.

### Integration Fixtures

Build small deterministic applications that demonstrate:

1. One canonical store used by two views: clean control.
2. Two duplicated writable stores: divergence.
3. Server mutation without client cache invalidation: stale read.
4. Server state copied into unsynchronized component state: navigation/reload
   distinction.
5. Eventual projection converging before and after the deadline.
6. Delayed response A overwriting later response B.
7. Immutable historical snapshot retaining the original value: negative control.
8. Observer/tool failure: unknown, not divergence.

### Security Tests

- Malicious contract paths, argv, environment references, adapter output, and
  comparator names.
- Symlink and worktree path escape.
- Secret-bearing mutation/observation payloads and browser traces.
- Process-tree timeout and cleanup.
- Untrusted pull-request policy cannot gain protected credentials.
- Fork CI runs do not execute privileged consistency adapters by default.

### UAT Protocol

For one fresh sample application:

1. Generate and lint a contract using only CLI help.
2. Run a clean cross-view flow.
3. Introduce the seeded stale-read defect and rerun.
4. Follow the reported repair and rerun command.
5. Repeat after browser reload and fresh session.
6. Exercise timeout, offline, malformed observation, and stale evidence.
7. Verify keyboard-only and `NO_COLOR` operation.
8. Inspect retained evidence for secrets and raw user data.
9. File `docs/uat/state-consistency-<date>.md` with SHIP, FIX FIRST, or REJECT.

## 10. Security And Privacy Requirements

- Execute argv arrays with `shell=False`; no shell-string compatibility path.
- Resolve cwd, fixtures, outputs, and retained artifacts inside approved roots.
- Use environment variable names in contracts, never values.
- Default to synthetic unique subjects, not production user records.
- Require explicit policy before network, browser, container, or production-like
  environment access.
- Bound process time, process tree, output bytes, observers, polls, sequence
  length, generated subjects, and retained artifacts.
- Hash or redact observed values by default. Permit raw retention only through
  explicit repository policy and existing secret scanning.
- Do not upload browser traces, screenshots, payloads, or application logs as
  public artifacts.
- Treat adapter output as untrusted data; validate schema before rendering.
- Cleanup credentials must not be exposed to mutation or observer phases unless
  explicitly required and least-privileged.

## 11. Performance And CI Placement

| Work | Placement | Initial state | Budget |
|---|---|---|---:|
| Contract discovery/lint | PR and local | Blocking for malformed active contracts after SC2 | 500 ms p95 |
| Deterministic API/CLI changed-scope runs | Separate PR job | Advisory | 5 min target |
| Browser cross-view journeys | Separate PR or scheduled | Advisory | 10 min target |
| Stateful sequences | Scheduled or explicit | Advisory | 30 min hard bound |
| Static heuristics | Edit/PR only after measured | Advisory | 150 ms per edited file |
| Full contract corpus | Scheduled | Advisory | 60 min hard bound |

No consistency execution joins the blocking critical path until SC9 proves the
repository's p95 critical path remains at or below 12 minutes. Lint may block
only malformed active contracts because it performs no application execution.

## 12. Observability And Evidence

Retain per run:

- Outcome counts by contract and observer.
- Source, contract, policy, adapter, and comparator digests.
- Phase durations, poll count, convergence duration, timeout, and cleanup state.
- Bounded output digests and redacted summaries.
- Deterministic seed and minimized sequence when applicable.
- Rerun command and stale/superseded reason.

Privacy-preserving aggregate telemetry may include counts and durations only.
It excludes repository names, paths, contract IDs, fact names, values,
fingerprints, URLs, selectors, commands, subject IDs, and raw evidence.

## 13. Blast Radius

Highest-risk surfaces:

- `fettle/cli.py`: public command compatibility and exit semantics.
- `fettle/tool_runner.py` and `fettle/environment.py`: subprocess and secret
  boundaries shared by other checks.
- `fettle/result.py` / `fettle/finding.py`: canonical outcome semantics.
- `fettle/spec_model.py`, `spec_audit.py`, and `semantic.py`: requirement and
  evidence traceability.
- `fettle/uat/`: browser permissions, credentials, and retained transcripts.
- `fettle/changeset.py`: conservative changed-scope selection.
- `fettle/report.py`: historical evidence interpretation.
- GitHub workflows: fork trust, credentials, runtime, and artifact privacy.

Required controls:

- Keep consistency records separate from shared result types until parity tests
  justify integration.
- Add one surface adapter at a time.
- Never weaken existing CI, UAT, or verification authority.
- Re-run four-agent event conformance only if dispatcher behavior changes.
- Run wheel/sdist resource smoke tests when templates or commands are packaged.
- Run current kgraph impact analysis before each accepted package.

## 14. Delivery Slices

Recommended releases:

| Slice | Scope | User value | Exit gate |
|---|---|---|---|
| A | SC1-SC2 | Contracts can be authored and validated | Five real contracts lint cleanly without execution-specific schema changes |
| B | SC3-SC4 | API/CLI divergence can be reproduced | Seeded clean, stale, tool-error, snapshot, and race controls pass |
| C | SC5 | Real cross-view browser journeys | Reload/fresh-session UAT and browser flake threshold pass |
| D | SC6-SC7 | Sequence and architectural-risk discovery | Retained deterministic race and measured heuristic precision |
| E | SC8-SC9 | Traceable advisory CI and graduation decision | Pilot thresholds and P35/P38 prerequisites pass |

Estimated engineering effort before pilot: 30-48 experienced-engineer days,
excluding repository-specific application adapters and the 30-run evidence
window. SC1-SC2 should be evaluated before committing to later estimates.

## 15. Implementation Task Contract

For each accepted package, decompose work into independently verifiable tasks:

1. Add the behavior contract test and adversarial fixture first.
2. Add clean, divergent, tool-error, unknown, and intentional-snapshot controls.
3. Implement the smallest production change.
4. Run focused tests after each concern.
5. Run integration fixtures whenever execution behavior changes.
6. Run the full test suite for behavior-changing Python.
7. Run Ruff, `fettle check --changed`, workflow parsing, and `git diff --check`.
8. Run package smoke tests for resources, templates, or optional extras.
9. Perform the UX/UAT journey in a fresh sample application.
10. Update schema, docs, changelog, roadmap, and work note with the same public
    contract change.

No package is complete based only on parser tests or mocked UI state.

## 16. Success Criteria

The program succeeds when:

1. A developer can declare one canonical fact and cross-view observers without
   introducing a second testing language.
2. The clean fixture converges and each seeded divergence is detected.
3. Intentional snapshots and allowed eventual consistency do not false-fire.
4. Missing tools, malformed output, unavailable canonical state, and cleanup
   failure cannot become pass.
5. Evidence identifies the divergent observer and reproducing command without
   leaking raw sensitive values.
6. Fixed journeys and stateful sequences detect both steady-state and temporal
   divergence.
7. Static heuristics remain advisory until their measured precision threshold.
8. Executed evidence is bound to exact source, contract, policy, and adapters.
9. Enforcement remains impossible until P35, P38, and SC9 graduation gates pass.
10. Full tests, Fettle scan, packaging smoke, UAT, and remote CI remain green.

## 17. Explicit Non-Goals

- Inferring business identity from matching field or variable names.
- Building a universal browser, API, SQL, or assertion DSL.
- Replacing repository-native unit, integration, or E2E frameworks.
- Guaranteeing distributed linearizability or solving consensus.
- Treating every stale read as proof of missing cache invalidation.
- Scanning production databases or user accounts by default.
- Storing raw business values, credentials, or unrestricted browser traces.
- Blocking normal edits with application startup or cross-view execution.
- Making property-based testing a core runtime dependency.
- Automatically rewriting application state architecture.

## 18. Compliance Gate

- Phase 0 UX: complete in `docs/state-consistency.ux-spec.md`.
- Phase 0.5 UI: not applicable; the planned interface is CLI/JSON with no new
  visual component system.
- Phase 1 plan: complete in this document.
- Phase 3.5 UAT: BDD scenarios and manual protocol are defined before code.
- Feature manifest: not applicable; this repository uses `docs/ROADMAP.md` and
  `docs/engagement/TODO.md`.
- Implementation authorization: not granted. Recommend accepting SC1 only as
  the first implementation package after review.
