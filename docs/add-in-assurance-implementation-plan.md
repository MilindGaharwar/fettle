# Add-in Assurance Pilot Implementation Plan

Status: PROPOSED; planning only; implementation is not authorized

UX contract: [add-in-assurance.ux-spec.md](add-in-assurance.ux-spec.md)

Depends on: Assurance Integrity CS-6 graduation and a separate explicit operator
authorization for this plan

## 1. Objective

Prove, with one local deterministic analyzer, that Fettle can accept optional
evidence through a narrow capability and identity contract without becoming an
agent orchestrator, plugin marketplace, runtime manager, memory system, or OS
sandbox, and without allowing optional evidence to create an authoritative PASS.

The pilot uses Ruff because it is local, deterministic for pinned inputs,
already present in Fettle's supported toolchain, and has a direct invocation
that can serve as the comparison oracle. Ruff evidence is deliberately
duplicate and non-independent. The pilot validates contract integrity, replay,
failure behavior, and operating cost; it does not claim increased assurance
coverage.

## 2. User Story

As a release owner evaluating optional analyzers, I want one shadow-only result
whose producer, inputs, capabilities, completeness, and cost can be verified
independently, so I can decide whether an add-in mechanism is worth retaining
without weakening the existing Assurance decision.

## 3. Hard Gates

### Gate 0: Existing Program Completion

No implementation work begins until all of the following are true:

1. CS-6 has 20 accepted real shadow assessments.
2. Every CS-6 difference is classified and resolved.
3. The operator has explicitly approved Assurance Integrity enforcement or has
   explicitly authorized this plan as a documented exception to the standing
   single-program rule in `docs/plan-index.md`.
4. The operator separately gives explicit approval to implement this plan.

Planning approval is not implementation approval. Repository status remains
`PROPOSED` until the fourth condition is recorded.

### Gate 1: Contract Review

Before runtime code, approve the frozen manifest, threat model, result mapping,
baseline protocol, and fixtures. No package discovery, dynamic imports, remote
registry, signatures, or policy DSL enter this pilot.

### Gate 2: Technical Readiness

Before real shadow collection, all contract, adversarial, focused, full-suite,
installed-wheel, and manual CLI checks pass. The adapter remains explicit-run
only and cannot affect an Assurance policy result.

### Gate 3: Feasibility Decision

Twenty add-in assessments establish feasibility only. They do not establish a
population-level accuracy or safety claim. The operator chooses `remove`,
`revise`, or `retain shadow-only`; any authoritative or automatic execution is a
new proposal requiring a powered study and separate approval.

## 4. Scope

### In Scope

- One strict local add-in manifest and validator.
- One fixed Ruff shadow adapter reached through `fettle integrations`.
- Exact source, policy, scope, manifest, tool, adapter, configuration, and output
  identities.
- Deterministic capability compatibility with strictest-result composition.
- `draft`, `approved`, and `revoked` manifest states, with repository review as
  the human transition boundary.
- Bounded subprocess execution of a trusted pinned executable.
- Canonical advisory evidence and an optional Assurance Record parent reference.
- Paired baseline measurement and an append-only 20-assessment register.

### Out Of Scope

- Agent planning, tool selection, workflow execution, or remediation loops.
- Dynamic plugin discovery or arbitrary Python imports from manifests.
- Registries, marketplaces, reputation, remote installation, or auto-update.
- LLM policy extraction, semantic memory, workflow memory, or chain-of-thought.
- LTL, a general policy language, probabilistic authority, or automatic policy
  promotion.
- Fettle-provided network/filesystem/process sandboxing.
- Docker, Kubernetes, Docker socket access, daemon processes, or hosted control
  planes.
- Action-indexed check skipping. The pilot evaluates every applicable file in
  canonical scope.
- Claims that lock-file identity proves complete runtime dependency behavior.

## 5. Decisions And Tradeoffs

