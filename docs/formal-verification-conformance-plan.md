# Formal Verification Conformance And Assurance Implementation Plan

> Integration precedence — current main’s November 14 sequencing decision and
> trust-remediation ownership govern execution. Earlier scheduling and review
> observations below remain historical. This merge grants no feature approval.

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/formal.md).

Status: PROPOSED, 2026-10-11; planning only. No implementation, model change,
solver installation, live evaluation, mutation campaign, CI change, enforcement,
commit, or release is authorized by this document.

Planning extension approved 2026-10-16: detail the four book-derived workstreams
and place their activities in the existing TODO. This approves documentation
only. WP-FM-0 through WP-FM-6 retain their identifiers and separate gates;
WP-FM-7 through WP-FM-11 are proposed internal-assurance follow-ups.

Priority: P2-FM in the [engagement TODO](engagement/TODO.md#current-priority-order).
This is a bounded continuation of P43, not a new verification authority.

Experience contracts: [UX and BDD](formal-verification-conformance.ux-spec.md),
[CLI presentation](formal-verification-conformance.ui-spec.md).

## 1. Goal And User Flow

As a maintainer or recipient of delegated work, I want to know which critical
properties were checked against which implementation, under which assumptions,
so I can distinguish useful assurance from an unsupported verification claim.

```text
change a mapped implementation or model
  -> identify the affected property and invalidated evidence
  -> run the explicitly authorized, bounded verification profile
  -> inspect a scoped result or replayable counterexample
  -> repair and rerun without weakening the property
  -> inspect the evidence through existing explain/report/assurance surfaces
  -> let existing policy and completion evaluators decide their own criteria
```

Fettle should integrate established checkers and make their evidence usable.
It should not implement an SMT solver, theorem prover, or general Python verifier.

## 2. Priority, Dependencies, And Authorization

1. Required audit-hardening acceptance and WP-WLI-0 through WP-WLI-4 retain P0.
   Start no FM execution in the active hardening worktree before that acceptance.
2. Reconsider WP-FM-0 after M-NC1's continue/revise/stop decision, with required
  hardening acceptance and WP-WLI-4 already evidenced. Preserve P0-IL incident
  learning and DS/ED checkpoints. Earlier work requires an explicitly approved
  reprioritization for a demonstrated trust-critical gap. P2-FM is not a new
  prerequisite for M-NC1, WLI, or every P3 proposal.
3. WP-FM-0 can overlap WP-WLI-6's observation window without taking resources
   committed to lifecycle measurement; it need not wait for the full 30 days.
4. WLI-5 projection work, P57, P34 qualification, and DS/ED retain their separate
   decisions. No whole-suite discipline rollout is an implicit FM prerequisite.
5. Every package below needs explicit authorization. Accepting the plan authorizes
   neither execution nor the next package. A discovered security-critical defect
   returns to P0 triage; it does not silently expand this pilot.
6. Completing this pilot qualifies at most its named claim. It does not complete
   P43, implement its three parked models, or prove all Fettle behavior correct.
7. Default internal order is capsule conformance (FM-0 through FM-5), the FM-6
  decision, completion obligations (FM-7/FM-8), evidence aggregation (FM-9),
  authority flow (FM-10), and claim-specific qualification (FM-11). Accepting a
  package does not authorize the next. A NO_GO pauses dependent work until the
  operator explicitly changes the sequence or scope.
8. WLI owns lifecycle validity; existing domain evaluators own evidence meaning;
  Assurance owns policy eligibility. This plan supplies scoped checks and
  correspondence evidence to those owners, not a competing evaluator or ledger.
  A newly demonstrated defect returns to P0 triage; it does not wait for FM-11
  or silently authorize a repair in the hardening worktree.

## 3. Observed Baseline And Gaps

This is a source inspection, not a fresh TLC or mutation result.

| Observed owner | Current behavior | Required improvement |
|---|---|---|
| [PolicyCapsule model](../specs/tla/PolicyCapsule.tla) and [configuration](../specs/tla/PolicyCapsule.cfg) | Mode ordering and protocol invariants; configured for three agents and depth two | State exact bounds and assumptions; connect actions to implementation |
| [Capsule implementation](../fettle/policy_capsule.py) | `merge_for_child` handles modes, enabled flags, directed numerics, plumbing, roles, defaults, and missing keys | Do not apply a mode-only model claim to the full merge contract |
| [Capsule tests](../tests/test_policy_capsule.py) | Example-based merge and file/verification tests | Add independently specified finite-domain and sequence conformance checks |
| [TLA synchronization hook](../fettle/tla_sync.py) | Mapped-file advisory and modification-time comparison; says source is formally verified | Truthful wording and content-bound evidence invalidation, not semantic claims from timestamps |
| [TLC runner](../specs/tla/run-all.sh) and [workflow](../.github/workflows/tla-verify.yml) | Separate model execution; CI verifies a pinned JAR checksum and uploads failure logs | Review terminal-state parsing, retain successful evidence, and align local tool integrity |
| [TLA README](../specs/tla/README.md) | Parameter table differs from the checked-in capsule configuration; claims a symmetry-based small-model guarantee | Derive displayed parameters from the checked configuration; require justification for generalization |
| [Integration contract](../fettle/integration_base.py) | Five adapter statuses with canonical evidence support and fallback bindings | Formal reports need explicit completeness and exact inputs, never fallback report-content source identity |
| [P43 decision record](fettle-evolution-implementation-plan.md#p43-narrow-formal-methods-decision-gate) | Model-to-code maps and property/state-machine tests remain open | Close one admitted claim before adding tools or models |

The historical [formal verification plan](tla-plus-formal-verification.md)
records prior vacuous invariants. Preserve that history as a fault-corpus input;
do not treat historical passing prose as fresh evidence.

### 2026-10-16 Status And Book-To-Mechanism Map

Current source/document inspection and `fettle completion validate` still show
`AH07-independent-hardening-acceptance` blocked. The validation reports P63, P69,
completion/work-item linkage, P54-P56, and P81 complete; that is the validator's
current disposition, not a new independent acceptance of their evidence. The
working tree contains ongoing hardening changes. No formal execution or new
behavior is authorized alongside them.

The source is Flemming Nielson and Hanne Riis Nielson, *Formal Methods: An
Appetizer* (2019), chapters 1, 3-6, and 8. These ideas inform the design; they do
not supply a proof or effectiveness result for Fettle.

| Book idea | Present Fettle boundary | Increment proposed here |
|---|---|---|
| Operational semantics and bounded model checking, chapters 1/6/8 | Two TLA+ models exist; standalone model execution does not establish Python correspondence | Complete the existing capsule claim before expanding; retain model and implementation observations separately |
| Verification obligations and partial correctness, chapters 3/6 | `completion._evaluate_manifest` checks declared criterion verdicts, reference identity/revision, and manifest constraints | Bind one admitted criterion family to independently defined expected outcomes and an authorized semantic evaluator; distinguish correct termination handling from successful work |
| Sound abstractions, chapter 4 | `evidence.py` already separates result/validity and carries completeness/trust; Assurance aggregates domain observations | Specify a conservative abstraction and independent reference relation for one existing aggregate, then check its real implementation |
| Integrity and non-interference, chapter 5 | Canonical bindings and producer-aware evidence consumption exist; identity and self-declared trust are not semantic truth | Test that changes confined to untrusted annotations cannot alter normalized authority decisions, including through check-selection branches |

Use existing tests and consumer paths. Do not add a Guarded Commands interpreter,
generic Python static analyzer, general theorem prover, trust-score replacement,
or new top-level CLI. Further concurrency work must distinguish abstract action
sequences from real lock/process scheduling; the three parked P43 models remain
parked. State-consistency P57-P61 and M-NC1 retain their independent scope gates.

## 4. Claim Boundary And Method Selection

Initial claim ID: `capsule.mode_monotonicity.v1` (proposed, frozen in WP-FM-0).
For a well-formed, shared, non-plumbing `gates.<name>.mode` leaf whose parent and
local values are `off`, `advisory`, or `enforce`, the effective child's rank is
the maximum of the two ranks. Repeated modeled delegation must not lower the
inherited rank. Tests must also preserve the documented local-plumbing exception.

The map must distinguish the pure `MonotonicMerge` operation from surrounding
`WriteCapsule` and `VerifyAndMerge` actions. Unmapped I/O, actor identity, lineage,
digest, and guard behavior remain outside this first claim, even when existing
tests or other model invariants cover parts of them.

Explicit initial exclusions: aliases and unknown mode values, missing/malformed
trees, enabled flags, numeric thresholds, roles, arbitrary filesystem schedules,
cryptographic authenticity, and unbounded actors or depth. Keep existing tests
for these behaviors; exclusions are not permission to weaken them. Unsupported
inputs are visibly outside scope, never a vacuous pass. Boundary fixtures pin
both admitted and excluded inputs. Expanding the domain needs a revised claim.

| Approach | Value | Limitation | Decision |
|---|---|---|---|
| More standalone TLA+ models | Explore additional protocol risks | Leaves implementation correspondence unresolved | Keep Verify Gate, Dispatcher, and TDD Gate parked |
| Existing TLC model plus implementation conformance | Reuses investment and tests the missing correspondence | Testing is not a formal refinement proof | Selected first |
| CrossHair contracts | Searches real Python paths for counterexamples | Supported semantics and bounded search; absence of counterexample is not proof | Later optional pure-function pilot |
| Dafny, Lean, TLAPS, or another proof system | Stronger claims for suitable kernels | New modeling, proof maintenance, and trusted-tool costs | Demand-gated, not an initial dependency |

Working hypothesis: a reviewed implementation map and fault-sensitive tests find
model/code divergence that rerunning unchanged TLC cannot find. Falsification:
the bridge misses a seeded in-scope implementation defect, derives its expected
answer from the same implementation helper, or cannot preserve honest scope
within the approved maintenance/runtime budget. Repair that design before adding
another model or engine. Model fault detection alone does not satisfy this goal.

## 5. Evidence And Authority Contract

Use the existing [EvidenceArtifact contract](evidence-artifact-contract.md).
Freeze a versioned domain payload, provisionally `fettle.formal`, without adding
top-level envelope fields or a second assurance/completion evaluator.

The payload must retain:

- Claim ID/version, property text digest, input-domain definition, assumptions,
  exclusions, safety/liveness classification, and declared model bounds.
- Model/configuration/imported-module digests; reduction settings, constraints,
  selected invariants, and deadlock/fairness options. An unchecked property is
  not inferred from the presence of its name or comment in a model.
- Exact source snapshot, policy and scope bindings, mapping digest, implementation
  dependencies, test/oracle/fixture digests, and supported runtime identity.
- Checker and adapter versions and implementation digests, executable/JAR digest,
  invocation profile, resource limits, terminal outcome, and checked obligations.
- Exploration completion and counts when supplied by the tool; test selection,
  executed counts, skips, and conformance coverage. Zero selected obligations
  cannot qualify. Missing fields remain missing, not assumed defaults.
- Digested bounded logs and counterexample/replay references, provenance for
  their generation, and an independent execution occurrence for each run.

Keep model checking and conformance as separate observations, with references
from the scoped claim record. A complete finite-model check is complete for its
declared model, not a proof of arbitrary implementation executions. A mapping
review is not a machine-checked refinement proof. Human approval and producer
attestation remain distinct from content identity.

| Observation | Canonical treatment | May satisfy the required claim? |
|---|---|---|
| Model exploration completed and all selected invariants held | `pass`, complete within declared model scope | Only the model obligation |
| All required implementation conformance checks executed and passed | `pass`, complete within declared test scope | Only the conformance obligation |
| Counterexample or conformance mismatch | `violation`; retain available evidence and completeness | No |
| Timeout, interruption, skipped required case, unfinished search | `unknown` with partial/unknown completeness | No |
| Missing checker, crash, unsupported output, malformed report | `tool_error` or validation non-pass as defined by the existing contract | No |
| Stale/wrong-source/wrong-policy/wrong-scope evidence | Existing artifact validity rejection | No |
| No admitted property, disabled optional integration, unsupported input | Explicit not-applicable/unknown reason under the frozen contract | Never satisfies a required criterion |

Never convert exit zero or the generic adapter's default `complete` into proof.
The formal producer must provide explicit bindings and completeness. External
checker output does not gain authority merely by being wrapped or signed. Existing
consumer allowlists and policy must explicitly admit the narrowly scoped evidence.

Invalidate evidence on any changed input above, even if timestamps are preserved.
Binding a mapping to source prevents stale reuse; it does not prove that the
mapping is semantically correct. Retain that independent review obligation.

## 6. Work Packages

Estimates are engineering days after prerequisites and authorization, excluding
review queues and observation. WP-FM-0 through WP-FM-5 total approximately 8-15
days; re-estimate after the first fault-sensitivity checkpoint, not by silently
reducing acceptance. Roles: implementation owner, independent model/oracle
reviewer, and operator as approval authority. One person may not self-approve an
unresolved specification or oracle disagreement.

### WP-FM-0: Freeze The Claim, Inventory, And Review Contract

Estimate: 1-2 days. Contract/review only; no production change.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Reconcile model, configuration, docs, implementation, tests, and CI | AUDIT | Property-to-owner matrix and verified source locations | Every modeled action is mapped or explicitly excluded; live constants replace stale prose |
| 2 | Freeze the admitted input domain and abstraction | SPECIFY | Model/Python value mapping and allowed transitions | Independent reviewer resolves all mismatches, including aliases, plumbing, and lineage assumptions |
| 3 | Audit vacuity, reductions, deadlock settings, and wording | REVIEW | Reviewed assumption and claim register | No unsupported small-model, liveness, cryptographic, or whole-source claim remains in the proposed contract |
| 4 | Freeze baseline and evaluation protocol | SPECIFY | Dev fault cases, sealed holdout, resource limits, retention, reviewer ownership | Expected outcomes are recorded before implementation; baseline uses current code and exact candidate |
| 5 | Confirm experience and capability inventory | REVIEW | Accepted UX/UI/BDD contracts and planned capability entry | Existing CLI/Assurance owners agreed; public capability documentation remains truthful about non-delivery |

Exit: accepted scope, mapping, corpus, budgets, and reviewers. Unresolved semantic
questions block WP-FM-1. Proposed starting budgets: conformance tests <=60 seconds,
one model profile <=5 minutes, and the existing CI job <=10 minutes. Measure and
freeze achievable limits here before evaluation; no timeout may count as success.

### WP-FM-1: Establish Independent Oracles And Red Evidence

Estimate: 1-2 days. Fixtures and tests; separately authorized.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Enumerate the canonical mode relation independently | TDD | Nine mode-pair expectations plus domain-boundary fixtures | Expected ranks are not imported from `_rank`, `_MODE_RANK`, or `merge_for_child` |
| 2 | Specify reachable delegation sequences and plumbing exceptions | SPECIFY | Named action traces, expected observations, and applicability | Positive witnesses exercise antecedents and exceptions; empty state spaces fail |
| 3 | Freeze implementation faults and model faults separately | SPECIFY | Disposable fault patches with expected detector and stable identity | Weaker-local-wins, wrong rank, plumbing propagation, removed guard, and vacuous invariant cases are distinguished |
| 4 | Retain the unchanged baseline | VERIFY | Exact test/model selection and results | Each seed names whether existing tests already detect it; no invented improvement claim |
| 5 | Exercise the actual selected producer and consumer together | INTEGRATION | Existing owning tests and the approved package fixtures | Actual output reaches the owning parser and decision; positive and negative controls are observed |
| 6 | Retain rejection of weaker-local-wins and wrong rank | REGRESSION | Existing owning tests and the approved package fixtures | Every named negative remains non-pass; positive controls prove the detector executes |
| 7 | Run bounded local execution after implementation | LIVE | Existing owning tests and the approved package fixtures | Run `uv run pytest tests/test_policy_capsule.py tests/test_capsule_guard.py -q`; observe real selected operations, candidate invalidation and explicit non-pass for weaker-local-wins and wrong rank. Freeze any added profile command at FM-0/FM-7; a local probe is not live-provider qualification |

Exit: independent oracles and a reviewed development/held-out corpus. The holdout
owner does not expose expected outcomes to implementation tuning. Existing tests
may already kill seeds; incremental value must be measured, not presumed.

### WP-FM-2: Implement The Bounded Conformance Bridge

Estimate: 2-4 days. Tests first; production defects require explicit scoped repair.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Extend existing capsule tests with finite-domain assertions | TDD | Exhaustive checks for the nine admitted pairs and plumbing boundary | Seeded in-scope faults fail while the unmodified implementation passes |
| 2 | Add a focused Hypothesis state machine using the reviewed map | INTEGRATION | Repeated merge/delegation tests with shrinking and reproducible settings | Real Python operations are invoked; selected actions and postconditions are observed |
| 3 | Replay named model/implementation divergences | REGRESSION | Small, deterministic regression cases in existing owning tests | A failing trace reproduces without a live agent, network, or remote service |
| 4 | Audit the bridge itself | REVIEW | Tests for missing mapping, excluded inputs, zero actions, and oracle disagreement | No omitted action, skipped case, or copied implementation logic can manufacture conformance |
| 5 | Run bounded local execution after implementation | LIVE | Existing owning tests and the approved package fixtures | Run `uv run pytest tests/test_policy_capsule.py tests/test_capsule_guard.py tests/test_tla_sync.py -q`; observe real selected operations, candidate invalidation and explicit non-pass for missing mapping, zero actions and implementation divergence. Freeze any added profile command at FM-0/FM-7; a local probe is not live-provider qualification |

Reuse local test helpers. Confirm Hypothesis availability; add it only to the
appropriate test dependency group if needed, never to the runtime surface by
default. Trace-driven tests establish bounded correspondence evidence; they are
not a proof that every implementation execution refines the TLA+ specification.

Exit: clean conformance run plus retained detection of every frozen required
development fault. A model pass with a broken implementation must remain visibly
distinct from a passed implementation claim.

### WP-FM-3: Produce And Validate Portable Formal Evidence

Estimate: 2-3 days. Adapter/runner and strict consumer-contract implementation.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Add a TLC producer through existing integration/evidence ownership | TDD | Versioned domain report and canonical envelope | Recorded successful, violating, interrupted, malformed, unsupported, and missing-tool outputs have exact expected states |
| 2 | Bind model and conformance evidence to their complete identities | INTEGRATION | Strict explicit source/policy/scope/tool/oracle bindings | Copied, altered, stale, partial, and mismatched artifacts are rejected |
| 3 | Retain success logs and counterexamples atomically | BUILD | Bounded, redacted, digested evidence with explicit retention | Partial writes and unavailable referenced evidence cannot satisfy the claim |
| 4 | Pin tool execution and resource behavior | BUILD | Consistent local/CI JAR verification and isolated execution | Wrong checksum, unsafe paths, runaway output, process interruption, and missing executable fail visibly |
| 5 | Retain rejection of wrong checksum, interrupted output and mismatched artifacts | REGRESSION | Existing owning tests and the approved package fixtures | Every named negative remains non-pass; positive controls prove the detector executes |
| 6 | Run bounded local execution after implementation | LIVE | Existing owning tests and the approved package fixtures | Run `uv run pytest tests/test_integration_base.py tests/test_integrations.py tests/test_evidence.py -q`; observe real selected operations, candidate invalidation and explicit non-pass for wrong checksum, interrupted output and mismatched artifacts. Freeze any added profile command at FM-0/FM-7; a local probe is not live-provider qualification |

Keep the existing envelope schema and adapter API compatible. If the generic
adapter cannot express a required state without loss, propose the smallest
reviewed domain mapping before coding; do not overload `PASS` or hide uncertainty.

Exit: complete parser/identity/failure matrix and portable replay in a clean
environment. No release gate or trust-class promotion is enabled.

### WP-FM-4: Add Truthful Inspection And Advisory CI Integration

Estimate: 1-2 days. Existing CLI/hook/Assurance surfaces; no new top-level command.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Correct mapped-file and model terminology | REVIEW | Scoped wording in hook, model docs, and capability descriptions | No source-file proof claim follows merely from its presence in `VERIFIED_FILES` |
| 2 | Use content identity for evidence applicability | TDD | Changed dependency/model/config/oracle invalidation | Same-mtime edits reject old evidence; touching a file alone does not prove semantic drift |
| 3 | Expose observations through explain/report and optional Assurance input | INTEGRATION | Human/JSON agreement, scope, exclusions, recovery, evidence references | UX scenarios pass; missing optional evidence is visible without silently introducing a required criterion |
| 4 | Add conformance and evidence retention to the TLA workflow | BUILD | Pinned, bounded CI steps and complete relevant path selection | Workflow tests cover model, source, mapping, tests, adapter, dependency, and workflow changes |
| 5 | Retain rejection of same-mtime stale evidence and text/JSON disagreement | REGRESSION | Existing owning tests and the approved package fixtures | Every named negative remains non-pass; positive controls prove the detector executes |
| 6 | Run bounded local execution after implementation | LIVE | Existing owning tests and the approved package fixtures | Run `uv run pytest tests/test_integrations.py tests/test_doc_claims.py tests/test_evidence.py -q`; observe real selected operations, candidate invalidation and explicit non-pass for same-mtime stale evidence and text/JSON disagreement. Freeze any added profile command at FM-0/FM-7; a local probe is not live-provider qualification |

The existing TLC CI job keeps its current authority; new claim aggregation starts
advisory. Do not run TLC or symbolic execution inside edit/Stop hooks. Hook work
is bounded local invalidation/inspection only. Required remote checks cannot be
inferred from a workflow file; verify host protection separately when authorized.

Exit: consistent text/JSON outputs and retained local/CI observations; no automatic
enforcement or P43 completion. Update the behavior map only for delivered changes.

### WP-FM-5: Qualify The Claim And Make A Graduation Decision

Estimate: 1-2 days plus an approved observation window. Separately authorized.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Evaluate the frozen holdout after development is closed | VERIFY | Independent model, implementation, evidence, and UX result matrix | Every required fault is detected; zero false eligible/ready results on the frozen negative corpus |
| 2 | Repeat in independent executions | VERIFY | Three complete retained clean-profile runs, including one fresh environment | Exact compatible identities, no terminal-outcome sharing, no skipped obligations, and frozen runtime budgets met |
| 3 | Measure incremental value and maintenance cost | REVIEW | Baseline/candidate detection, runtime, review effort, and repair effort | A documented blind spot is closed without increasing unsupported claims or exceeding accepted cost |
| 4 | Review claim-specific eligibility | REVIEW | Explicit GO, NO_GO, or BLOCKED with criterion evidence | Missing, stale, contradictory, timed-out, or unavailable required evidence is non-pass |
| 5 | Apply any approved promotion through existing policy | FIX | Opt-in named criterion, compatibility tests, and tested rollback | Operator authorizes exact policy/candidate; disabling a producer never bypasses a required criterion |
| 6 | Write failing tests before the authorized policy/consumer change | TDD | Existing owning tests and the approved package fixtures | The named negative cases fail for the intended reason before repair |
| 7 | Exercise the actual selected producer and consumer together | INTEGRATION | Existing owning tests and the approved package fixtures | Actual output reaches the owning parser and decision; positive and negative controls are observed |
| 8 | Retain rejection of unauthorized promotion and rollback bypass | REGRESSION | Existing owning tests and the approved package fixtures | Every named negative remains non-pass; positive controls prove the detector executes |
| 9 | Run bounded local execution after implementation | LIVE | Existing owning tests and the approved package fixtures | Run `uv run pytest tests/test_policy_layers.py tests/test_assurance_integrity.py -q`; observe real selected operations, candidate invalidation and explicit non-pass for unauthorized promotion and rollback bypass. Freeze any added profile command at FM-0/FM-7; a local probe is not live-provider qualification |

Follow the mutation playbook: fixtures -> preflight -> narrow replay -> separately
authorized held-out full verification where required. Do not make full mutation
runs an iteration loop. Keep stable fingerprints and complete cache identities;
an interrupted mutation run requires whole-worktree restoration inspection.

Exit: a criterion-level decision, not a blanket verified-source badge. Validate
any new completion records with `fettle completion validate`; no pilot result
closes unrelated P43 or hardening criteria. A NO_GO retains evidence and keeps
the new capability advisory or disabled without weakening existing requirements.

### WP-FM-6: Decide Expansion By Demonstrated Demand

Estimate: 1 review day; execution estimates and approvals are separate.

After FM-5, compare measured value and maintenance cost against the current
backlog. The preferred next branch is the bounded internal-assurance sequence
FM-7 through FM-11 below, beginning with approval of FM-7 only. Freeze the exact
claim and next package; do not authorize all follow-ups as a bundle. Record
CONTINUE, REVISE, STOP, or BLOCKED with evidence and an owner.

Retain Work Item Claims conformance with genuine two-actor contention/retry
evidence, and an opt-in CrossHair pure-function contract pilot for external
projects as alternatives requiring separate demand and authorization. They are
not dependencies of the internal sequence. Do not equate sequential state-machine
tests with verification of real filesystem locking or scheduling.

External-project support additionally requires contract discovery, explicit
execution consent, isolation, supported-language/runtime declarations, bounded
tool installation, and a portable report consumer. CrossHair executes Python;
its internal side-effect checks are not a security sandbox. Exit zero means no
counterexample found, not universal correctness. Defer other engines, generalized
model generation, and the three parked P43 models until their own decision gates.

### WP-FM-7: Freeze Completion Obligations And Independent Oracles

Estimate: 2-3 engineering days after FM-6 authorizes this package. Contract and
fixtures first; changes to live manifests or runtime validators are excluded.
Accountable owners: WLI/completion maintainer and the selected domain evaluator
maintainer. An independent reviewer accepts expected outcomes and claim scope.

Proposed claim: `completion.obligation_sufficiency.v1`. For one explicitly opted-in
criterion family, completion eligibility requires every required obligation in
the approved inventory to have current, applicable evidence whose authorized
evaluator establishes its expected outcome. The claim is relative to that
inventory and evaluator, not proof that the user's unstated needs were met.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Reconcile accepted WLI schema and actual completion/Assurance consumers | AUDIT | Criterion-to-owner matrix covering `completion.py`, `evidence.py`, `assurance.py`, and the selected existing producer | Every accept/reject path and compatibility boundary mapped; unresolved authority or schema questions block FM-8 |
| 2 | Freeze one criterion family and independently controlled obligation inventory | SPECIFY | Versioned contract defining criterion identity, required/applicable status, expected outcome, producer/evaluator identity, source/policy/scope and evidence meaning | Candidate-produced text cannot omit a required obligation, change its expected outcome, or declare itself authoritative |
| 3 | Select an existing machine-checkable success observation | SPECIFY | Positive fixture with nonempty executed obligations and an accepted producer/domain parser | Valid bytes plus a declared `confirmed` verdict are insufficient without the agreed semantic observation; unsupported families remain visibly outside the new claim |
| 4 | Specify a bounded lifecycle table | SPECIFY | Initial, pending, observed, invalidated, rejected and accepted transitions; legal recovery and terminal outcomes | Safety: no accept without all admitted required obligations; bounded progress under declared scheduler/tool limits: terminal result or explicit unresolved outcome, never forced success |
| 5 | Freeze independently adjudicated fault fixtures | SPECIFY | Missing/subset inventory, optional-only inventory for a required claim, stale revision, wrong producer/scope, forged success, skipped case, conflicting evidence, timeout and cancellation cases | Every negative has an expected non-pass reason and a positive witness; conflicting evidence cannot be resolved by choosing the favorable record |

Keep expected rejection/timeout-handling criteria distinct from required success:
an observed failure may satisfy a specifically authorized negative-test criterion,
but cannot satisfy a different success criterion. No blanket rule that every
domain observation must itself say `pass`. Legacy manifests retain their existing
semantics and are not relabeled as semantically qualified; any version migration
or new required field needs WLI approval and explicit compatibility fixtures.

Exit: accepted claim, nonempty inventory, finite state/domain bounds, authority
map, frozen development/held-out corpus and cost limits. Unresolved oracle or
authority disagreements are BLOCKED, not resolved by using production output as
the expected answer. No new production model or solver is required.

### WP-FM-8: Implement One Obligation-To-Evidence Connection

Estimate: 3-5 engineering days. Requires accepted FM-7 and separate implementation
approval. Owners: the same WLI/domain maintainers; existing Assurance owner
reviews consumption and authority. No new general evaluator service.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Add failing fixtures for the accepted relation | TDD | Existing `tests/test_completion.py`, `tests/test_completion_gate.py` and selected producer tests | Show the precise uncovered behavior against the frozen baseline; count defects already caught rather than claiming new detection |
| 2 | Connect the opted-in criterion to its existing authorized domain evaluator | BUILD | `fettle/completion.py` and the approved consumer path identified at FM-7 | No arbitrary command/callback imported from a manifest; no success default for absent, unsupported, partial or malformed semantic output |
| 3 | Exercise actual operations against the finite lifecycle table | INTEGRATION | Existing completion tests with independently defined action/expectation data | Each admitted transition executes; source/evidence invalidation followed by reevaluation cannot reuse prior acceptance; positive recovery succeeds |
| 4 | Preserve compatibility and independence | REGRESSION | Existing WLI parser, completion gate, canonical evidence and Assurance tests | Legacy records keep their declared assurance level; advisory results cannot bypass or silently add required criteria; no live corpus reconciliation before its existing gates |
| 5 | Retain scoped observations and recovery | VERIFY | Existing canonical payload/retention and completion inspection paths | Wrong-source, unknown, rejected and successful cases have matching human/JSON meanings and safe evidence references |
| 6 | Run bounded local execution after implementation | LIVE | Existing owning tests and the approved package fixtures | Run `uv run pytest tests/test_completion.py tests/test_completion_gate.py tests/test_evidence_contract.py -q`; observe real selected operations, candidate invalidation and explicit non-pass for forged confirmation and missing required observations. Freeze any added profile command at FM-0/FM-7; a local probe is not live-provider qualification Observe pending to rejected or accepted transitions and invalidation; missing evidence never permits acceptance. |

A fake producer can have a valid digest: test producer admission and domain
semantics separately from artifact identity. Review actor/input ownership and
source changes between observation and acceptance; do not promise atomicity that
the consumer cannot provide. Record the candidate snapshot and require recheck
when it changes. Exit: all frozen development cases discriminate as specified,
real operations are observed, and no current authority or legacy claim is silently
promoted. The new claim stays advisory pending FM-11.

### WP-FM-9: Specify And Check Conservative Evidence Aggregation

Estimate: 2-4 engineering days. Requires FM-8 acceptance and separate approval.
Owners: canonical evidence and Assurance maintainers. Start with the admitted
FM-8 family and one existing policy aggregate, not every producer or language.
Proposed claim: `assurance.conservative_aggregation.v1`.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Define concrete meaning and abstract uncertainty | SPECIFY | Reviewed interpretation from admitted observations to possible criterion outcomes, with separate validity, completeness, applicability and authority constraints | Explain why each abstract state conservatively represents its concrete cases; an executable reducer alone is not evidence of semantic soundness |
| 2 | Define an information order and aggregation relation | SPECIFY | Independent finite-domain reference tables; distinguish uncertainty union from conjunction across required obligations | Do not sort PASS/UNKNOWN/ERROR into a single numeric confidence score; conflicting observations and empty/impossible interpretations cannot imply success |
| 3 | Exercise the real aggregate | INTEGRATION | Extend `tests/test_evidence.py`, `tests/test_evidence_contract.py`, `tests/test_assurance_integrity.py` and `tests/test_assurance_adversary.py` where owned | Exhaust the frozen single-observation states and bounded multi-observation combinations; check required/optional, applicability, duplicates, ordering and conflicts |
| 4 | Check conservative weakening and invalidation | REGRESSION | Paired fixtures holding policy, scope, inventory and authority fixed | Removing required evidence or widening its possible outcomes cannot turn a non-eligible claim eligible; new contradiction or a new candidate may revoke an old decision; absent required observations remain unknown and non-eligible, never a fabricated pass |
| 5 | Repair only demonstrated in-scope divergence | TDD | Small changes to the actual `evidence.py`/`assurance.py` owner if required, or tests only if the implementation already satisfies the relation | Compare frozen Assurance baseline and required historical corpus; no unsupported producer becomes eligible and no default required gate changes |
| 6 | Run bounded local execution after implementation | LIVE | Existing owning tests and the approved package fixtures | Run `uv run pytest tests/test_evidence.py tests/test_evidence_contract.py tests/test_assurance_integrity.py tests/test_assurance_adversary.py -q`; observe real selected operations, candidate invalidation and explicit non-pass for removed required evidence and contradictory observations. Freeze any added profile command at FM-0/FM-7; a local probe is not live-provider qualification |

This is not a total ordering of lifecycle states or a promise that decisions only
improve over time. Unknown is not a fabricated pass or an empty set of behaviors.
Authoritative acceptance requires all possible admitted interpretations to satisfy
the required relation and all validity/authority conditions to hold. The reference
oracle must not call the production rank, join, acceptance or merge helpers.
Exit: an independently reviewed interpretation, executable correspondence tests,
and retained non-vacuity/fault-sensitivity evidence within the frozen domain.

### WP-FM-10: Check Information Flow Into Authority

Estimate: 3-5 engineering days. Requires FM-9 acceptance and separate approval.
Owners: Assurance/evidence consumers, policy maintainer and independent security
reviewer. Proposed claim: `assurance.annotation_noninterference.v1`.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Classify inputs at the admitted decision boundary | AUDIT | Inventory of operator-approved policy, authorized evaluator observations, untrusted annotations and controlled approvals | Treat a producer-supplied `trust_class`, signature or digest as data, not authority; classify by actual origin and approved consumption |
| 2 | Freeze a two-execution property | SPECIFY | Same trusted inputs and admitted observations, different untrusted annotation values, equal normalized authoritative decision | Compare eligibility, required obligations, selected checks and effective policy; exclude only diagnostic prose/occurrence IDs, never safety-relevant differences |
| 3 | Exercise explicit and control-dependent flows | TDD | Paired tests in existing assurance adversary/integrity, completion and capsule tests only where those paths are actually called | Prose such as a claimed approval cannot skip a check, alter requirement selection, relax policy or grant a pass; malformed/forged artifacts remain a separate rejection corpus |
| 4 | Preserve meaningful sensitivity | INTEGRATION | Positive controls that change an authorized observation or approved policy | Legitimate relevant changes can alter decisions; a reducer that ignores all input cannot pass the non-interference suite vacuously |
| 5 | Test controlled endorsement and disclosure | REGRESSION | Explicit approval-boundary cases with actor/scope/candidate binding, retained reason and revocation behavior | Untrusted input cannot approve itself; no implicit endorsement from rewrapping or signing; replay logs do not disclose secrets or execute annotation content |
| 6 | Run bounded local execution after implementation | LIVE | Existing owning tests and the approved package fixtures | Run `uv run pytest tests/test_assurance_adversary.py tests/test_assurance_integrity.py tests/test_completion.py -q`; observe real selected operations, candidate invalidation and explicit non-pass for untrusted approval annotations and forged endorsement. Freeze any added profile command at FM-0/FM-7; a local probe is not live-provider qualification |

When annotations live inside a digested artifact, vary them in separately valid
fixtures under the approved producer contract and hold the semantic observation
fixed. A tampered digest is not a valid two-run comparison. If an input cannot be
varied without changing trusted meaning, narrow the claim instead of excluding
the resulting authority difference from the comparison.

The first claim concerns decision integrity, not general prompt-injection
resistance, confidentiality, timing/termination covert channels, compromised
trusted evaluators, or arbitrary host/process interleavings. Findings outside
scope get explicit triage rather than an implied guarantee. Exit: accepted flow
inventory, passing real-consumer pairs, positive controls, and detection of each
frozen in-scope bypass seed. Scope expands only by another reviewed claim.

### WP-FM-11: Qualify Internal Claims And Decide Promotion Separately

Estimate: 2-3 engineering days plus any separately approved observation period.
Requires accepted FM-8 through FM-10 evidence and explicit qualification approval.
Owners: independent reviewer and operator, with each consumer maintainer signing
off only its own boundary. No automatic inheritance of the capsule claim's GO.

| # | Task | Method | Deliverable / owner | Verify by |
|---|---|---|---|---|
| 1 | Run the sealed fault corpus once development is frozen | VERIFY | Per-claim baseline/candidate matrix, exact test selection, versions, inputs, skips, terminal states and logs | Zero false eligible results on required negative fixtures; every frozen positive control succeeds; zero missing or skipped required obligations |
| 2 | Check implementation and oracle sensitivity independently | VERIFY | Distinct development and held-out implementation faults with stable identities | Every required in-scope seed is detected; do not count a model-only failure as an implementation detection or tune against the holdout |
| 3 | Check replay and cost | VERIFY | Three independently retained compatible clean-profile runs, including a fresh environment; runtime, reviewer effort and recovery cost | Meet limits frozen before execution; no shared terminal outcomes or omitted attempts; equivalent tests alone do not establish real concurrency safety |
| 4 | Perform recipient UAT and compatibility review | REVIEW | BDD-FM-8 through BDD-FM-13 and existing FM scenarios as applicable; required WLI/Assurance/code regressions | Recipient distinguishes integrity, semantic sufficiency, unknown and acceptance; text/JSON agree; false non-eligible decisions are independently adjudicated |
| 5 | Decide each named claim and rollback | REVIEW | GO, NO_GO or BLOCKED with criterion-level reasons; existing policy admission and tested rollback if approved | No pooled score hides a failed claim; rollback removes optional capability without bypassing an explicitly required criterion; no default enforcement or P43 completion |

Treat these as conformance/assurance checks for declared finite domains, not
machine-checked unbounded refinement proofs. A newly admitted required criterion
needs an explicit policy/consumer approval, not merely a passing producer. Reuse
the existing canonical envelope and proposed `fettle.formal` payload with separate
claim records for the three follow-ups; field/schema changes need owner review.
Carry the full source/policy/scope/inventory/evaluator/oracle/tool identity and
independent occurrence required in section 5. A timeout stays non-pass even when
other claims finish. Missing evidence prevents promotion; it does not authorize
weakening the criterion or deleting the failed case.

### Follow-Up Costs And Stop Rules

FM-7 through FM-11 total an initial 12-20 engineering-day estimate, excluding
review queues, observation and approval waits. This is not a budget authorization
or delivery promise. Re-estimate at FM-7 against the accepted WLI/evaluator
boundary. Propose a <=60-second focused test profile and <=5-minute optional
finite-model profile, then measure and freeze achievable limits before execution.
Do not add solver installation or live-agent runs to this test-only profile.

Stop and return for a decision if there is no independently specifiable criterion,
the oracle merely copies implementation logic, a claim depends on unknown producer
semantics, authority would change without owner approval, or evaluation exceeds
the agreed cost. Report a passing baseline honestly: stronger scope documentation
or coverage can be the output, but invented new defect detection cannot. A NO_GO
retains evidence and existing safeguards. No branch resumes the parked external
effectiveness study or authorizes new spending.

## 7. Verification And Blast Radius

Implementation owners are the capsule functions/tests, TLA specs/config/runner,
`tla_sync`, integration/evidence contracts, existing inspection/Assurance consumers,
and the TLA workflow. Shared config, policy, test dependencies, packaging, or
release boundaries enter scope only when an approved package requires them.
Run a fresh impact query and inspect actual consumers before each executable
slice; documentation-time graph output is not runtime assurance.

Existing entry checks, to be run only in the authorized implementation phase:

```bash
uv run pytest tests/test_policy_capsule.py tests/test_capsule_guard.py tests/test_tla_sync.py -q
uv run pytest tests/test_integration_base.py tests/test_integrations.py tests/test_doc_claims.py -q
./specs/tla/run-all.sh PolicyCapsule
uv run fettle completion validate
```

Add the exact evidence, Assurance, workflow, and conformance selections when
WP-FM-0 resolves the consumer map; do not guess new CLI switches or test names.
For the internal continuation, existing focused entry points are:

```bash
uv run pytest tests/test_completion.py tests/test_completion_gate.py -q
uv run pytest tests/test_evidence.py tests/test_evidence_contract.py -q
uv run pytest tests/test_assurance_integrity.py tests/test_assurance_adversary.py tests/test_assurance_baseline.py -q
```

FM-7 must add the actual selected producer and accepted WLI test selections before
FM-8, not presume these commands cover them. Package-level red/green tests precede
the sealed FM-11 evaluation. Run completion validation to report prerequisites;
a blocked AH07 is not permission to alter hardening evidence. These commands are
implementation-phase checks, not tests executed by this planning update.

Use disposable source copies for seeded faults and keep generated artifacts out
of tracked source. Run Fettle's changed-file check and applicable project rules.
Preserve required fresh full-suite/mutation gates where their contracts apply.
Remote CI must be green for any authorized push; this plan authorizes no push.

Principal risks: specification error, copied-oracle error, vacuous invariants,
unsound abstraction, model drift, hidden partial results, stale cache reuse,
state-space explosion, unsafe analyzer execution, and overstated user-facing
claims. The work packages address each with explicit negative fixtures and
independent review; none is solved merely by adding another solver.

## 8. Planning Gate And Worklog

- UX, CLI presentation, and pre-code BDD contracts are drafted alongside this
  plan; they remain subject to WP-FM-0 acceptance, not live UAT evidence.
- The capability inventory is the current P43 baseline plus the proposed scoped
  claims in sections 4 and 6. Do not add a public shipped feature to CAPABILITIES
  until the corresponding package is delivered and verified. The documentation
  [coordination item](backlog/formal-verification-conformance.md) is not a second
  P43 completion record or a runtime approval. No new FEATURES manifest is added.
- Planning verification is separate from runtime qualification. No TLC, formal
  fault campaign, live UAT, or new completion milestone is claimed here.
- 2026-10-11: read TODO priorities, P43, current model/configuration/runner,
  capsule implementation/tests, integration/evidence contracts, and planning
  conventions. Selected one mode-ordering claim and preserved P0/WLI priorities.
- 2026-10-11: initial TODO edit passed all six documentation-claim tests. The
  installed `kgraph impact` uses positional paths, not `--file`; its documentation
  impact result reports a stale index and is diagnostic only. No index refresh
  or unrelated worktree repair was performed.
- 2026-10-11: linked package passed all six documentation-claim tests; 37 local
  Markdown link targets across the five edited documents resolve; editor
  diagnostics and `git diff --check` reported no errors. The required Fettle
  `check --changed` reported no issues. No project-local rule pack was present
  at `.fettle/rules` or `.lint/semgrep`.
- 2026-10-11: `fettle completion validate` reports audit-hardening incomplete:
  `AH07-independent-hardening-acceptance` is blocked. This is an existing P0
  prerequisite, not formal-pilot evidence or a completed milestone. Its recovery
  requires the existing independent-review disposition and exact-candidate
  platform, host, and remote CI evidence. No hardening status was changed.
- 2026-10-16: operator requested detailed book-derived planning and TODO placement,
  excluding Fettle code changes. Rechecked current TODO, existing plans, owning
  completion/evidence paths, test entry points and completion disposition. AH07
  remains blocked. Preserved P0-IL, WLI, DS/ED and M-NC1 sequencing; extended this
  plan instead of adding a competing assurance program. The impact index reports
  stale; direct owner/link inspection is the planning fallback, not evidence of
  exhaustive runtime impact. No index refresh or hardening repair was attempted.
- 2026-10-16: documentation-only coordination item added; all six existing
  documentation-claim tests passed before claiming it and after both plan and
  linked-document edits. Structural checks passed for seven documents, 71 local
  links/anchors, 12 unique pending work packages, 13 BDD scenarios, referenced
  owner/test paths and preserved priority order. Editor diagnostics and whitespace
  checks were clean. The required Fettle scan reported no issues; no project-local
  rule pack exists at `.fettle/rules` or `.lint/semgrep`.
- 2026-10-16: the first ad hoc priority check matched a worklog reference instead
  of a checklist entry; anchoring to actual entries made the check discriminate
  correctly without changing priorities. Completion validation rejected the new
  coordination item's historical boolean marker; corrected it to the required
  `fettle-work-item: v2` and reran validation. The new-item error is gone; AH07
  remains blocked with its existing recovery requirements. The item stays open;
  releasing its editing claim does not assert implementation or P43 completion.
- 2026-10-16: the pre/post Git diff fingerprint for source, tests, models,
  workflows and project metadata is identical. Existing worktree changes were
  preserved; only the seven scoped planning documents were edited. No formal
  checker, live UAT, mutation run, benchmark, dependency change, commit, push or
  runtime qualification was performed. Final post-worklog checks repeat the
  documentation tests and Fettle scan before releasing the editing claim.

Research is not a prerequisite for this bounded plan: the local evidence already
identifies the missing correspondence. Later engine research may use Luna when
authorized, with public/minimized inputs and explicit cost/privacy limits. Use
primary checker documentation for semantics, including CrossHair's
[limitations](https://crosshair.readthedocs.io/en/latest/limitations.html) and
[execution/contract behavior](https://crosshair.readthedocs.io/en/latest/contracts.html).