| Decision | Alternatives | Reason |
|---|---|---|
| Reuse `fettle integrations` | Add `fettle addins`; hidden hook execution | Avoid another top-level command and accidental orchestration |
| Add a strict contract beside the legacy integration report | Treat current `IntegrationReport` defaults as authoritative; rewrite all adapters | Existing defaults synthesize unspecified bindings and are unsuitable for authority; a bounded additive path limits regressions |
| Ruff as the first adapter | ShellCheck; network service; model analyzer | Ruff is local, pinned, available, and has a direct oracle; it tests plumbing rather than novelty |
| Explicit static registration | Entry points; filesystem discovery; marketplace | Discovery expands supply-chain and execution authority before value is proven |
| Repository-reviewed manifest | Build PKI now; trust a self-declared ID | Git review is the existing local human boundary; external signing is deferred until external distribution exists |
| Pre/post executable digest plus pinned version | Claim atomic executable identity; hash only the command name | Portable Python cannot guarantee atomic execution of a path; detecting identity drift is honest and sufficient for this trusted local pilot |
| Full applicable scope | Action-indexed selection | Completeness is simpler to prove; ShieldAgent's efficiency results do not validate Fettle's domain |
| Advisory parent reference | New Assurance dimension; add-in-only PASS | Preserves the current release policy and schema authority |
| Host-provided containment | Claim subprocess isolation; make Fettle own a sandbox | A subprocess is not a sandbox; untrusted executables remain inadmissible |

## 6. Trust And Capability Contract

### Research Decision Register

| Source | Adopt now | Defer | Reject | Enforced by |
|---|---|---|---|---|
| ShieldAgent | Independently validate advisory analyzer evidence | Action-indexed verification, pending a separate Fettle-domain study | Learned decisions as authority or ShieldAgent efficiency claims as Fettle evidence | Full-scope pilot, advisory trust class, and Assurance-decision parity tests |
| openJiuwen | Conceptual core/harness/extension separation and deterministic strictest-result composition | Stronger isolation supplied by an independently validated external sandbox | Bypasses, fail-open malformed state, Docker socket exposure, and subprocess-as-sandbox claims | Static registration, fail-closed contract tests, capability checks, and containment disclosures |
| WikiSkill | Persistent knowledge may inform proposer-side drafts only | Evaluated transfer mechanisms with explicit provenance and domain validation | Executor access to accumulated guidance and assumptions that cross-model transfer is safe | Immutable reviewed manifests, no execution memory, and derived/untrusted treatment of transferred output |

These sources inform architecture but do not provide evidence that their reported
results transfer to Fettle. Learned, generated, transferred, or history-aware
decisions remain proposals or derived evidence and cannot authorize execution,
promote policy, or establish PASS.

The conceptual boundary is:

- Core: validates canonical identity, evidence, lifecycle, and authority without
  importing or executing extension code.
- Harness: attenuates capabilities, invokes the fixed trusted executable, applies
  bounds, and records observations without making an Assurance decision.
- Extension: maps one statically registered analyzer's bounded output into the
  canonical advisory evidence contract.

Capability composition follows `deny > ask > allow`, with the strictest result
winning across the manifest, operator policy, and host capability. The pilot is
non-interactive, so `ask` does not prompt or persist consent: it becomes
`UNKNOWN`, execution does not start, and the operator must approve a reviewed
manifest or policy change outside the runtime. Missing, malformed, unsupported,
or conflicting state is also `UNKNOWN`, never `allow`.

The manifest is strict canonical JSON with unknown fields rejected. Proposed v1
fields are:

| Field | Rule |
|---|---|
| `schema_version` | Exact supported version |
| `add_in_id` | Stable bounded identifier; statically registered |
| `version` | Exact adapter contract version |
| `state` | `draft`, `approved`, or `revoked` |
| `owner` | Human-readable accountable owner |
| `adapter_implementation_digest` | Full SHA-256 of the Fettle adapter implementation |
| `tool` | Fixed executable name, exact supported version, resolved executable digest |
| `capabilities` | Read scope, write scope, network, environment names, process and output limits |
| `input_kinds` | Explicit accepted artifact kinds |
| `output_kind` | Exact canonical evidence kind |
| `compatibility` | Supported Fettle evidence schema and adapter protocol versions |
| `approval_reference` | Reviewed repository decision reference; empty while draft |

Pilot capability policy permits repository reads for canonical scope, one fixed
Ruff invocation, no declared environment inputs, no network, no repository
writes, and bounded wall-clock/output. Compatibility is attenuation-only: the
effective capability set is the intersection of manifest request and operator
policy; any unmet request is `UNKNOWN` and execution does not start.

The contract records declared capability and observed execution metadata. It
does not claim to prevent network, filesystem, or subprocess behavior at the OS
level. For that reason the pilot admits only the pinned Ruff executable already
trusted by Fettle. A future untrusted add-in requires an external sandbox
provider contract and separate approval.

Lifecycle semantics are deliberately narrow:

- `draft`: may run only when explicitly named; always shadow-only.
- `approved`: reserved for a later operator decision; remains non-authoritative
  under this pilot and does not imply automatic execution.
- `revoked`: cannot execute and all retained evidence is stale/non-pass.
- Only a reviewed repository change may alter lifecycle state. Runtime code
  never writes or suggests a persisted allow rule.

## 7. Evidence And Result Contract

The add-in emits a raw bounded report plus `EvidenceArtifact` sidecar. The
sidecar uses trust class `derived`, never `authoritative`, and binds:

- canonical source snapshot and revision;
- effective layered-policy digest;
- complete assessed scope and applicable Python subset;
- manifest digest and lifecycle state;
- adapter implementation digest;
- resolved Ruff path, pre/post executable digest, and exact version;
- fixed argv, environment-name allowlist, timeout, output limit, and cwd class;
- raw output digest, normalized findings digest, exit code, elapsed milliseconds,
  completeness, and result state.

Mapping is fixed:

| Observation | Canonical state | CLI exit |
|---|---|---|
| Complete, clean Ruff result | `pass`, displayed as `SHADOW PASS` | 0 |
| Complete Ruff findings | `violation`, displayed as `SHADOW FAIL` | 1 |
| No applicable Python files | `not_applicable` | 0 |
| Missing/revoked/incompatible manifest or tool identity | `unknown` | 2 |
| Timeout, malformed/oversized output, identity drift, or persistence failure | `tool_error` or `unknown` | 2 |

The Assurance Record may include the valid sidecar as an advisory parent and in
human/JSON diagnostics. The existing dimensions, completeness calculation,
policy criteria, and exit code are computed without it. A test must prove that
adding, removing, failing, or tampering with the shadow result cannot change the
policy decision.

## 8. Threat Model

| Threat | Required response |
|---|---|
| Manifest self-approves or requests broader capability | Reject before execution |
| Unknown manifest field/version | Reject as unsupported |
| Executable path is missing, changes, or resolves unexpectedly | `UNKNOWN`; invalidate prior sidecar |
| Executable changes between pre/post identity checks | Reject result; do not claim atomic identity |
| Symlink or output path escapes repository-owned `.fettle/add-ins/` | Reject before read/write |
| Ruff writes repository content | Detect source snapshot drift, reject result, report boundary limitation |
| Process times out or output exceeds limit | Terminate, discard partial authority, emit non-pass |
| Output and exit code disagree | Reject as malformed |
| Prior result copied to another source/policy/scope | Canonical validation rejects binding mismatch |
| Add-in result claims independence or authority | Schema/consumer rejects unsupported trust class |
| Retained sidecar is deleted or corrupt | Assurance omits/rejects advisory reference; its verdict is unchanged |
| Host lacks enforceable network/process containment | Admit only pinned trusted Ruff; state limitation visibly |

## 9. Baseline And Pilot Design

### Baseline Unit

One verified change is one distinct Git change assessed under the same effective
policy and canonical scope. A paired observation contains:

1. Baseline `fettle assurance --policy production` without the add-in reference.
2. Direct pinned Ruff invocation over the complete applicable scope.
3. Candidate `fettle integrations ruff-shadow` invocation.
4. Candidate Assurance evaluation with the advisory parent enabled.
5. Human discrepancy classification and effort timing.

### Metrics

- Machine: direct-Ruff duration, adapter duration, assurance-only duration,
  bytes retained, peak result size, retries, and error category.
- Human: setup minutes, discrepancy-review minutes, recovery minutes, and total
  operator minutes.
- Integrity: normalized finding agreement, source/policy/scope binding result,
  content replay result, stale/tamper rejection, and Assurance-decision parity.
- North star for the pilot:

```text
incremental_cost_per_verified_change =
    median(add-in machine cost + add-in operator time) per accepted assessment
```

Machine cost and operator time remain separate reported components; they are not
collapsed into an invented independence score.

### Sample

Twenty distinct real changes are required after Gate 2. They are separate from
the 20 CS-6 assessments unless an add-in candidate was already technically
ready, which this plan explicitly forbids before Gate 0.

The feasibility sample should contain, with categories allowed to overlap:

- at least 10 Python-bearing changes;
- at least 5 mixed-language changes;
- at least 5 changes with no applicable Python files;
- among applicable changes, at least 5 direct-Ruff clean outcomes and 5 finding
  outcomes.

If organic work does not satisfy those strata, collection remains open. Fixtures
test errors but do not count as real assessments. No statistical effectiveness
claim is made from n=20.

## 10. Work Packages

Every package requires fresh `kgraph index` and `kgraph impact` output for its
runtime files before editing. The current index is stale and cannot establish
the final blast radius.

### AA-0: Freeze Planning And Authorization

Files: this plan, `docs/add-in-assurance.ux-spec.md`, `docs/plan-index.md`.

Atomic tasks:

1. Record Gate 0 status and owner. Verify: plan links resolve.
2. Review manifest fields and remove any field without a pilot consumer.
   Verify: contract table maps every field to one validation rule.
3. Review all BDD scenarios with the operator. Verify: explicit approval record
   names accepted scenarios and exclusions.
4. Record implementation authorization separately from planning approval.
   Verify: status changes from `PROPOSED` only after explicit instruction.

Estimate: 0.5-1 day. No runtime behavior change.

### AA-1: Establish Baseline And Fixtures

Files: `tests/fixtures/add_ins/`, `tests/test_addin_contract.py` (new),
`docs/engagement/add-in-assurance-shadow-assessments.md` (new).

Atomic tasks:

1. Capture one valid draft manifest fixture. Verify: canonical bytes round-trip.
2. Add fixtures for unknown fields and unsupported versions. Verify: each is
   rejected for its intended reason.
3. Add fixtures for missing, malformed, approved, and revoked lifecycle states.
   Verify: only explicit-run draft is eligible in pilot mode.
4. Add capability-escalation fixtures for network, writes, environment, command,
   timeout, and output size. Verify: each is rejected before runner invocation.
5. Add path/symlink escape and executable-drift fixtures. Verify: each is
   non-pass and invalidates stale evidence.
6. Add clean, findings, malformed JSON, exit/output mismatch, timeout, and
   oversized-output Ruff fixtures. Verify: table-driven result mapping.
7. Create the append-only register with baseline/candidate timing and discrepancy
   columns. Verify: it rejects duplicate subject/scope entries by review rule.

Estimate: 1-2 days. Tests must fail for the intended missing behavior before
AA-2 begins.

### AA-2: Implement The Strict Manifest Contract

Files: `fettle/addin_contract.py` (new), `tests/test_addin_contract.py`, and
`fettle/config_schema.py` only if the reviewed config requires schema exposure.

Atomic tasks:

1. Add enums for lifecycle and capability names. Verify: unsupported values
   raise a bounded validation error.
2. Add immutable manifest value types. Verify: required fields cannot be empty.
3. Parse canonical JSON with duplicate-key and Unicode ambiguity rejection.
   Verify: adversarial fixtures fail closed.
4. Validate exact schema fields and bounds. Verify: unknown/missing fields fail.
5. Canonically digest the manifest excluding no authority-bearing field. Verify:
   equivalent bytes have equal identity and changed fields do not.
6. Implement attenuation against the static pilot policy. Verify: effective
   capabilities never exceed either side and incompatible requests do not run.
7. Implement lifecycle eligibility without persistence. Verify: runtime code has
   no path that writes state or approval.

Estimate: 2 days.

### AA-3: Implement Bounded Local Execution

Files: `fettle/addin_runner.py` (new), `fettle/tool_runner.py` only if a generic
bounded-output improvement is proven safe, and focused tests.

Atomic tasks:

1. Resolve the statically registered Ruff executable to a regular file. Verify:
   missing and unexpected symlink/path cases fail before invocation.
2. Capture exact Ruff version and pre-execution digest. Verify: version or digest
   mismatch is `UNKNOWN`.
3. Build one fixed argv using `--no-cache` and canonical applicable paths.
   Verify: manifest content cannot inject arguments or shell syntax.
4. Build a minimal environment from the allowlist. Verify: secret test variables
   are absent from the child environment and evidence.
5. Execute without a shell under wall-clock and output bounds. Verify: timeout
   and oversized-output fixtures terminate as non-pass.
6. Recompute executable and source identities after execution. Verify: drift
   rejects the result and records the limitation without claiming sandboxing.
7. Return execution facts without creating policy decisions. Verify: runner
   output contains no authority or lifecycle mutation method.

Estimate: 2-3 days.

### AA-4: Add The Ruff Shadow Adapter

Files: `fettle/ruff_shadow_adapter.py` (new), `fettle/integration_base.py`,
`tests/test_integration_base.py`, and `tests/test_integrations.py`.

Atomic tasks:

1. Derive source, effective policy, and canonical changed scope through existing
   APIs. Verify: caller-supplied paths cannot replace canonical identity.
2. Select every Python file in canonical scope and record the full applicability
   projection. Verify: mixed and non-Python fixtures classify deterministically.
3. Normalize Ruff findings to bounded repository-relative records. Verify:
   absolute/escaping paths and secret-like text are rejected.
4. Reconcile Ruff exit code, JSON, file coverage, and completeness. Verify: only
   complete clean/findings results become pass/violation.
5. Build `fettle.addin.ruff-shadow` evidence with trust class `derived`. Verify:
   every influencing identity is digest-bound.
6. Persist raw report and sidecar atomically under
   `.fettle/add-ins/ruff-shadow/`. Verify: interrupted writes cannot preserve an
   old current sidecar.
7. Remove or prohibit synthesized `unspecified` source/policy/scope bindings on
   the strict add-in path. Verify: legacy integration behavior is unchanged.

Estimate: 2-3 days.

### AA-5: Wire Existing CLI Surfaces

Files: `fettle/cli.py`, `fettle/doctor.py`, `fettle/pipeline_dump.py`,
`fettle/config.py`, `tests/test_cli.py`, `tests/test_doctor.py`,
`tests/test_pipeline_dump.py`, and `docs/behavior-map.md` only if public behavior
requires a new mapping row.

Atomic tasks:

1. Statically register `ruff-shadow` under `fettle integrations`. Verify: no
   entry-point or filesystem discovery occurs.
2. Render shadow authority, status, scope, elapsed time, evidence path, and
   recovery action. Verify: human/JSON parity.
3. Preserve 0/1/2 exit semantics. Verify: clean, findings, and invalid execution
   each produce the documented code.
4. Add doctor readiness for manifest and Ruff identity. Verify: doctor performs
   no analyzer execution or network call.
5. Add read-only pipeline inspection of state and capabilities. Verify: the
   command cannot mutate manifest, policy, or lifecycle.
6. Keep run-all behavior opt-in during the pilot. Verify: ordinary `fettle
   integrations` and hooks do not execute `ruff-shadow` implicitly.

Estimate: 1-2 days.

### AA-6: Bind Advisory Evidence Without Authority

Files: `fettle/assurance.py`, `tests/test_assurance_record.py`,
`tests/test_assurance_adversary.py`, and `tests/test_assurance_integrity.py`.

Atomic tasks:

1. Validate the optional sidecar against exact assessment context. Verify:
   wrong source, policy, scope, manifest, producer, or implementation is rejected.
2. Add a valid sidecar only as an advisory parent/diagnostic. Verify: dimensions
   and completeness are byte-for-byte equivalent before and after attachment.
3. Prove clean, findings, missing, malformed, stale, and revoked add-in states do
   not alter policy status or exit code. Verify: table-driven final-boundary test.
4. Show concise shadow evidence in human and JSON output. Verify: no output calls
   it independent or authoritative.
5. Verify deletion or failed persistence cannot retain an old parent reference.
   Verify: final-boundary stale-success regression test.

Estimate: 1-2 days.

### AA-7: Automated Verification And Installed UAT

Files: tests above, `docs/uat/add-in-assurance-pilot.md` (new), and packaging
configuration only if the manifest is not present in the built wheel.

Atomic tasks:

1. Run focused contract and adapter tests. Verify: all pass.
2. Run the record-level adversary suite. Verify: zero add-in-caused false passes.
3. Run the complete repository suite and Ruff. Verify: no regression.
4. Build and inspect the wheel. Verify: required manifest resources and no
   unintended files are present.
5. In a clean temporary repository, exercise first-time, clean, findings,
   non-applicable, malformed, timeout, stale, revoked, and recovery flows.
6. Compare direct Ruff and adapter normalized findings. Verify: exact agreement.
7. Repeat identical content in a second checkout. Verify: content digest matches
   while occurrence identity differs.
8. Record manual terminal usability after the required review break. Verify:
   every state gives status, authority class, and one next action.

Required commands, adjusted only if repository tooling changes before approval:

```bash
uv run pytest tests/test_addin_contract.py tests/test_integration_base.py tests/test_integrations.py -q
uv run pytest tests/test_assurance_record.py tests/test_assurance_adversary.py tests/test_assurance_integrity.py -q
uv run pytest -q
uv run ruff check fettle tests
uv run fettle config --validate
uv run fettle check --changed
uv run fettle completion validate
uv build
```

Estimate: 1-2 days.

### AA-8: Run Twenty Real Shadow Assessments

Files: `docs/engagement/add-in-assurance-shadow-assessments.md` and retained
assessment artifacts.

For each distinct real change:

1. Record subject, policy, scope, and baseline Assurance digest.
2. Time the direct pinned Ruff oracle over the same applicable scope.
3. Run and time `fettle integrations ruff-shadow`.
4. Run Assurance with the valid advisory reference.
5. Compare normalized findings, completeness, evidence bindings, and policy
   decision.
6. Record setup, review, and recovery minutes.
7. Classify every discrepancy as core defect, adapter defect, tool drift,
   expected normalization, or unresolved.
8. Accept the row only after evidence replay and human review succeed.

Estimate: observation window for 20 qualifying real changes; cannot be replaced
by repeated runs or fixtures.

### AA-9: Feasibility Decision

Files: shadow register, `docs/uat/add-in-assurance-pilot.md`, this plan,
`docs/plan-index.md`, and `docs/ROADMAP.md` only after operator decision.

Atomic tasks:

1. Recompute acceptance metrics from retained rows. Verify: no hand-entered
   aggregate conflicts with row evidence.
2. Review every discrepancy and rejected row. Verify: unresolved count is zero.
3. Compare measured incremental cost with the predeclared budgets. Verify:
   median and p95 calculations are reproducible.
4. Present `remove`, `revise`, or `retain shadow-only` recommendation. Verify:
   no implementation self-promotes.
5. Record the explicit operator decision. Verify: no automatic execution or
   authority is enabled without a separately approved next plan.

Estimate: 0.5-1 day.

## 11. Acceptance Gates

### Contract Integrity

- 100% of malformed, unsupported, stale, wrong-bound, revoked, and
  capability-incompatible fixtures produce non-pass.
- Deterministic composition always selects `deny` over `ask` and `ask` over
  `allow`; non-interactive `ask` never executes or creates persisted consent.
- Zero invocation occurs after pre-execution identity or capability failure.
- Zero prior sidecars survive a failed replacement as current evidence.
- 100% of accepted replay attempts reproduce the canonical content digest;
  occurrence IDs and timestamps are expected to differ.
- Core tests do not import or execute extension code, harness tests cannot create
  Assurance decisions, and extension tests cannot bypass the canonical contract.

### Authority Integrity

- Zero Assurance policy-status or exit-code differences with versus without the
  advisory add-in reference across tests and 20 accepted assessments.
- Zero add-in-only authoritative PASS outcomes.
- The Ruff pilot is always labelled derived, duplicate, and non-independent.
- Learned, generated, history-aware, or cross-model output is always untrusted
  derived evidence and cannot approve a manifest, promote policy, or grant PASS.
- Runtime execution receives only the immutable reviewed manifest and bounded
  assessment inputs; proposer knowledge and accumulated guidance are absent.

### Oracle Agreement

- 100% normalized finding agreement between direct pinned Ruff and the adapter
  for accepted assessments.
- Every difference is resolved before a row counts; there is no catch-all
  `explained` classification.

### Operability

- Assurance-only local p95 remains at or below one second.
- Ruff adapter execution p95 remains at or below 30 seconds.
- Median incremental human effort remains at or below two minutes per accepted
  assessment.
- Median retained add-in artifacts remain below 1 MiB and every artifact obeys
  existing canonical payload limits.
- Setup, runtime, storage, and human effort are reported separately; no composite
  score hides a regression.

### Sample And Decision

- Twenty distinct real changes satisfy the declared strata.
- The register has zero unresolved discrepancies and 100% accepted replay.
- All technical quality gates and installed-wheel UAT pass.
- The operator explicitly chooses the next state. Silence or an incomplete
  register means `NO GO`.

## 12. Blast Radius

- `fettle integrations` registration, output, and exit behavior.
- Integration evidence construction, but legacy vendor adapters must retain
  their current behavior.
- Tool execution limits and environment handling if a shared runner change is
  justified.
- `fettle doctor` and `fettle pipeline` read-only inspection.
- Assurance Record parent references and presentation, not dimensions or policy.
- Configuration schema and package resources.
- Evidence persistence below `.fettle/add-ins/`.

The preliminary `kgraph impact` result is stale and reports broad coupling from
`fettle/evidence.py` and `fettle/assurance.py`. Refreshing the index and reviewing
all consumers is mandatory before implementation. If exact impact shows the
Assurance schema cannot accept an advisory parent compatibly, AA-6 is removed
rather than forcing a schema migration into this pilot.

## 13. Rollback And Stop Conditions

Rollback is configuration-first: remove static registration and ignore/delete
the optional `.fettle/add-ins/ruff-shadow/` artifacts. Existing Assurance
dimensions and policies remain unchanged throughout, so rollback does not need
legacy authority compatibility.

Stop immediately if:

- CS-6 or explicit implementation authorization is absent;
- the design requires dynamic discovery, a new daemon, network access, repository
  writes, or Fettle-owned sandboxing;
- the add-in can alter an Assurance dimension or policy result;
- complete applicable scope cannot be proven;
- direct Ruff and adapter output cannot be reconciled deterministically;
- retained evidence exposes secrets or absolute checkout paths;
- runtime or operator effort exceeds budget without demonstrated value;
- another active feature program conflicts with the standing program constraint.

## 14. Estimate

- Contract, fixtures, runtime, adapter, CLI, Assurance binding, and UAT: 8-12
  engineering days after authorization.
- Shadow evidence: time needed for 20 qualifying real changes.
- Feasibility review: 0.5-1 day.

These are planning ranges for one experienced engineer, not commitments. No
implementation work, work-item claim, branch, or runtime/config change is
authorized by this document.
