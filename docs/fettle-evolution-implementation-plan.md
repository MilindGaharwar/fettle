# Fettle Evolution Implementation Plan

Status: APPROVED for completed activities; P33, P35, and P44 complete; P34,
P43, and P52 partially implemented; P36-P42 and P45-P61 remain proposed,
blocked, or evidence-gated; P62-P65 preserve the prioritized mutation-learning
follow-through; P66-P71 prioritize first-class evidence-contract convergence

Scope: post-v1.8 evolution of Fettle from Python-first governance to a
trustworthy, polyglot policy and evidence layer. This plan consolidates the
strategic review, competitor analysis, current audit findings, agent-facing
ergonomics gaps, semantic-delta opportunities, shell-security boundaries, and
language/framework expansion recommendations.

The user-flow contract is
[polyglot-governance.ux-spec.md](polyglot-governance.ux-spec.md). Existing
v1.6/v1.7 audit commitments remain owned by
[15-v161-audit-remediation.md](engagement/15-v161-audit-remediation.md) and are
dependencies, not duplicated work packages.

## 1. Outcome

### User Story

As a developer or platform engineer using AI coding agents, I want one Fettle
policy to produce consistent, actionable evidence across Python,
JavaScript/TypeScript, .NET, Java, and mixed repositories, so that agents can
repair problems while context is fresh and CI remains an independent assurance
boundary.

### Product Position

Fettle is the portable assurance layer between agent authority, software action,
engineering evidence, and independent verification:

```text
agent -> authority -> action -> evidence -> verification
             |             Fettle             |
             +-- policy and decision provenance
             +-- explicit degraded states
             +-- portable evidence contracts
             +-- independent CI boundary
```

Fettle does not become a general agent orchestrator, proprietary static
analyzer, semantic memory/database, IDE suite, hosted control plane, or
operating-system sandbox. It records observable decision inputs and outcomes,
not private model chain-of-thought. Model confidence, inferred memory, and
advisory graph output never grant authority.

## 2. Assumptions

1. v1.7 policy-resolution parity and workflow distribution are complete.
2. Python 3.11+ and the default zero-runtime-dependency posture remain.
3. Repository-native wrappers and commands take precedence over global tools.
4. Hooks remain the deterministic enforcement boundary; MCP is optional
   preflight and explanation.
5. CI remains an independent fail-closed boundary for full analysis.
6. New languages and framework rules start advisory and graduate only from
   measured evidence.
7. Existing Python, Go, Rust, and JS/TS behavior remains supported throughout
   migration; no flag-day dispatcher rewrite is acceptable.
8. Implementation remains additive until parity tests permit removal of an old
   path; unrelated worktree changes must not be overwritten or reverted.
9. Product value is measured as cost per verified software change, including
   repair success, assurance latency, tool/model cost, and visible indeterminate
   outcomes; token reduction alone is not a success criterion.

## 3. Decisions And Tradeoffs

### 3.1 Adapter Architecture

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Add `post_edit_<lang>.py` per language | Small initial diff | Duplicates parsing, errors, routing, and output | Reject |
| Route all checks through the existing adapter protocol immediately | Clean end state | High regression blast radius | Reject as flag day |
| Introduce one adapter-backed dispatcher check, migrate languages incrementally | Shared contract with reversible slices | Temporary dual paths | Adopt |

### 3.2 Framework Support

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Dedicated adapter per framework | Easy branding | Tool duplication and combinatorial growth | Reject |
| Framework rule packs over language adapters | Composable and testable | Requires pack detection and metadata | Adopt |
| Depend only on existing ecosystem plugins | Lowest maintenance | Cannot express Fettle process/evidence rules | Use first, supplement narrowly |

### 3.3 MCP

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Replace hooks with MCP | Rich interaction | Agent can ignore calls; weak enforcement | Reject |
| Persistent Fettle daemon | Caching and low latency | Lifecycle, security, and packaging burden | Defer |
| Thin stdio MCP adapter over shared services | Useful preflight with small scope | Another output surface to parity-test | Adopt after finding parity |

### 3.4 Shell Containment

Regex and shell parsing remain defense-in-depth mediation. Fettle will improve
classification and integrate with external sandboxes, but will not claim that
hooks provide process or network containment. eBPF/ptrace belongs in a separate
privileged, platform-specific security product.

## 4. Current Baseline And Authoritative Scope

v1.10.0 is the shipped trust baseline. The activity IDs below are the execution
source of truth; release work packages later in this document provide design
detail. Estimates include tests and documentation for one experienced engineer
and are planning ranges, not commitments.

| ID | Activity | Release | Depends on | Estimate | State |
|---|---|---|---|---|---|
| P0 | Align roadmap, release numbering, and v1.7 baseline | v1.8 | v1.7.0 | 0.5 day | Complete |
| P1 | Define canonical four-state result contract | v1.8 | P0 | 0.5–1 day | Complete |
| P2 | Add actionable fields to the canonical finding | v1.8 | P1 | 0.5–1 day | Complete |
| P3 | Carry findings and evidence through dispatcher transport without changing host wires | v1.8 | P1, P2 | 1–2 days | Complete |
| P4 | Record repair, turn, recurrence, byte, and indeterminate eval metrics | v1.8 | P1 | 1–2 days | Complete |
| P5 | Add Python and TypeScript repair/error behavioral scenarios | v1.8 | P2, P4 | 1–2 days | Complete |
| P6 | Persist bounded, redacted structured evidence in trace | v1.8 | P2, P3 | 1–2 days | Complete |
| P7 | Render concise, detailed, and JSON findings in report/explain | v1.8 | P2, P6 | 1–2 days | Complete |
| P8 | Attach evidence IDs to verify, coverage, UAT, CI, and integrations | v1.8 | P6 | 2–4 days | Complete |
| P9 | Consolidate workspace models and nested routing | v1.9 | P3 | 4–7 days | Complete |
| P10 | Strengthen adapter protocol with explicit `CheckRun` state | v1.9 | P1, P9 | 3–5 days | Complete |
| P11 | Add adapter-backed dispatcher check and migrate TypeScript | v1.9 | P3, P10 | 3–5 days | Complete |
| P12 | Migrate Go, Python, and Rust after parity | v1.9 | P11 | 4–7 days | Complete |
| P13 | Centralize file and test classification | v1.9 | P9, P10 | 3–5 days | Complete |
| P14 | Verify all affected workspaces and bind evidence | v1.9 | P8, P9, P10 | 3–5 days | Complete |
| P15 | Complete repository-native JS/TS tooling | v1.10 | P10, P11 | 3–5 days | Complete |
| P16 | Discover Node workspaces and framework metadata | v1.10 | P9, P15 | 2–4 days | Planned |
| P17 | Establish web CLI/hook/LSP parity and eval corpus | v1.10 | P5, P15, P16 | 3–5 days | Planned |
| P18 | Add argv-only generic command integration | v1.10 | P1, P6, P10 | 2–4 days | Planned |
| P19 | Ingest bounded SARIF and JUnit evidence | v1.10 | P2, P18 | 3–5 days | Planned |
| P20 | Expand adversarial shell corpus and conservative classification | v1.10 | P1 | 3–5 days | Planned |
| P21 | Define optional external sandbox provider contract | v1.10 | P18, P20 | 2–4 days | Demand-gated |
| P22 | Add .NET workspace, adapter, and behavioral evals | v1.11 | P10, P14, P19 | 5–8 days | Planned |
| P23 | Add Java workspace, adapter, and behavioral evals | v1.11 | P10, P14, P19 | 5–8 days | Planned |
| P24 | Add advisory framework-pack infrastructure | v1.12 | P13, P17, P22, P23 | 3–5 days | Planned |
| P25 | Add React/Next.js pack | v1.12 | P17, P24 | 3–5 days | Evidence-gated |
| P26 | Add ASP.NET Core and Spring Boot packs | v1.12 | P22, P23, P24 | 5–8 days | Evidence-gated |
| P27 | Add HTML/HTMX pack; add Angular only on demonstrated demand | v1.12 | P17, P24 | 3–6 days | Demand-gated |
| P28 | Capture bounded pre-edit structural evidence | v1.13 | P6, P13 | 3–5 days | Evidence-gated |
| P29 | Add initial semantic-delta rules and native infra ingestion | v1.13 | P19, P28 | 5–10 days | Evidence-gated |
| P30 | Extract shared side-effect-controlled analysis service | v1.14 | P12, P17, P19 | 4–7 days | Planned |
| P31 | Add thin stdio MCP query surface | v1.14 | P30 | 3–5 days | Demand-gated |
| P32 | Graduate additional LSP languages after parity | v1.14 | P22, P23, P30 | 3–6 days | Evidence-gated |
| P33 | Make scanner and CI result handling fail closed | next patch | P1, P3 | 1–2 days | Complete |
| P34 | Repair mutation selection, execution, and score integrity | next minor | P33 | 2–4 days | In progress |
| P35 | Establish seeded-defect and recorded-override contracts | next minor | P33 | 3–5 days | Complete |
| P36 | Reconstruct red-before-green evidence in CI | next minor | P33, P35 | 4–7 days | Proposed |
| P37 | Expand and version the Fettle behavioral benchmark | next minor | P4, P5, P33 | 5–8 days | Proposed |
| P38 | Consolidate specification traceability and add drift evidence | following minor | P33, P35 | 4–7 days | Proposed |
| P39 | Operationalize static and supply-chain controls | following minor | P33, P35 | 4–7 days | Proposed |
| P40 | Add invariant properties and flake detection selectively | following minor | P33, P37 | 4–7 days | Proposed |
| P41 | Build commit-linked, tamper-evident governance evidence | later minor | P35, P38 | 5–10 days | Proposed |
| P42 | Add deterministic Fettle event and check replay | later minor | P33, P37, P41 | 5–8 days | Proposed |
| P43 | Model only proven high-risk concurrent state machines | unscheduled | P40, P42 | 5–10 days | In progress (2 of 5 models) |
| P44 | Define hypergraph, provider, traversal, snapshot, and fixture contracts | unscheduled | P33 design contract | 3-5 days | Complete |
| P45 | Build graph-independent committed and working source snapshots | unscheduled | P44 | 5-8 days | Proposed |
| P46 | Assemble deterministic ephemeral graphs from native providers | unscheduled | P38, P44, P45 | 7-12 days | Proposed |
| P47 | Add advisory graph status, impact, and obligation output | unscheduled | P46 | 5-8 days | Proposed |
| P48 | Shadow semantic, topology, and verification consumers | unscheduled | P47 | 7-12 days | Proposed |
| P49 | Bind CI obligations and attestations to immutable candidates | unscheduled | P33, P35, P41, P48 | 7-12 days | Proposed |
| P50 | Add graph-expanded strict claim and integration checks | unscheduled | P49 | 7-12 days | Proposed |
| P51 | Evaluate and, only if admitted, add graph-cache persistence | unscheduled | P46-P50 profiling | 5-10 days | Evidence-gated |
| P52 | Enforce authorship separation: test-writer ≠ code-writer | next minor | P13, P14 | 2–3 days | In progress |
| P53 | Freeze state-consistency contract, adapter, evidence, and result schemas | next minor | P33 | 3-5 days | Proposed |
| P54 | Add state-consistency discovery, lint, list, and init template | next minor | P53 | 3-5 days | Proposed |
| P55 | Build bounded API/CLI state-consistency execution kernel | following minor | P54 | 5-8 days | Proposed |
| P56 | Add comparators and immediate/eventual/snapshot/monotonic evaluation | following minor | P55 | 4-6 days | Proposed |
| P57 | Add cross-view web/UAT state-consistency adapter | later minor | P55, P56 | 5-8 days | Proposed |
| P58 | Add optional deterministic and property-based state sequences | later minor | P55, P56 | 5-8 days | Evidence-gated |
| P59 | Add advisory duplicate-state and invalidation heuristics | unscheduled | P53, measured corpus | 5-8 days | Evidence-gated |
| P60 | Bind consistency evidence to specs, reports, and changed-scope CI | unscheduled | P35, P38, P56 | 5-8 days | Blocked on P35 -> P38 |
| P61 | Pilot state-consistency contracts and decide per-surface graduation | after P57-P60 as applicable | P55-P60 evidence | 30 qualifying runs | Evidence-gated |
| P62 | Complete authoritative mutation calibration and baseline | immediate, P0 | P34 implemented preflight slice | 2 full runs plus replay | Complete |
| P63 | Institutionalize mutation learning and user guidance | next minor, P1 | P34 | 3-5 days | Complete |
| P64 | Automate mutation methodology and generalize evidence staging | following minor, P2 | P62, P63 | 5-8 days | Planned |
| P65 | Operate and evolve mutation evidence from measured feedback | ongoing, P3 | P62, P64 | recurring | Evidence-gated |
| P66 | Inventory evidence surfaces and freeze the portable artifact contract | immediate, P0 | P6, P8, P33, P44 contracts | 3-5 days | Complete |
| P67 | Implement the canonical evidence kernel and pilot verification | next minor, P0 | P66 | 5-8 days | Complete |
| P68 | Bind CI, trace, and inspection to canonical evidence | next minor, P0 | P33, P67 | 5-8 days | Complete |
| P69 | Migrate assurance producers and strengthen override binding | following minor, P1 | P35, P62 where applicable, P68 | 7-12 days | Complete |
| P70 | Run advisory evidence migration and graduate producers independently | after P69, P2 | P37, P69 | 30 qualifying runs | Evidence-gated |
| P71 | Connect canonical evidence to change-integrity and evaluate persistence | after P45-P50 as applicable, P3 | P45, P49, P70 | 5-10 days | Evidence-gated |

The critical path to trustworthy polyglot verification is P0 → P1 → P3 → P9
→ P10 → P11 → P14. P4–P5 run alongside the result-contract work; P18–P21 may
run alongside the web proving ground after their dependencies close. Work
marked demand- or evidence-gated is not scheduled until its trigger is met.

P44-P51 form the change-integrity hypergraph program. P44's immutable contract
and adversarial-fixture layer is complete; P45-P51 remain gated. The program's
authoritative architecture, UX/UAT contract, staged implementation details,
migration gates, and persistence admission criteria are maintained in:

- [Change integrity architecture](change-integrity-architecture.md)
- [Change integrity UX specification](change-integrity.ux-spec.md)
- [Change integrity implementation plan](change-integrity-implementation-plan.md)

The program begins with an ephemeral graph and cannot authorize blocking graph
decisions until P33 closes false-clean result paths. P35 is required for
overrides, and P41 or an approved successor is required for durable graph-bound
attestations. Existing semantic, topology, claim, and verification behavior
remains authoritative until each consumer passes its own shadow graduation.
P51 may close with a no-go decision; SQLite is not an assumed deliverable.

P66-P71 form the first-class evidence convergence program. They do not replace
P6/P8 evidence references, P41 durable governance evidence, provider fact sets,
mutation reports, or P44-P51 graph contracts. They define the portable envelope
and validity rules those surfaces share. P66-P68 are the priority path because
new graph-bound or cross-process authority must not depend on loosely structured
evidence dictionaries. P69 migrates each producer without reducing its stronger
domain-specific report. P70 measures compatibility and operational value before
enforcement. P71 references accepted artifacts from the evidence plane and may
close with no persistent evidence store.
P66 is the first package eligible for proposal acceptance; P67-P71 remain
unauthorized until their package-specific UX, impact, security, migration, and
test contracts are reviewed. `immediate` denotes priority, not implementation
authorization or work already in progress.

P53-P61 form the state-consistency program. P53-P54 establish explicit
ownership, mutation, canonical-read, observer, comparator, and consistency-model
contracts before any application execution. P55-P56 add bounded API/CLI
execution and deterministic evaluation. Browser journeys, stateful sequences,
and static heuristics remain separately gated because their flake, dependency,
and false-positive risks differ. P60 cannot begin until P35's override contract
and P38's traceability contract graduate; P61 may approve only the surfaces and
contract classes that meet their own evidence thresholds. Detailed UX, BDD,
security, package sequencing, and graduation criteria are maintained in:

- [State consistency UX specification](state-consistency.ux-spec.md)
- [State consistency implementation plan](state-consistency-implementation-plan.md)

The state-consistency program does not infer business identity from matching
field names and does not treat application or adapter failure as a clean result.
P53 is the first package eligible for proposal acceptance; P54-P61 remain
unauthorized until their package-specific review.

### 4.1 Verification-Integrity Program (P33-P43)

#### Program User Story

As a developer or platform engineer relying on Fettle, I want every reported
pass to be backed by independently reproducible evidence, so that a missing
tool, parser defect, agent assertion, or mutable local record cannot create
false confidence.

#### Program Assumptions And Boundaries

1. Fettle remains a governance and integration layer, not a model runtime or
   universal agent scheduler.
2. Interactive hooks remain fail-open for session safety, but failures are
   visible, persisted, actionable, and escalated when repeated.
3. CI and explicit verification commands fail closed when a required check is
   unavailable, malformed, timed out, or indeterminate.
4. Full replay of externally controlled model hosts, network services, and
   arbitrary filesystem behavior is outside Fettle's ownership boundary.
5. Replay covers normalized events, effective policy, Fettle decisions,
   evidence, and recorded runner responses without spending model tokens.
6. Core installation remains dependency-free. Heavy engines remain CI tools or
   optional extras.
7. A check begins advisory. Promotion requires a seeded defect, measured
   precision, accepted runtime, a recovery action, and a recorded override.
8. The normal pull-request critical path has a 12-minute ceiling and a
   three-minute first-feedback target.

#### Alternatives Considered

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Implement the blueprint V1-V10 in order | Simple narrative | Builds expensive controls on evidence paths that can currently fail clean | Reject |
| Add all controls to every PR immediately | Maximum apparent coverage | Excessive latency, flaky gates, routine bypass | Reject |
| Repair evidence integrity, operationalize existing controls, then add independent evidence | Smallest trustworthy sequence; preserves architecture | Delays broad feature count | Adopt |
| Build a universal deterministic agent simulator | Ambitious reproducibility | Fettle does not control host model, network, clock, or tool runtime | Reject |

#### Required Check Contract

Every check introduced or promoted under P33-P43 must declare:

- Stable check identifier and owner.
- Applicability and explicit outcomes: `pass`, `violation`, `tool_error`,
  `unknown`, and `not_applicable`; `unknown` is never serialized as pass.
- Hard-gate or advisory status for each execution surface.
- One clean fixture and one seeded defect missed by the prior assurance layer.
- Recovery and exact rerun command for every non-pass outcome.
- Wall-clock p50/p95, timeout, output bound, and execution placement.
- Override policy containing actor, reason, timestamp, expiry, affected
  revision, check identifier, and prior evidence identifier.
- Evidence schema version and retention policy.

#### P33: Scanner And CI Result Integrity

Goal: close false-clean paths before relying on any additional automation.

Primary files:

- `fettle/quality_scan.py`
- `fettle/ci.py`
- `fettle/tool_runner.py`
- `fettle/result.py`
- `tests/test_quality_scan.py`
- `tests/test_ci.py`
- `tests/fixtures/`

Implementation slices:

1. Introduce an internal scanner result carrying findings, result state,
   command, exit code, stderr summary, and tool version.
2. Map missing binary, abnormal exit, timeout, empty malformed output, and JSON
   parse failure to `tool_error` or `unknown`; retain empty findings only for a
   successful clean execution.
3. Keep interactive callers policy-controlled and visibly fail-open; make
   `fettle ci` fail closed for required scanner errors.
4. Add seeded missing-tool, malformed-JSON, timeout, and nonstandard-exit
   fixtures and verify the existing behavior would miss them.
5. Preserve concise human output and stable JSON/exit-code contracts.

Acceptance:

- No required Ruff or Semgrep execution failure can yield a clean CI result.
- Clean, violation, unavailable, malformed, and timeout paths are contract
  tested independently.
- First feedback remains below three minutes in GitHub Actions.

Verification:

```bash
python3 -m pytest tests/test_quality_scan.py tests/test_ci.py tests/test_tool_runner.py -q
python3 -m fettle.cli ci --root .
python3 fettle/quality_scan.py --root . --json
```

#### P34: Mutation Evidence Integrity And Operationalization

Goal: turn the existing mutmut wrapper into trustworthy, bounded evidence.

Primary files:

- `fettle/mutation_test.py`
- `fettle/changeset.py`
- `fettle/ratchet.py`
- `tests/test_mutation_test.py`
- `.github/workflows/ci.yml`
- `.github/workflows/mutation.yml` (new, only if a separate workflow is needed)

Implementation slices:

1. Select changed implementation files against an explicit merge-base SHA,
   including added, modified, renamed, and deleted paths where meaningful.
2. Pin a supported mutmut version in CI and capture both `run` and `results`
   exit codes, stderr, timeout, and engine version.
3. Parse a version-pinned machine-readable store or verified output grammar;
   reject unknown grammar instead of guessing.
4. Treat zero generated or zero parsed mutants as `unknown`, never 100%.
5. Report killed, survived, timeout, suspicious, and untested mutants; include
   actionable survivor identifiers and files.
6. Run changed-module mutation as advisory with a ten-minute hard bound. Run
   full mutation nightly with retained artifacts.
7. Establish a baseline only after independent full runs satisfy the measured
   reproducibility contract, then ratchet without allowing a lower score unless
   P35 records an override.

Acceptance:

- Seeded weak assertions produce a surviving mutant that ordinary coverage
  misses.
- Tool failure, parser drift, and zero-mutant runs cannot pass.
- Mutation never extends the blocking PR critical path beyond 12 minutes;
  advisory completion may report separately.

Verification:

```bash
python3 -m pytest tests/test_mutation_test.py -q
python3 -m fettle.mutation_test --root . --paths fettle/ --json
```

Status 2026-08-07: explicit merge-base and full-source selection, pinned engine
validation, strict result parsing, fail-closed zero-mutant and tool-error states,
a seeded surviving-mutant fixture, and advisory changed/full CI lanes are
implemented. Retained runs `31183880854`, `31183880954`, and `31183881105`
are invalid: every report is `tool_error` because the mutation environment
omitted the PyYAML test dependency. The workflow now installs the development
dependencies, and a strict evaluator requires reproducible successful full runs
before establishing the baseline and ratchet. Replacement runs
`31186179762`, `31186179925`, and `31186180110` also remain invalid because the
baseline test suite requires Semgrep, which the development extra omitted. The
workflow now installs all runtime tools. P34 has not graduated.

Runtime note 2026-08-07: full runs `31187357044`, `31187357306`, and
`31187357350` passed the unmutated baseline but each reached the 1,800-second
wrapper limit. The next candidate uses mutmut's native pytest-testmon
integration to retain full production-file scope while selecting tests by
recorded code dependencies. Its runner is pinned in retained evidence. Held-out
run `31193102459` also reached the 1,800-second limit and retained a fail-visible
`tool_error`, so dependency selection alone is insufficient. A manually
dispatched diagnostic run may use a 7,200-second wrapper limit to measure total
completion time; routine PR and scheduled limits remain unchanged. That timing
will size the next complete, non-overlapping sharding experiment and is not
itself graduation evidence. Diagnostic run `31197332468` reached that 7,200-second
limit without completing. Full scheduled and manual evidence therefore runs as
twelve deterministic, size-balanced shards with 1,800-second worker bounds. A
separate aggregator accepts the run only when every shard completes against the
same revision and execution identity and the file scopes are complete and
non-overlapping. Held-out run `31209029718` showed that twelve-way source-byte
balancing is still too coarse: all eleven retained workers reached the
1,800-second wrapper limit, shard 8 lost its runner with exit 143 before upload,
and the aggregator correctly rejected the incomplete set. The next bounded
experiment uses 48 deterministic partitions without changing scope, timeout,
or aggregation integrity.

Runtime note 2026-08-08: revision `e3706df` uses 240 test-cost-weighted line
partitions and 20-line chunks for the measured `fettle/quality_scan.py` hotspot.
Run `31246843926` completed all workers and aggregation in 1,792,060 ms, covering
154 production modules and 30,441 source lines exactly once with zero untested
mutants. Its 43.3 percent diagnostic score is not yet a baseline; canonical
survivor identity must be implemented before independent calibration runs by the
[mutation quality plan](mutation-quality-implementation-plan.md).

Runtime note 2026-08-09: canonical replacement, insertion-only, deletion-only,
multiline, repeated-source, and invalid-Python handling is implemented. Bounded
per-mutant diagnostics, fresh-cache corpus preflight, the public
`fettle mutation preflight` command, retained preflight evidence, and the CI
fan-out gate are committed. Full live preflight, archived-range replay,
authoritative calibration, and baseline establishment remain open and are owned
by P62-P65 below. P34 retains ownership of mutation selection, canonicalization,
execution, and CI evidence infrastructure; its implemented preflight slice
satisfies P62's code dependency. P62 owns live proof, replay, calibration, and
baseline acceptance, so P34 remains in progress without blocking P62's first
step.

#### P62-P65: Mutation Learning Follow-Through Registry

This registry is part of the authoritative activity plan. The detailed mutation
contract remains in
[mutation-quality-implementation-plan.md](mutation-quality-implementation-plan.md),
but no item below may be omitted when that plan is executed or archived.
Numbering is global to preserve the requested 36-step follow-through; explicit
activity-table dependencies, not numbering alone, control cross-priority gates.

Priority means:

- **P0:** blocks authoritative mutation evidence and baseline establishment.
- **P1:** required to make the learning durable and usable in the next minor.
- **P2:** automates the methodology and extends it safely across Fettle.
- **P3:** recurring measurement and maintenance after graduation.

##### P62: Authoritative Calibration And Baseline (P0)

Execute strictly in order. A failed step returns to the cheapest preceding
falsifying check; it never authorizes skipping ahead.

1. [x] Run the pinned CI mutation preflight.
2. [x] Verify retained preflight evidence reconciles generated and canonicalized
   counts with zero collisions and zero rejected details.
3. [x] Replay historical failing shards/ranges 46, 62, 63, and 239.
4. [x] For every failure, add an adversarial fixture first, fix the generic
   contract, and rerun fixtures, corpus preflight, and narrow replay.
5. [x] Run one complete held-out authoritative calibration.
6. [x] Launch the second calibration only after the first is authoritative.
7. [x] Compare revision, scope, identities, outcomes, policy/configuration
   digests, invalidation inputs, and runtime across both reports.
8. [x] Establish the baseline only when both reports satisfy the reproducibility
   contract and contain zero untested mutants.

P62 completion evidence: retained preflight and replay artifacts, two accepted
independent report IDs for one revision, comparison output, and the reviewed
baseline digest.

Accepted evidence: preflight `31821815789` and replay `31831754903` on
`9eef2fab60c504e26be176db123164bc46e593fe`; independent complete reports
`31850858224` and `31865158733`; 14,107 killed, 14,611 survived, 5 native
timeouts, zero suspicious, and zero untested outcomes in both reports; score
and floor 49.1 with target 80.0; baseline digest
`4fe9e0fb238ad72169109b3d45666c54b83904bf5233d5568acaf2ac448e4a4c`.

##### P63: Durable Learning And Developer Experience (P1)

9. [x] Create `docs/mutation-quality-playbook.md` documenting the validation
   funnel, evidence invariants, cache isolation, exit semantics, and recovery.
10. [x] Link the playbook from `README.md`, mutation documentation, and CLI help;
    execute every copied command in a temporary project.
11. [x] Add concise mutation invariants to repository-local agent instructions:
    full runs are held-out verification; use fixtures -> preflight -> narrow
    replay -> full run; distrust engine IDs and unverified caches; calibrate
    sequentially.
12. [x] Store the reusable evidence-integrity lessons in the persistent knowledge
    wiki and link back to this plan when the connection is useful.
13. [x] Update WP3.5 completion state and hypothesis records with implementation
    and retained-run evidence.
14. [x] Add every historical mutation failure to the permanent adversarial
    fixture corpus; shard numbers remain provenance, never runtime logic.
15. [x] Add mutation readiness to `fettle doctor`.
16. [x] Make human preflight output show scope, engine, generated,
    canonicalized, rejected, collisions, and one next action.
17. [x] Preserve complete bounded diagnostics in JSON artifacts without secrets
    or absolute paths.
18. [x] Document and test exit 0 as success, exit 1 as valid policy failure, and
    exit 2 as configuration, tool, or evidence-integrity failure.
19. [x] Add setup and troubleshooting examples for missing mutmut, unsupported
    versions, unmapped tests, stale caches, parser drift, and collisions.
20. [x] Manually validate first-time, success, empty, error, and recovery CLI
    flows using the installed executable in a clean sample repository.

P63 completion evidence: linked playbook, automatic agent instruction surface,
doctor and CLI acceptance output, adversarial corpus, and manual UAT record.

Correction 2026-08-15: implementation, automated contracts, and error-state UAT
are complete, but the required installed-CLI success flow exceeded its manual
120-second window. That timeout proves timeout handling only; it does not satisfy
the successful preflight criterion. P63 remains in progress until a fresh
installed sample exits 0 with complete collision-free canonical evidence and
the copied validation-funnel commands are exercised successfully.

Corrective evidence 2026-08-15: an exact rebuilt wheel in a dedicated
environment completed preflight with 6 generated = 6 canonicalized details,
zero rejected details, and zero collisions. The copied changed-scope flow then
killed 6/6 mutants with no timeout, suspicious, or untested outcomes. P63 is
complete; the original timeout remains error-path evidence only.

##### P64: Automated Methodology And Fettle-Wide Adoption (P2)

21. [ ] Add a Fettle rule that detects full mutation workflows without a
    successful preflight dependency.
22. [ ] Detect unpinned mutation tools and missing retained preflight artifacts.
23. [ ] Detect parallel authoritative calibration runs and require sequential
    confirmation.
24. [ ] Require adversarial regression tests whenever canonicalization behavior
    changes.
25. [ ] Bind preflight artifacts to revision, policy, source scope, test mapping,
    engine, and manifest digest.
26. [ ] Verify every full worker consumes preflight and manifest evidence with
    those exact identities.
27. [ ] Apply the staged readiness -> execution -> policy model to other
    expensive Fettle providers, starting from measured failure risk.
28. [ ] Keep readiness, execution outcomes, and policy decisions separate in
    every migrated provider contract and output.
29. [ ] Treat provider caches as untrusted optimizations; require complete cache
    identity validation before reuse.
30. [ ] Standardize bounded diagnostics across providers: stage, subject,
    reason, evidence, and one recovery action.
31. [ ] Add narrow historical replay suites before expensive end-to-end checks
    for each migrated provider.

P64 completion evidence: rule fixtures, workflow violations detected in CI,
identity-bound worker tests, and at least one additional provider proving the
staged model without a false-clean path.

##### P65: Measurement And Ongoing Operations (P3)

32. [ ] Monitor preflight duration and failure categories without collecting
    source content or secrets.
33. [ ] Track parser drift and accepted vocabulary by pinned mutmut version.
34. [ ] Promote every production mutation failure into a permanent regression
    fixture before closing the incident.
35. [ ] Review the playbook, invariants, fixtures, and identity contract during
    every mutation-engine upgrade.
36. [ ] Recalibrate only when engine, scope, policy, mapping, or canonical
    identity semantics change; otherwise retain the accepted baseline.

P65 is recurring and never marked complete globally. Each release records its
monitoring window, new fixtures, upgrade review, and any recalibration trigger.

#### P66-P71: First-Class Evidence Contract Convergence

##### Program User Story

As a developer or platform engineer relying on Fettle, I want every consequential
assurance result to identify what was observed, by which producer, against which
source and policy, with what completeness and freshness, so that an evidence
reference can be validated independently rather than trusted as an opaque string.

##### Program Boundary And Decisions

- Evidence becomes a first-class portable contract, not a mandatory service or
  central registry.
- A canonical artifact is an immutable observation envelope. Findings, policy
  decisions, overrides, statistics, and compliance summaries remain separate
  domain objects that may reference or aggregate artifacts.
- Content identity and execution occurrence are distinct. Full SHA-256 identifies
  canonical content; a separate run/observation ID identifies one execution.
- Result state, completeness, trust class, freshness, and policy disposition are
  orthogonal. No single confidence score or evidence lattice replaces them.
- Freshness is evaluated against requested source, policy, scope, and producer
  identities. A generic TTL is not sufficient proof of applicability.
- Specialized reports may be stronger than the common envelope. Mutation,
  graph, CI, UAT, and integration schemas are referenced or wrapped without
  discarding their domain-specific invariants.
- Git and retained portable artifacts remain authoritative. Persistence is an
  optional measured optimization, never required for bootstrap or recovery.
- Existing persisted schemas receive explicit readers or migrations where
  concrete compatibility is required; legacy data is never silently reinterpreted.

```text
P6/P8 references + P33 non-pass + P44 contracts
                       |
                       v
               P66 contract freeze
                       |
                       v
            P67 kernel + verify pilot
                       |
                       v
              P68 CI/trace/explain
                       |
                       v
               P69 producer migration
                       |
                       v
                P70 advisory proof
                       |
                       v
          P71 graph references/persistence gate
```

P41 may consume P67's accepted artifact contract after P38 and P41 receive their
own authorization. It is not a prerequisite for P68, and P68 does not implement
P41's durable attestation substrate.

##### P66: Inventory And Freeze The Portable Contract (P0)

Goal: establish one vocabulary and compatibility boundary before changing any
authoritative producer.

1. [ ] Inventory every evidence producer, reference, reader, persistence format,
   schema version, identity rule, retention rule, and authority decision. Cover
   trace, findings, dispatcher, verify, CI, coverage, UAT, integrations,
   mutation, overrides, ratchet, compliance, provider facts, and graph records.
2. [ ] Classify each representation as primary observation, reference,
   domain-specific report, attestation, diagnostic, aggregate statistic, or
   policy disposition. Record current and target ownership; do not force
   aggregates into the artifact contract.
3. [ ] Define `EvidenceArtifact` schema v1 with schema version, artifact/content
   digest, evidence kind, producer identity/version, result state, completeness,
   trust class, source snapshot/revision, policy digest, scope digest,
   observation/run ID, observed time, bounded payload, and optional parent
   references.
4. [ ] Define `EvidenceReference` v2 as the additive successor to the current
   `evidence_id`/`kind` reference, with full artifact digest, kind, schema
   version, and only the expected bindings needed by a consumer to detect a
   mismatched artifact. Keep the current representation readable only under the
   explicit compatibility rules in step 7.
5. [ ] Specify canonical UTF-8 JSON, Unicode/path normalization, deterministic
   ordering, full SHA-256 identity, digest exclusions, maximum sizes, and
   unknown-field/version behavior.
6. [ ] Define validity outcomes for missing, malformed, unsupported, tampered,
   incomplete, stale, wrong-source, wrong-policy, wrong-scope, wrong-producer,
   and unavailable referenced artifacts. Consequential consumers map all such
   cases to canonical non-pass outcomes.
7. [ ] Define the compatibility matrix for trace schema v1/v2, existing
   verification and CI stamps, findings with bare evidence IDs, overrides,
   mutation schema v2, and provider fact sets. Name read-only, migrate, reject,
   and expiry behavior explicitly.
8. [ ] Rename planned meanings, not persisted fields: `ratchet.Evidence` becomes
   `RuleEvidenceStats`, and `ControlEvidence` becomes
   `ControlCoverageSummary` when their implementation package executes.
9. [ ] Write adversarial fixtures before runtime implementation for digest
   collision injection, tampering, duplicate IDs, replay under another revision,
   policy/scope mismatch, partial evidence, unknown producer/version, oversized
   payload, absolute-path leakage, Unicode ambiguity, and embedded secrets.

Primary files:

- `docs/evidence-artifact-contract.md` (new)
- `fettle/finding.py`
- `fettle/trace.py`
- `fettle/provider_contract.py`
- `fettle/graph_types.py`
- `tests/fixtures/evidence/` (new)

P66 completion evidence: reviewed producer/consumer matrix, accepted schema and
compatibility contract, canonical examples, threat model, and executable
adversarial fixtures. No authoritative runtime behavior changes in P66.

Status 2026-08-09: complete. The portable contract, producer/consumer inventory,
compatibility matrix, canonical artifact/reference examples, validity mapping,
threat model, and machine-readable adversarial corpus are frozen in
`docs/evidence-artifact-contract.md` and `tests/fixtures/evidence/`. P66 changed
no runtime writer, reader, host wire format, or authority decision; P67 remains
separately gated.

##### P67: Canonical Evidence Kernel And Verification Pilot (P0)

Goal: prove the contract on one bounded, consequential path before broad
migration.

10. [x] Add a zero-runtime-dependency `fettle/evidence.py` containing immutable
    artifact/reference types, canonical serialization, full-digest calculation,
    construction, parsing, and validation. Keep it independent of graph and
    persistence modules.
11. [x] Separate artifact content digest from observation/run identity. Prove
    equal content across independent runs has equal content identity but distinct
    occurrence identity, and that neither can substitute for the other.
12. [x] Centralize bounded payload validation, redaction, repository-relative
    path normalization, secret filtering, and safe diagnostic rendering. Reject
    unsupported values instead of stringifying arbitrary objects into authority.
13. [x] Add explicit binding validation for requested source, policy, scope,
    producer, schema, and freshness. Return typed validity reasons and one safe
    recovery action without embedding source bodies or secrets.
14. [x] Extend `EvidenceReference` additively and implement the P66 compatibility
    matrix for legacy readers: read-only, migrate, reject, and expiry paths each
    receive executable tests and rollback behavior. Preserve existing host wire
    formats until dispatcher/agent conformance tests authorize a version change.
15. [x] Pilot canonical artifacts in `fettle verify`: bind the exact source
    state, effective policy, affected workspace/scope, runner identity, command
    outcome, and run occurrence to the verification stamp.
16. [x] Prove verification evidence cannot authorize another revision, dirty
    state, policy, workspace, producer version, or expired/invalidated request.
17. [x] Preserve concise human output while retaining the complete bounded
    artifact in machine-readable output; interruption or write failure cannot
    leave a parseable success artifact.

Primary files:

- `fettle/evidence.py` (new)
- `fettle/finding.py`
- `fettle/verify_gate.py`
- `tests/test_evidence.py` (new)
- `tests/test_finding.py`
- `tests/test_verify_gate.py`

P67 completion evidence: cross-process deterministic artifact tests, adversarial
binding tests, installed-CLI verification UAT, legacy-stamp compatibility tests,
and no regression in hook or verification latency budgets.

Status 2026-08-15: complete. `fettle/evidence.py` implements the frozen P66
artifact/reference schema, deterministic serialization, full content identity,
separate occurrence identity, bounded payload handling, strict parsing, and
typed applicability validation without graph or persistence dependencies.
`fettle verify` atomically writes `.fettle/verify-evidence.json` beside the
legacy stamp and binds source, effective policy, selected scope, producer,
outcome, completeness, trust, and occurrence. Stamps that claim canonical
evidence fail closed on invalid or mismatched artifacts; legacy-only stamps
remain accepted for rollback. The frozen adversarial corpus, split-write paths,
cross-process determinism, installed-CLI flow, and compatibility are covered by
2,514 passing repository tests and the UAT report in
`docs/uat/canonical-evidence-verification.md`. P68 remains responsible for CI,
trace, and inspection migration.

##### P68: CI, Trace, And Inspection Binding (P0)

Goal: make canonical evidence independently inspectable at the authority
boundary without treating a local trace as an attestation.

18. [x] Bind CI artifacts to the exact checked-out revision or merge candidate,
    effective policy, selected scope, producer/toolchain, result state,
    completeness, and run identity. Recomputed CI evidence remains independent
    from local verification evidence.
19. [x] Reject local or prior-run references when source, policy, scope,
    producer, or run expectations do not match; prove a copied evidence ID cannot
    authorize a different candidate.
20. [x] Update trace schema additively to retain canonical artifacts or portable
    references with explicit availability. Preserve bounded redaction, rotation,
    tolerant legacy reads, and visible append failures.
21. [x] Extend `fettle explain` and reports to show producer, covered scope,
    source/policy binding, result, completeness, freshness, and the exact reason
    evidence was accepted or rejected. Human and JSON decisions must match.
22. [x] Publish the canonical attestation integration point for P41. When P41 is
    separately authorized after P38, it owns durable commit-linked implementation
    and binds signatures or platform attestations to artifact digest plus
    immutable candidate identity rather than defining a competing evidence
    schema.
23. [x] Add replay and cross-boundary tests proving local pass, stale pass,
    missing analyzer, malformed artifact, trace loss, CI tool failure, and policy
    change cannot manufacture accepted evidence.

Primary files:

- `fettle/ci_gate.py`
- `fettle/ci.py`
- `fettle/trace.py`
- `fettle/explain.py`
- `fettle/report.py`
- P41 attestation implementation files when authorized
- `tests/test_ci_gate.py`
- `tests/test_trace.py`
- `tests/test_explain.py`
- `tests/test_report.py`

P68 completion evidence: independent local/CI mismatch fixtures, retained CI
artifacts, JSON/human parity, legacy trace replay, and zero false-clean results.

Status 2026-08-15: complete. Remote CI writes an independently recomputed
canonical sidecar and validates exact candidate, policy, workflow scope,
producer implementation, result, completeness, and occurrence bindings at the
existing authority boundary. Trace stores bounded diagnostic-only references;
legacy entries remain readable, and append loss is visible without changing CI
authority. Detailed explain and report output derive human and JSON decisions
from the same inspection fields. Focused P68 tests passed, installed CLI UAT
covered accepted and malformed evidence, and 300 Stop-gate validations measured
p95 0.359 ms and maximum 3.29 ms against the existing 100 ms budget. See
`docs/uat/canonical-evidence-inspection.md`.

##### P69: Producer Migration And Override Integrity (P1)

Goal: converge assurance producers incrementally without flattening stronger
domain contracts or changing policy unexpectedly.

24. [x] Migrate coverage and UAT evidence first; retain their domain payloads,
    output states, recovery guidance, and existing acceptance semantics.
25. [x] Migrate integration and adapter evidence; map provider trust,
    completeness, determinism, applicability, and tool identity explicitly.
26. [x] Integrate mutation by referencing its complete schema-v2 report and
    calibration identities. Never replace mutant fingerprints, shard manifests,
    outcome counts, or reproducibility checks with a generic payload.
27. [ ] Bind state-consistency evidence to the canonical envelope when P53-P60
    execute, while preserving canonical-read, observer, cleanup, and consistency
    semantics as domain records.
    Deferred from this producer slice because the state-consistency migration
    remains separately gated by P53-P60 and P70.
28. [x] Strengthen overrides so accepted evidence matches revision/source,
    policy, scope, surface, check, validity period, and expected artifact kind.
    Missing resolution is non-pass where an override is authoritative, but no
    global evidence database is required.
29. [x] Rename `ratchet.Evidence` and `ControlEvidence`; link aggregates to their
    source window/digests where reproducibility is required, without pretending
    each aggregate is a primary observation.
30. [x] Add per-producer compatibility and rollback switches. Existing producers
    remain authoritative until their canonical path passes parity and review.
31. [x] Document producer-specific payload schemas, retention, invalidation,
    recovery, and any stronger guarantees layered above the common artifact.

Primary files:

- `fettle/coverage_gate.py`
- `fettle/uat/`
- `fettle/integration_base.py`
- `fettle/adapters/`
- `fettle/mutation_test.py`
- `fettle/mutation_baseline.py`
- `fettle/overrides.py`
- `fettle/ratchet.py`
- `fettle/compliance.py`

P69 completion evidence: producer contract matrices, old/new parity fixtures,
wrong-binding override rejection, migration rollback tests, and complete
domain-specific reports reachable from each canonical reference.

Status 2026-08-16: complete for the scoped coverage, UAT, integration,
mutation, override, ratchet, and compliance producers. Focused P69 tests pass
(462), the repaired BDD gate passes (10), and the unexcluded full repository
suite passes (2,631). Ruff, config validation, completion validation, and diff
checks also pass. See `docs/uat/p69-producer-migration.md`.

##### P70: Advisory Migration And Independent Graduation (P2)

Goal: prove the common contract improves integrity and operability without
creating unacceptable latency, incompatibility, or false rejection.

32. [ ] Run old and canonical evidence paths in shadow mode for at least 30
    qualifying runs per producer class; compare decisions, bindings, artifact
    availability, size, and runtime.
33. [ ] Track malformed legacy artifacts, missing references, source/policy/scope
    mismatches, stale evidence, tool errors, redaction events, trace write loss,
    false rejection, and false-clean prevention without collecting source,
    prompts, secrets, or absolute paths.
34. [ ] Establish explicit per-producer latency and size budgets from baseline
    measurements. Do not let artifact construction consume interactive hook
    budgets or make full reports unusably large.
35. [ ] Graduate verification, CI, coverage/UAT, integrations, mutation, and
    future producers independently. Require zero evidence-integrity false passes,
    reviewed compatibility evidence, bounded overhead, and tested rollback.
36. [ ] Publish evidence-quality measures: complete artifact rate,
    stale/mismatch rejection, visible tool-error rate, accepted reuse rate,
    repair path success, and incremental cost per verified change.
37. [ ] Remove a legacy writer only after every maintained reader and external
    consumer has migrated or completed its documented compatibility window.

P70 completion evidence: retained shadow reports, reviewed discrepancy ledger,
per-producer graduation records, latency/size profiles, and an explicit retain,
migrate, or reject decision for every legacy schema.

##### P71: Evidence Plane Integration And Persistence Decision (P3)

Goal: make the change-integrity evidence plane consume accepted artifacts
without turning the graph or a database into a bootstrap dependency.

38. [ ] Represent accepted evidence artifacts as immutable references from graph
    nodes, provider fact sets, obligation resolutions, and attestations; do not
    define a second graph-specific evidence identity.
39. [ ] Bind graph-dependent actions to source snapshot, policy, provider
    manifest, traversal rules, graph digest, and canonical evidence artifact.
40. [ ] Prove graph construction failure, cache loss, missing artifacts, and
    stale references cannot authorize an action; `doctor`, diagnosis, deletion,
    and rebuild remain graph- and store-independent.
41. [ ] Measure lookup volume, artifact size, recomputation cost, retention, and
    replay needs using P70 data before proposing a content-addressed evidence
    store.
42. [ ] If persistence is admitted, treat it as an untrusted derived store with
    digest validation, atomic writes, bounded queries, corruption recovery,
    privacy controls, and portable export. Otherwise close P71 with a reviewed
    no-go and continue using retained files/references.
43. [ ] Align any evidence-store decision with P51 so Fettle does not create
    independent graph and evidence databases with overlapping lifecycle and
    recovery responsibilities.

P71 completion evidence: graph/reference parity tests, recovery drills,
measured persistence admission record, and either an accepted minimal store or
a documented no-go. P71 does not authorize a hosted evidence service.

#### P35: Seeded-Defect And Recorded-Override Contract

Goal: make value and bypasses observable before promoting any gate.

Primary files:

- `fettle/finding.py`
- `fettle/trace.py`
- `fettle/suppressions_v3.py`
- `fettle/config.py`
- `fettle/config_schema.py`
- `docs/fettle.schema.json`
- `tests/fixtures/verification/` (new)
- `tests/test_trace.py`
- `tests/test_suppressions_v3.py`

Implementation slices:

1. Define a fixture manifest linking each check to clean and known-bad cases,
   the prior suite result, expected finding, and maximum runtime.
2. Add a conformance test that executes every enabled/promotable check against
   its manifest and rejects missing seeded evidence.
3. Define one override record schema with actor, reason, timestamp, expiry,
   check, scope, revision, policy digest, and evidence ID.
4. Route structured suppressions, gate bypasses, and ratchet exceptions through
   that schema. Deprecate unrecorded global bypass for CI; preserve an emergency
   interactive escape that emits a prominent trace event.
5. Report overridden distinctly from pass and expose active/expired overrides
   through `fettle report` and JSON output.

Acceptance:

- Every promoted gate catches a committed defect that the preceding assurance
  layer misses.
- CI cannot use an anonymous, reasonless, or non-expiring override.
- Expired overrides fail closed in CI and remain visible in audit output.

Status 2026-08-07: complete. The promoted `ci.verdict` gate has committed clean
and known-bad fixtures whose preceding assurance result remains green; the
registered conformance runner catches the seeded red verdict without executing
manifest-provided commands. Canonical overrides are stored separately from
legacy suppressions and bind actor, reason, timestamp, expiry, check, scope,
revision, effective CI-policy digest, prior evidence, and surface. The enforcing
CI Stop gate applies only an exact active match, emits an auditable `overridden`
non-pass outcome, and fails closed for missing, mismatched, future-dated,
expired, invalid, or unauditable records. Evidence: `fettle verification check
--check ci.verdict` passed; override CLI UAT passed; the full suite passed with
2262 tests; Ruff and `git diff --check` passed; `fettle check --changed` reported
no errors (11 existing/non-blocking CLI print warnings).

#### P36: Independent Red-Before-Green Reconstruction

Goal: prove a new behavior test detects the absence of its implementation
without trusting agent-authored assertions about execution order.

Primary files:

- `fettle/tdd_gate.py`
- `fettle/changeset.py`
- `fettle/worktrees.py`
- `fettle/verify.py`
- `tests/test_tdd_gate.py`
- `.github/workflows/ci.yml`

Implementation slices:

1. Keep edit-order guidance advisory; do not represent it as red-phase proof.
2. Define an evidence artifact containing test node identifier, command,
   expected failure signature, merge-base SHA, candidate SHA, exit status,
   bounded output hashes, duration, and exemptions.
3. In an isolated temporary worktree, apply only the selected new/changed test
   to the merge-base implementation and execute that node.
4. Require a meaningful assertion failure, not import, syntax, setup, timeout,
   or missing-tool failure.
5. Execute the same test against the candidate and require green evidence.
6. Start with Python defect fixes and behavior additions. Exempt docs,
   generated files, configuration-only changes, test-only maintenance,
   refactors with unchanged behavior, and unsupported test frameworks through
   P35's recorded override path.
7. Run advisory until at least 30 qualifying PRs establish precision and p95
   runtime; promote only if false blocks stay below 2%.

Acceptance:

- A test that passes on the base is rejected as non-proving.
- Infrastructure failures are reported as `tool_error`, not accepted as red.
- Evidence can be reproduced locally from the recorded SHAs and command.

#### P37: Versioned Behavioral Benchmark

Goal: measure whether Fettle changes improve agent outcomes rather than merely
matching static regexes.

Primary files:

- `fettle/evals_runner.py`
- `evals/README.md`
- `evals/scenarios/`
- `tests/test_evals_runner.py`
- `.github/workflows/evals.yml` (new)

Implementation slices:

1. Version scenario schema and benchmark corpus independently from Fettle.
2. Add representative bug-fix, feature, refactor, missing-tool, contradiction,
   underspecification, refusal, and recovery scenarios with executable outcome
   checks.
3. Replace regex-only grading where possible with tests, exit codes, file
   containment, and behavior-preservation checks.
4. Record benchmark version, Fettle commit, runner/model identity when exposed,
   prompt/workflow digest, success, turns, duration, token/cost data when
   exposed, interventions, and unrelated regressions.
5. Run at least three repetitions for live comparisons and report median,
   range, and failure distribution. Indeterminate runs remain separate.
6. Keep static schema and grader tests blocking. Run live evals only for
   relevant prompt/workflow/agent/tool changes or on schedule; begin advisory.
7. Store raw transcripts as access-controlled, bounded artifacts with secret
   redaction; publish only aggregate results by default.

Acceptance:

- The benchmark detects one seeded behavior regression missed by unit tests.
- A candidate cannot appear improved solely by dropping indeterminate runs.
- Corpus changes produce a new benchmark version and do not rewrite historical
  results.

#### P38: Canonical Traceability And Drift Evidence

Goal: connect specifications, scenarios, tests, governed code, and executed
results without relying on filename similarity.

Primary files:

- `fettle/spec_model.py`
- `fettle/trace_requirements.py`
- `fettle/spec_audit.py`
- `fettle/semantic.py`
- `tests/test_spec_model.py`
- `tests/test_spec_audit.py`

Implementation slices:

1. Make `spec_model.py` stable IDs and scenario markers canonical; deprecate
   filename-substring inference in `trace_requirements.py`.
2. Validate that markers target existing active specifications and scenarios.
3. Bind successful test result evidence to scenario markers; declaration alone
   counts as linked but not verified.
4. Use spec `scope` globs to flag code changes whose governing active spec was
   neither changed nor explicitly reviewed in an audit artifact.
5. Report uncovered scenarios, unknown markers, unlinked tests, changed governed
   regions, and executed specification coverage separately.

Acceptance:

- Renaming prose or files does not break stable IDs.
- A marker in a skipped or failing test does not count as verified coverage.
- A changed governed file without spec review produces an actionable advisory.

#### P39: Static And Supply-Chain Operationalization

Goal: use proven ecosystem controls before writing bespoke scanners.

Primary files:

- `.github/workflows/ci.yml`
- `.github/dependabot.yml` (new if Dependabot is selected)
- `fettle/supply_chain.py`
- `fettle/secret_scan.py`
- `fettle/complexity_check.py`
- `fettle/boundary_rules.py`
- `pyproject.toml`

Implementation slices:

1. Record strict-type coverage and ratchet it; keep mypy advisory until its
   accepted baseline reaches zero blocking findings.
2. Add scheduled dead-code reporting with reviewed exclusions; do not block
   until seeded defects and precision justify promotion.
3. Run architecture-boundary rules in CI and test cycles as well as hooks;
   retain language-specific limitations in output.
4. Add GitHub dependency review, vulnerability, license, and branch-history
   secret scanning with pinned actions and severity policy.
5. Retain release SBOM, build provenance, Sigstore/SLSA attestation, pinned
   tools, and RECORD verification already present.
6. Do not build package popularity, maintainer-count, or download-volume scoring
   into Fettle; use human dependency review for ambiguous trust decisions.

Acceptance:

- New vulnerable, incompatible-license, or secret-bearing fixtures are caught
  at the configured boundary.
- Scanner unavailability follows P33 and never becomes clean.
- Existing core runtime dependencies remain empty.

#### P40: Selective Invariant And Flake Verification

Goal: add independent runtime signal only where a concrete invariant or
nondeterminism risk exists.

Primary files:

- `tests/`
- `.github/workflows/ci.yml`
- `.github/workflows/flake.yml` (new)
- `fettle/pact_adapter.py`
- `fettle/blackduck_adapter.py`

Implementation slices:

1. Introduce Hypothesis as a development-only dependency for selected parsers,
   policy resolution, path containment, event normalization, and state-machine
   invariants; store minimized failing examples as ordinary regression tests.
2. Add a scheduled repeat-run flake job, classify failures by stable test ID,
   and require owner, issue, first-seen date, and expiry for quarantine.
3. Keep quarantined tests visible and excluded only from the blocking lane;
   expired quarantine fails the maintenance job.
4. Describe Pact honestly as broker-status integration unless Fettle invokes
   provider/consumer verification; do not claim contract execution otherwise.
5. Add performance or memory gates only for measured critical paths with stable
   environments; begin with dispatcher budget regressions.

Acceptance:

- A seeded nondeterministic test is detected and cannot disappear silently.
- At least one property finds or prevents an edge case not covered by examples.
- Performance gates compare like environments and expose variance.

#### P41: Commit-Linked Governance Evidence

Goal: evolve mutable local traces into queryable evidence with tamper detection
without creating a hosted control plane.

Primary files:

- `fettle/trace.py`
- `fettle/provenance_gate.py`
- `fettle/session_report.py`
- `fettle/lineage_report.py`
- `fettle/scope_creep.py`
- `fettle/loop_detect.py`
- `fettle/claims_gate.py`

Implementation slices:

1. Define a versioned run manifest linking normalized agent identity when
   available, runner/model version when exposed, workflow/prompt digest, policy
   digest, specification IDs, repository commit, parent run, and evidence IDs.
2. Hash-chain records and periodically anchor the terminal digest to a commit,
   CI artifact attestation, or signed release artifact. Describe this as
   tamper-evident, not immutable.
3. Preserve bounded redaction and make rotation retain chain checkpoints and
   retention metadata.
4. Extend loop detection from identical calls to repeated edits of the same
   region with unchanged test outcomes; remain advisory until precision is
   measured.
5. Add configurable file/module/diff thresholds. Interactive excess requests
   review; Fettle-owned runners may stop. External host sessions cannot be
   universally terminated.
6. Enforce token ceilings only where runners expose usage and Fettle owns their
   lifecycle; wall-clock ceilings remain universally available for owned
   subprocesses.

Acceptance:

- Editing or deleting a middle ledger record breaks chain verification.
- Every generated commit can identify its governing evidence when Fettle owns
  the commit flow; externally created commits report coverage as unknown.
- Secrets and raw prompts are not persisted by default.

#### P42: Deterministic Event And Check Replay

Goal: reproduce Fettle decisions without claiming deterministic reproduction of
external models or arbitrary hosts.

Primary files:

- `fettle/event.py`
- `fettle/agents/`
- `fettle/dispatcher.py`
- `fettle/trace.py`
- `fettle/runners/`
- `fettle/replay.py` (new)
- `tests/test_replay.py` (new)

Implementation slices:

1. Define a recording bundle containing normalized events, effective policy,
   relevant file-content hashes or explicitly included fixture snapshots,
   check versions, runner response fixtures, monotonic offsets, and run ID.
2. Inject clock and runner seams only into workflow code that Fettle owns; do
   not ban ordinary wall-clock use repository-wide.
3. Replay dispatcher selection and check decisions with network and model calls
   replaced by recorded responses.
4. Add fault points for timeout, malformed response, truncated output, runner
   error, and bounded file-write failure at Fettle-owned interfaces.
5. Compare canonical result states, findings, evidence IDs, and side-effect
   manifests while ignoring explicitly nondeterministic presentation fields.
6. Profile representative owned paths: dispatch, config, analyzers, subprocess
   wait, and runner wait. Keep model inference separate when host telemetry is
   unavailable.

Acceptance:

- A recorded scanner parse failure reproduces the same canonical decision
  without network or token use.
- Fault injection covers each owned interface and produces P33-compliant
  non-pass outcomes.
- Recording bundles are bounded, redacted, schema-versioned, and portable.

#### P43: Narrow Formal-Methods Decision Gate

Goal: use formal methods only after evidence identifies a consequential
concurrent state machine.

Candidate scope:

- Worktree claim and locking transitions.
- Verification-stamp invalidation under concurrent edits.
- Retry/idempotency behavior in a future Fettle-owned background UAT runner.

Entry criteria:

- A documented safety invariant whose violation loses work, attributes work to
  the wrong actor, or accepts stale verification.
- At least two interacting actors or retry paths that example and property
  tests cannot cover economically.
- An implementation owner capable of reviewing TLA+/PlusCal independently.

Deliverable if admitted:

1. A narrow model and explicit environment assumptions.
2. Checked invariants and retained counterexamples.
3. Property/state-machine tests derived from the same invariants.
4. A refinement map from model actions to implementation operations.

Do not model a Fettle agent scheduler unless Fettle later owns one. P43 remains
advisory; a plausible-looking model is not release evidence.

Status 2026-08-07: `PolicyCapsule` and `WorkItemClaims` models are implemented,
mutation-checked, and CI-gated. Verify Gate, Dispatcher, and TDD Gate models are
not implemented. The required property/state-machine tests and refinement maps
from model actions to implementation operations also remain, so P43 is not
complete.

#### Program Sequence And Graduation

```text
P33 evidence integrity
  +--> P34 mutation integrity
  +--> P35 seeded defects + overrides
          +--> P36 red/green reconstruction
          +--> P38 traceability
          +--> P39 static + supply chain
P33 + existing eval substrate --> P37 benchmark
P37 + P33 --> P40 properties + flakes
P35 + P38 --> P41 governance evidence
P33 + P37 + P41 --> P42 replay
P40 + P42 --concrete concurrency need--> P43 formal model
```

| Stage | Packages | Graduation evidence |
|---|---|---|
| A: Trust existing results | P33 | All scanner failure modes are canonical non-pass; seeded fixtures pass |
| B: Operationalize existing controls | P34, P35 | Mutation is honest and bounded; each promoted check has value and override evidence |
| C: Add independent evidence | P36, P37, P38 | CI reconstructs red/green; benchmark variance and executed spec coverage are reported |
| D: Broaden assurance selectively | P39, P40 | Ecosystem controls and invariant tests meet precision and runtime budgets |
| E: Govern and reproduce | P41, P42 | Evidence is commit-linked and tamper-evident; owned decisions replay offline |
| F: Formalize only proven risk | P43 | Entry criteria are documented and independently approved |

No later stage is authorized merely because this plan exists. Each package ends
with a proposal review and requires explicit agreement before implementation.

#### Pull-Request And Scheduled Budgets

| Check group | Placement | Initial status | Budget |
|---|---|---|---:|
| Ruff, Semgrep, boundaries, secrets, spec lint | PR | Blocking after P33 | 2 min |
| Unit tests and branch coverage | PR, parallel matrix | Blocking | 8 min |
| Type and architecture ratchets | PR | Advisory first | 3 min |
| Changed-module mutation | PR, separate completion | Advisory first | 10 min hard bound |
| Eval schema and deterministic graders | PR | Blocking | 1 min |
| Red/green reconstruction | Qualifying PRs | Advisory first | 5 min target |
| Live repeated model evals | Relevant PR or scheduled | Advisory | Outside normal critical path |
| Full mutation, dead code, and flake detection | Nightly | Advisory until graduated | 30-60 min |
| Full dependency/service integrations | PR or scheduled by policy | Policy-controlled | 5-10 min |

Jobs run in parallel. The blocking critical path must remain at or below 12
minutes at p95 across 20 runs. A package that exceeds its budget is moved out of
the critical path or redesigned before enforcement.

#### Program-Level Blast Radius

Highest-risk surfaces:

- `fettle/result.py`, `fettle/finding.py`, and `fettle/tool_runner.py`: result
  semantics shared by all checks.
- `fettle/quality_scan.py` and `fettle/ci.py`: CI trust boundary.
- `fettle/trace.py`: every audit and evidence consumer.
- `fettle/config.py`, schema, and suppressions: policy and bypass behavior.
- `fettle/dispatcher.py`: interactive fail-open behavior must not regress.
- `fettle/changeset.py` and worktrees: merge-base and isolation correctness.
- GitHub workflows: PR latency, permissions, secrets, and release behavior.

Required controls:

- Run `kgraph impact` before each behavior-changing package.
- Land one result-producing integration at a time with parity tests.
- Never conflate interactive fail-open with CI fail-closed semantics.
- Pin third-party actions and tools; bound subprocess output and time.
- Use temporary worktrees without mutating the operator's working tree.
- Preserve zero core runtime dependencies.
- Run four-agent event conformance after dispatcher or replay changes.
- Run package smoke, full tests, Fettle scan, and manual CLI acceptance before
  release.

#### Program Success Criteria

P33-P42 are complete only when:

1. No required tool failure, timeout, malformed output, or zero-result parse is
   represented as pass.
2. Every enforced check has a seeded defect, declared cost, recovery action,
   and recorded override.
3. Red-before-green evidence is independently reconstructed for supported
   qualifying changes.
4. Mutation score and behavioral benchmark results identify their engine/corpus
   versions and preserve indeterminate outcomes.
5. Specification coverage distinguishes declared links from executed evidence.
6. Required supply-chain controls run without adding core runtime dependencies.
7. Governance evidence is commit-linked, bounded, redacted, and tamper-evident.
8. Fettle-owned event/check decisions replay offline from a versioned bundle.
9. Interactive hooks remain responsive and visibly fail-open; CI remains
   independently fail-closed.
10. Blocking PR p95 stays at or below 12 minutes for 20 consecutive runs.

#### Deliberate Non-Goals

- Universal deterministic replay of external agent hosts.
- Repository-wide prohibition of wall-clock APIs.
- Package trust scoring based on popularity or maintainer counts.
- Automatic property generation from unrestricted natural-language prose.
- Fettle-owned staging infrastructure for arbitrary applications.
- A TLA+ model of an agent scheduler Fettle does not own.
- Mandatory live-model evaluation on every pull request.
- Universal red-before-green enforcement for non-behavioral changes.

## 5. Dependency Spine

```text
v1.7 correctness and policy parity
        |
        v
R1 evidence-rich finding contract + agent eval baseline
        |
        v
R2 canonical workspace and adapter execution substrate
        |
        +----------------------+-----------------------+
        v                      v                       v
R3 JS/TS proving ground   R4 generic ingestion   R5 shell hardening
        |
        +----------+-----------+
                   v
          R6 .NET and Java adapters
                   |
                   v
          R7 framework policy packs
                   |
                   v
          R8 semantic-delta checks
                   |
                   v
          R9 thin MCP + broader LSP
```

No downstream release starts until its predecessor's graduation trigger is
met. Parallel work is allowed only where the graph explicitly branches.

## 6. Release Plan

### R0: v1.7 Trust Foundation

Owner: existing audit plan, not this plan. Status: COMPLETE in v1.7.0.

Required completion evidence:

- Normalized enforcement parity across Claude, Codex, Gemini, and OpenCode.
- One canonical policy resolver used by runtime and inspection.
- Capsule and MCP-trust bypass findings closed with adversarial tests.
- Verification stamps bound to session, source state, and verified scope.
- VS Code process invocation no longer interpolates untrusted shell strings.
- Existing Fettle quality scan and CI matrix green.

Graduation trigger: the v1.7 re-audit criteria pass. Polyglot work must not
build additional execution surfaces on unresolved policy divergence.

### R1: v1.8 Evidence And Agent Ergonomics

Goal: make every Fettle verdict actionable and measurable before broadening
language reach.

#### WP-201: One Canonical Finding Envelope

Change:

- Extend `fettle/dispatcher_types.py` so dispatcher results carry structured
  findings and evidence references rather than only a message string.
- Treat `fettle/finding.py` as the canonical finding schema; version it for
  additive fields including `impact`, `action`, `evidence_id`, and
  `result_state` (`pass`, `violation`, `tool_error`, `unknown`).
- Preserve host-specific rendering in `fettle/dispatcher_aggregate.py`.
- Update trace serialization in `fettle/trace.py` to store bounded structured
  evidence without source content.
- Add concise, detailed, and JSON rendering in `fettle/report.py` and
  `fettle/explain.py`.

Acceptance:

- No check crash, missing binary, timeout, or malformed tool output can become
  a pass.
- Existing check implementations can migrate one at a time through a temporary
  compatibility constructor; remove it before R2 closes.
- Output schema tests cover every decision and result state.

Verification:

```bash
python -m pytest tests/test_finding.py tests/test_output_schema.py tests/test_dispatcher.py tests/test_explain.py -q
python3 fettle/cli.py check --changed
```

#### WP-202: Evidence Artifacts

Change:

- Add bounded command, exit, timing, scope, and tool-version evidence to
  minutes-world operations.
- Attach evidence identifiers to verify, coverage, UAT, CI, and integration
  stamps.
- Never write secrets, raw source, repository identifiers, or unredacted
  environment values to global telemetry.

Primary files:

- `fettle/verify_gate.py`
- `fettle/coverage_gate.py`
- `fettle/uat/`
- `fettle/ci_gate.py`
- `fettle/integration_base.py`
- `fettle/finding.py`

Verification: stamp contract tests plus redaction fixtures.

#### WP-203: Agent-Ergonomics Evaluation Suite

Change:

- Extend `evals/scenarios/` from two scenarios to a maintained corpus covering
  finding comprehension, repair, rerun, repeated-block recovery, missing-tool
  behavior, and concise versus detailed output.
- Record repair success, turns-to-repair, repeated violation, diagnostic bytes,
  and indeterminate runs.
- Add held-out scenarios before tuning messages.

Primary files:

- `evals/README.md`
- `evals/scenarios/`
- `fettle/evals_runner.py`
- `tests/test_evals_runner.py`

Graduation trigger:

- All existing gates emit the canonical result state.
- Baseline agent metrics are recorded for at least Python and TypeScript.
- Every non-pass path supplies a recovery action.

### R2: v1.9 Canonical Workspace And Adapter Substrate

Goal: remove duplicated language assumptions and make workspace routing the
single source of execution context.

#### WP-210: Consolidate Workspace Models

Current issue: `fettle/profile.py` and `fettle/workspace.py` define overlapping
workspace models and marker registries.

Change:

- Make `fettle/workspace.py` own one `Workspace` model containing path,
  language, frameworks, manager, wrapper, commands, source roots, test roots,
  dependency files, and lockfiles.
- Make `fettle/profile.py` return those workspaces and retain cache/provenance.
- Support nested workspaces, longest-prefix routing, root shared files, and
  deleted-file routing.
- Replace the current one-level fallback with bounded marker discovery that
  excludes generated/vendor directories.
- Add config overrides per workspace, not only `profile.workspaces[0]`.

Markers added:

- `.sln`, `.slnx`, `.csproj`, `global.json`
- `pom.xml`, `mvnw`, `build.gradle`, `build.gradle.kts`, `gradlew`
- Existing Python, Node, Go, and Rust markers

Primary files:

- `fettle/workspace.py`
- `fettle/profile.py`
- `fettle/config.py`
- `fettle/config_schema.py`
- `docs/fettle.schema.json`
- `tests/test_workspace.py`
- `tests/test_profile.py`

#### WP-211: Strengthen The Adapter Protocol

Change `fettle/adapters/__init__.py` to define:

```python
class LanguageAdapter(Protocol):
    language: str
    extensions: frozenset[str]
    def supports(self, workspace: Workspace) -> bool: ...
    def classify(self, path: str, workspace: Workspace) -> FileKind: ...
    def lint(self, workspace: Workspace, files: list[str]) -> CheckRun: ...
    def format_check(self, workspace: Workspace, files: list[str]) -> CheckRun: ...
    def typecheck(self, workspace: Workspace, files: list[str]) -> CheckRun: ...
    def test(self, workspace: Workspace, files: list[str], scope: str) -> CheckRun: ...
    def build(self, workspace: Workspace) -> CheckRun: ...
    def dependency_check(self, workspace: Workspace) -> CheckRun: ...
```

`CheckRun` contains findings plus result state, command evidence, scope, and
tool errors. It does not return an empty list for execution failure.

Primary files:

- `fettle/adapters/__init__.py`
- `fettle/adapters/python_adapter.py`
- `fettle/adapters/typescript_adapter.py`
- `fettle/adapters/go_adapter.py`
- `fettle/adapters/rust_adapter.py`
- `fettle/tool_runner.py`
- `tests/test_adapter.py`
- `tests/test_polyglot_adapters.py`

#### WP-212: Adapter-Backed Dispatcher Check

Change:

- Add `fettle/adapter_check.py` as the single PostToolUse entry point.
- Resolve target file to workspace, select its adapter, and run only fast
  configured checks within the hook deadline.
- Migrate JS/TS first, then Go, then Python and Rust after parity tests.
- Remove `post_edit_ts.py` and `post_edit_go.py` only after their parity suites
  pass; retain no permanent dual paths.

Primary files:

- `fettle/adapter_check.py`
- `fettle/dispatcher_registry.py`
- `fettle/post_edit_ts.py`
- `fettle/post_edit_go.py`
- `tests/test_dispatcher.py`
- `tests/test_post_edit_ts.py`
- `tests/test_post_edit_go.py`

#### WP-213: Central File And Test Classification

Change:

- Move implementation/test/generated/config classification behind adapter and
  workspace APIs.
- Replace hardcoded extension and command lists in `quality_gate.py`,
  `verify_gate.py`, `tdd_gate.py`, `paths.py`, `bench.py`,
  `lean_sniffers.py`, and `lean_debt.py`.
- Ensure unsupported languages remain neutral rather than silently exempting a
  supported workspace.

Verification:

- A matrix test supplies each language's implementation, test, generated,
  dependency, and configuration paths to every affected gate.
- Existing Python classifications remain unchanged.

#### WP-214: Multi-Workspace Verification

Change:

- `fettle verify` groups edited code by workspace.
- Run impacted tests where the adapter has a reliable mapping; otherwise run
  the affected workspace's full suite.
- Stamp every workspace, command, source-state digest, and scope.
- Stop gate rejects omitted affected workspaces.

Graduation trigger:

- Python, JS/TS, Go, and Rust parity suites pass through `adapter_check`.
- No production gate owns a private implementation-extension list.
- Mixed Python/Node fixture runs only affected workspace commands.
- Hook latency remains inside configured budgets at p95.

Status 2026-08-05: graduated. The adapter-backed dispatcher owns all four
language routes; TypeScript and Go Semgrep parity is covered through adapter
tests and the retired hook modules are removed. Classification has no private
production implementation-extension list, deleted files remain verification
relevant, reliable Python impacted tests run per affected workspace, and a
100-invocation adapter-routing p95 contract enforces the 150 ms hook budget.

### R3: v1.10 JavaScript/TypeScript And Web Baseline

Goal: use the highest-value, partially implemented stack to prove the complete
polyglot flow.

#### WP-220: Complete Native JS/TS Tooling

- Resolve local tools through package-manager execution (`pnpm exec`, `npm
  exec`, `yarn exec`, `bunx`) before global PATH.
- Prefer repository scripts when present.
- Support ESLint or Biome lint, Biome or Prettier format, `tsc --noEmit`,
  Vitest/Jest tests, and configured build scripts.
- Correct package-manager install/build semantics; do not use `yarn ci` or
  `pnpm ci` where unsupported.
- Parse stderr as well as stdout where native tools use it.

Primary files:

- `fettle/adapters/typescript_adapter.py`
- `fettle/tool_runner.py`
- `fettle/profile.py`
- `tests/test_typescript_adapter.py`

#### WP-221: Node Workspace Discovery

- Detect npm, pnpm, Yarn, and Bun workspaces.
- Detect TypeScript from dependencies or `tsconfig*.json`.
- Detect React, Next.js, Angular, Vue/Nuxt, Svelte/SvelteKit, and HTMX markers
  as metadata without enabling strict rules.
- Route lockfile changes to all workspaces sharing that lockfile.

#### WP-222: Web LSP Parity

- Refactor `fettle/lsp_server.py` to consume the adapter-backed check service.
- Publish JS/TS diagnostics only after CLI versus LSP parity tests pass.
- Keep unsupported language selectors out of the VS Code extension.

#### WP-223: Web Behavioral Evals

Add live and static scenarios for:

- Unhandled promise
- Unsafe SQL construction
- Debug artifact
- Missing loading/error state
- Missing native analyzer
- Mixed frontend/backend workspace routing

Graduation trigger: JS/TS hook, CLI, LSP, and verify findings agree on the
maintained fixture corpus.

### R4: v1.10 Generic External Evidence Ingestion

This release may run parallel to R3 after R2 closes.

#### WP-230: Generic Command Integration

Add a configured integration capable of executing argv arrays without a shell,
with timeout, cwd, environment allowlist, expected output format, and severity
mapping.

#### WP-231: SARIF And JUnit Ingestion

- Normalize SARIF findings into `CheckFinding`.
- Normalize JUnit suite/test failures into evidence artifacts.
- Preserve external rule identifiers and locations.
- Reject malformed or oversized input as tool error.

Primary files:

- `fettle/integration_base.py`
- `fettle/integrations.py`
- `fettle/finding.py`
- `tests/test_integrations.py`
- `tests/test_sarif.py`
- `tests/test_junit.py`

Outcome: Snyk, TruffleHog, Checkmarx, SonarQube, and similar tools primarily
need documented recipes, not bespoke permanent adapters.

### R5: v1.10 Shell Mediation Hardening

This release may run parallel to R3/R4 after R1 establishes structured errors.

#### WP-240: Adversarial Shell Corpus

Extend fixtures for nested shells, command substitution, encoded execution,
pipes to interpreters, environment wrappers, SSH commands, Bash file writes,
network exfiltration shapes, and infrastructure mutation.

#### WP-241: Conservative Classification

- Keep exact allow-list semantics.
- In enforce mode, block ambiguous high-risk commands that contain a protected
  operation but cannot be safely parsed.
- Make the reason and escape route explicit.
- Record classification confidence and rule identifier.

#### WP-242: External Sandbox Contract

Document and implement an optional execution-provider interface that can hand
an agent command to an external sandbox. Fettle supplies policy and receives
the verdict; it does not implement eBPF, ptrace, containers, or network
namespaces itself.

Graduation trigger: adversarial corpus results are published with known false
positive and false negative classes; documentation never calls the hook guard
a sandbox.

### R6: v1.11 .NET And Java

Goal: add the two highest-value enterprise backends on the common substrate.

#### WP-250: .NET Workspace And Adapter

Detection:

- `.sln`, `.slnx`, `.csproj`, `global.json`, `Directory.Build.props`,
  `Directory.Packages.props`, `packages.lock.json`
- Project references and test projects
- ASP.NET Core and common test frameworks as metadata

Native operations:

- Format: `dotnet format --verify-no-changes`
- Build/type analysis: `dotnet build --no-restore`
- Test: `dotnet test --no-build` where prior evidence permits, otherwise normal
  `dotnet test`
- Dependency audit: `dotnet list package --vulnerable --include-transitive`
- Coverage: configured Coverlet output
- Static analysis: repository-configured Roslyn analyzers; no forced vendor
  analyzer dependency

Test conventions:

- `*Tests.cs`, `*Test.cs`, test projects, xUnit/NUnit/MSTest markers
- Namespace/project-reference mapping before filename fallback

Primary files:

- `fettle/adapters/dotnet_adapter.py`
- `fettle/workspace.py`
- `fettle/adapters/__init__.py`
- `fettle/coverage_gate.py`
- `tests/test_dotnet_adapter.py`
- `tests/fixtures/dotnet/`

#### WP-251: Java Workspace And Adapter

Detection:

- Maven reactor through `pom.xml` and `mvnw`
- Gradle multi-project builds through `settings.gradle*`, `build.gradle*`, and
  `gradlew`
- Java/Kotlin source sets and test source sets
- Spring Boot metadata

Native operations:

- Prefer `./mvnw` or `./gradlew`; global Maven/Gradle is fallback only.
- Compile/build and test through repository lifecycle commands.
- Ingest Checkstyle, SpotBugs, PMD, Error Prone, JaCoCo, and dependency-check
  reports only when configured by the repository.
- Do not auto-modify `pom.xml` or Gradle files to install plugins.

Test conventions:

- `*Test.java`, `*Tests.java`, `*IT.java`, JUnit/TestNG source roots
- Maven/Gradle module mapping before filename fallback

Primary files:

- `fettle/adapters/java_adapter.py`
- `fettle/workspace.py`
- `fettle/adapters/__init__.py`
- `fettle/coverage_gate.py`
- `tests/test_java_adapter.py`
- `tests/fixtures/java/`

#### WP-252: Enterprise Stack Behavioral Evals

At least one live repair scenario and one missing-tool scenario per language,
plus a mixed React/.NET and React/Java workspace scenario.

Graduation trigger:

- Clean fixture, violation fixture, malformed-output fixture, timeout fixture,
  and native sample project pass for each adapter.
- No repository build file is modified by setup.
- Wrapper-first execution is demonstrated in tests.

### R7: v1.12 Framework Policy Packs

Framework packs contain high-confidence rules not already covered by native
ecosystem analyzers. Every rule requires fire and silent fixtures, source
metadata, suggested repair, and an advisory-only observation period.

#### WP-260: Framework Pack Infrastructure

- Add pack metadata: language, framework markers, required analyzer, rules,
  default mode, confidence, and compatibility range.
- Auto-detection recommends packs but does not silently enforce them.
- `fettle doctor` explains inactive packs and missing analyzers.
- `fettle rules list` filters by language and framework.

Primary files:

- `fettle/rule_loader.py`
- `fettle/rule_integrity.py`
- `fettle/profile.py`
- `fettle/doctor.py`
- `rules/packs/`
- `tests/test_rule_integrity.py`

#### WP-261: React And Next.js Pack

Initial candidates:

- Unsafe HTML injection
- Missing loading/error/empty handling where deterministically identifiable
- Unstable list keys
- Server/client boundary misuse
- Missing page metadata where framework convention is unambiguous
- Accessibility checks delegated to established ESLint plugins where possible

Do not recreate `eslint-plugin-react`, `eslint-plugin-react-hooks`,
`eslint-plugin-jsx-a11y`, or Next.js core-web-vitals rules.

#### WP-262: ASP.NET Core Pack

Initial candidates:

- Sensitive logging
- Insecure CORS configuration
- Sync-over-async patterns
- Missing cancellation-token propagation in configured application layers
- Unsafe model-binding and authorization patterns only where high confidence
- Entity Framework migration hazards

#### WP-263: Spring Boot Pack

Initial candidates:

- Insecure actuator exposure
- Sensitive logging and configuration secrets
- Unsafe controller binding or expression use
- Entity exposure and transaction-boundary rules only where deterministic
- Blocking calls in explicitly reactive modules

#### WP-264: HTML And HTMX Pack

Initial candidates:

- Missing CSRF integration for state-changing requests
- Unsafe dynamic `hx-*` URL construction
- Unescaped fragment insertion
- Duplicate IDs likely after fragment swaps
- Missing progressive fallback for critical actions
- Focus restoration and accessible status behavior

Template support starts with plain HTML, Razor, Thymeleaf, and JSX-supported
patterns. Jinja support reuses Python-side parsing where possible.

#### WP-265: Angular Pack

Angular follows React because it has a strong enterprise footprint and builds
on the TS adapter. Initial support should consume Angular ESLint and framework
build output before adding Fettle-native rules.

Deferred until demand: Vue/Nuxt, Svelte/SvelteKit, Kotlin-specific, mobile, and
desktop framework packs.

Graduation trigger for each pack:

- Zero findings on its maintained clean corpus.
- Acceptable field false-positive rate defined before observation begins.
- At least 80% agent repair success in behavioral evals.
- No rule becomes enforce-by-default.

### R8: v1.13 Stateful Semantic-Delta Checks

Goal: detect harmful removals and session-level drift that ordinary linting
cannot see, without whole-repository snapshots.

#### WP-270: Bounded Pre-Edit Evidence

- On PreToolUse for an edited file, cache a bounded content hash and targeted
  structural summary in session state.
- On PostToolUse, compare only that file and relevant git diff.
- Respect privacy, file-size, and event-budget limits.
- Do not create a persistent semantic database.

#### WP-271: Initial Delta Rules

Candidates, in evidence order:

1. Removed error-handling block.
2. Weakened or skipped test assertion.
3. Removed authorization or validation check.
4. Deleted public API without corresponding usage/spec update.
5. Excessive file creation in one session.
6. Large edit without subsequent verification.
7. Dependency manifest change without lockfile consistency.

Use language ASTs where standard and cheap; otherwise use native analyzer or
structured diff. Regex-only rules remain advisory and clearly identified.

#### WP-272: Infrastructure Semantic Integration

Do not build custom Terraform/Kubernetes parsers. Define optional adapters for
established plan/diff tools and ingest their structured output. Block execution
only on explicit policy and high-confidence native-tool evidence.

Graduation trigger: p95 hot-path cost remains within event budgets and each
rule has measured precision plus clean/violation/delta fixtures.

### R9: v1.14 Optional MCP And Expanded Editor Support

#### WP-280: Shared Analysis Service

Extract side-effect-controlled service functions used by CLI, dispatcher, LSP,
and MCP. A parity test feeds one workspace/file/config into every surface and
compares canonical findings.

#### WP-281: Thin MCP Server

Initial tools:

- `check_content(content, file_path)`
- `check_changed()`
- `explain_finding(finding_id)`
- `get_effective_policy(path)`
- `get_session_brief()`
- `list_rules(language, framework)`

Constraints:

- Stdio transport first.
- No daemon, remote endpoint, policy mutation, automatic suppression, or
  network requirement.
- MCP responses are guidance; hooks and CI retain enforcement.
- Content passed for preflight is not written to telemetry or trace.

#### WP-282: LSP Language Graduation

Add each language selector only after adapter CLI/LSP parity passes. Publish
tool errors as explicit diagnostics or status, not an empty diagnostic set.

Graduation trigger: the same fixture produces the same canonical findings over
CLI, hook, LSP, and MCP, modulo transport fields.

### R10: Authorship Separation Enforcement

Goal: guarantee that the agent writing tests is never the same agent writing
the implementation being tested, and that the implementing agent cannot modify
the tests. This prevents an agent from manufacturing passing tests for broken
code.

#### WP-520: Role-Based File Authority

**Principle:** Tests must never be written by the same agent writing the code.
The agent running the implementation must never be allowed to change the tests.
Any changes to tests must be evaluated and implemented by a separate
independent agent.

**Design:**

Introduce a `role` policy key carried through the capsule protocol:

```python
# New policy key in .fettle.toml or capsule
[gates.authorship]
enabled = true
mode = "enforce"  # advisory | enforce
roles = ["tester", "implementer", "reviewer"]
```

The role determines which file categories a session may edit:

| Role | May edit implementation | May edit tests | May edit both |
|------|----------------------|----------------|---------------|
| `implementer` | Yes | No | No |
| `tester` | No | Yes | No |
| `reviewer` | No | No | No (read-only) |
| `solo` (default) | Yes | Yes | Yes (backwards-compatible) |

**Enforcement mechanism:**

1. `fettle spawn` accepts `--role tester|implementer|reviewer`:
   ```bash
   fettle spawn claude --task "implement item-a" --role implementer --worktree item-a
   fettle spawn claude --task "write tests for item-a" --role tester --worktree item-a-tests
   ```

2. The role is written into the policy capsule (new field: `policy.role`).

3. A new `authorship_gate.py` (PreToolUse) checks:
   - Classify the target file via `paths.classify_file()` → `"test"` or `"implementation"`
   - Compare against the session's role from the resolved capsule policy
   - Block if the role forbids editing that file category

4. The capsule's monotonic merge ensures a child cannot weaken its role:
   - `role` uses a strictness ladder: `solo > implementer/tester > reviewer`
   - A parent with `role: implementer` cannot spawn a child with `role: solo`
   - A parent with `role: solo` CAN spawn children with any narrower role

**Interaction with existing gates:**

- `tdd_gate.py`: still enforces test-first ordering within a `solo` session.
  Under authorship separation, the tester session edits tests first, then the
  implementer session is spawned — the ordering is structural, not temporal.
- `topology.py`: scope declarations ensure test and impl worktrees don't
  overlap on implementation files. The tester's scope covers `tests/`; the
  implementer's scope covers `src/`.
- `claims_gate.py`: each role claims its own work item or shares a parent
  item with disjoint file scopes.
- `verify_gate.py`: verification must be run by a session that can see both
  test and implementation results — the parent (`solo`) or a dedicated
  `reviewer`.

**Primary files:**

- `fettle/authorship_gate.py` (new)
- `fettle/policy_capsule.py` (add `role` to merge semantics)
- `fettle/spawn.py` (add `--role` parameter)
- `fettle/dispatcher_registry.py` (register new gate)
- `fettle/config_schema.py` (add `gates.authorship` schema)
- `tests/test_authorship_gate.py` (new)
- `tests/test_policy_capsule.py` (extend role merge tests)

**TLA+ extension:**

Add a `role` field to the PolicyCapsule spec and verify:
- S6 (RoleMonotonicity): a child's role is always equal or stricter than its
  parent's
- S7 (RoleFileAuthority): an agent with role `implementer` never transitions
  to a state where it edits a test file, and vice versa

**Acceptance criteria:**

1. A `role: implementer` session is blocked from writing any file classified
   as `"test"` by `paths.classify_file()`.
2. A `role: tester` session is blocked from writing any file classified as
   `"implementation"`.
3. A child agent cannot escalate its role through capsule manipulation.
4. Default behavior (`role: solo`) is unchanged — no regression for single-
   agent workflows.
5. The topology advisor recommends `writer-reviewer` or separate tester/
   implementer worktrees when role-separated items are detected.
6. TLA+ spec extended and passing with role invariants.

**Graduation trigger:**

- Role enforcement passes adversarial tests (agent attempts to edit forbidden
  file categories through path manipulation, symlinks, tool aliases).
- At least one real multi-agent session demonstrates the full flow: parent
  spawns tester and implementer children, each constrained to its file set.
- TLA+ role invariants verified via TLC.

Status 2026-08-07: role propagation, monotonic capsule merging, spawn plumbing,
and PreToolUse file-authority enforcement are implemented and unit-tested. The
TLA+ role invariants, adversarial path/symlink coverage, topology recommendation,
and evidenced end-to-end multi-agent session remain, so P52 has not graduated.

Estimate: 2–3 days.

## 7. Cross-Cutting Test Strategy

### Unit Contract

Each adapter and pack requires:

- Detection tests
- Workspace routing tests
- Clean parser output
- Violating parser output
- Malformed output
- Missing tool
- Timeout
- Non-zero exit with empty output
- Path containing spaces
- Monorepo/root wrapper behavior

### Rule Integrity

Every Fettle-native rule requires:

- `tests/fixtures/rulepacks/<pack>/<rule>/fire/`
- `tests/fixtures/rulepacks/<pack>/<rule>/silent/`
- Metadata source and intended action
- Semgrep or native analyzer validation
- Stable rule identifier

### Integration Matrix

| Surface | Required evidence |
|---|---|
| Hook | Correct host response and budget behavior |
| CLI | Correct finding and exit contract |
| Verify | Correct workspace command and bound stamp |
| LSP | Canonical finding parity before activation |
| MCP | Canonical finding parity before release |
| CI | Independent full check remains green |

### Behavioral Evaluation

Each promoted language/framework has:

- One happy repair scenario
- One clean scenario
- One missing-tool/error recovery scenario
- One held-out scenario
- Recorded turns, diagnostic bytes, repair result, and indeterminate reason

### Manual Acceptance

For each release, use a fresh sample repository rather than only fixtures:

1. Initialize Fettle from checkout and clean wheel.
2. Review stack/workspace detection.
3. Trigger one native violation through a supported agent.
4. Follow the displayed repair and rerun instruction.
5. Run workspace verification.
6. Confirm Stop verdict and evidence report.
7. Repeat in a mixed-workspace repository.

File the report under `docs/uat/` for each language or framework graduation.

## 8. Security Requirements

- Execute configured tools as argv arrays with `shell=False`.
- Resolve target paths inside their declared workspace before invocation.
- Prefer repository wrappers but reject symlink/path traversal outside policy.
- Bound tool time, output size, and input file count.
- Redact secrets before persistence or rendering.
- Validate SARIF/JUnit/JSON payload size and shape.
- Do not send source to network services without explicit integration policy.
- Framework detection cannot enable telemetry or weaken central policy.
- MCP cannot mutate policy, approve packages, or suppress enforcing rules.
- Missing tools and parser failures remain visible and policy-controlled.

## 9. Performance Budgets

- PreToolUse total default: 250 ms.
- PostToolUse total default: 400 ms.
- Stop-hook inspection default: 600 ms.
- Native compile/test/build operations run only in minutes-world commands.
- Fast per-edit adapters target p95 below 150 ms individually; if a repository
  tool cannot meet that target, run a cheaper check in-hook and defer the full
  analyzer to `fettle verify` or CI.
- Profile/workspace discovery is cached by marker content/mtime and invalidated
  when any relevant marker changes.

## 10. Observability And Graduation

Measure locally and through existing privacy-preserving aggregate telemetry:

- Applicable checks
- Pass, violation, tool error, unknown
- Check duration and budget overrun
- Rule fire, override, suppression, and recurrence
- Repair success and turns in evals
- Workspace routing failures

Do not add repository names, paths, source snippets, session identifiers, or
raw commands to aggregate telemetry. OpenTelemetry export and a hosted control
plane remain deferred until a concrete enterprise consumer requires them.

## 11. Blast Radius

High-risk modules:

- `fettle/dispatcher_registry.py`: every in-session check selection.
- `fettle/dispatcher_types.py` and `fettle/dispatcher_aggregate.py`: every host
  response and exit decision.
- `fettle/config.py` and policy resolver: every gate.
- `fettle/profile.py` / `fettle/workspace.py`: command cwd and stack routing.
- `fettle/verify_gate.py`: Stop completion and trusted evidence.
- `fettle/adapters/`: minutes-world commands and new per-edit checks.
- `fettle/lsp_server.py`: editor diagnostics.
- `rules/` and rule loading: clean-code false positives.

Required controls:

- Land one adapter migration at a time.
- Keep parity tests before deleting old paths.
- Use advisory defaults and ratchet evidence.
- Re-run four-agent event conformance after dispatcher changes.
- Run packaging smoke tests whenever rules, fixtures, commands, or optional
  surfaces are added.

The graph was re-indexed before P0–P5 implementation. Rerun `kgraph index` and
`kgraph impact <file>` whenever the worktree changes before a later work
package begins.

## 12. Historical Release-Level Estimate

The activity-level estimates in **Current Baseline And Authoritative Scope**
supersede this original coarse sizing. This table remains only to preserve the
mapping from the initial R1-R9 proposal.

Sizing uses S (days), M (about one week), L (two to three weeks), and XL
(multi-release), including tests and documentation for one experienced
engineer.

| Release | Scope | Estimate |
|---|---|---|
| R1 | Finding contract, evidence, eval baseline | L |
| R2 | Workspace and adapter consolidation | XL |
| R3 | Complete JS/TS and web parity | L |
| R4 | Generic command/SARIF/JUnit ingestion | M |
| R5 | Shell corpus and external sandbox contract | M-L |
| R6 | .NET and Java | XL |
| R7 | Pack infrastructure + first four packs | XL |
| R8 | Semantic-delta checks | L-XL, evidence-gated |
| R9 | Shared service, MCP, broader LSP | L |

Recommended staffing: one architectural owner for R1/R2, then separate adapter
owners can implement .NET and Java in parallel against the frozen contract.
Framework packs should follow, not overlap, initial adapter development.

## 13. Implementation Task Contract

Every work package is decomposed during its planning session into small tasks
that name exact files and leave tests green. The minimum sequence for each is:

1. Add or update the behavior contract test.
2. Add clean, violation, and error fixtures.
3. Implement the smallest production change.
4. Run focused tests.
5. Run cross-surface parity tests if shared code changed.
6. Run the full suite for behavior-changing Python code.
7. Run `python3 fettle/cli.py check --changed`.
8. Run the relevant behavioral evaluation.
9. Perform manual acceptance in a clean sample repository.
10. Update configuration schema, docs, changelog, and roadmap in the same
    release slice when the public contract changes.

No work package is complete based only on parser unit tests.

## 14. Release Success Criteria

The program is successful when:

1. One policy resolves identically for CLI, hooks, LSP, MCP, and CI inputs.
2. Python, JS/TS, .NET, and Java edits route to the correct workspace and
   native tools.
3. Mixed repositories verify every affected workspace and no unaffected one.
4. Tool failure and unknown analysis are never represented as clean.
5. Every actionable finding carries location, impact, action, and rerun.
6. React/Next.js, ASP.NET Core, Spring Boot, and HTMX packs meet their clean
   corpus and behavioral-eval gates.
7. Semantic-delta rules stay inside latency budgets with measured precision.
8. MCP improves preflight and repair but cannot bypass hook or CI enforcement.
9. Fettle documents shell mediation honestly and delegates containment to
   external sandboxes.
10. The full test suite, Fettle scan, package smoke, and remote CI are green at
    every release boundary.

## 15. Explicit Non-Goals

- Kernel-level eBPF or ptrace enforcement.
- Default-deny network namespaces managed by Fettle.
- A persistent semantic database.
- Whole-repository AST snapshots on every tool call.
- A supervisor daemon or general multi-agent orchestration platform.
- Cryptographic approval by another probabilistic reviewer agent.
- Automatic promotion of learned or framework rules.
- A hosted enterprise telemetry control plane without validated demand.
- Bespoke permanent adapters for every commercial scanner.
- Enforce-by-default framework heuristics.

## 16. TLA+ Formal Verification

### Motivation

Fettle's correctness guarantees depend on protocol-level properties
(monotonicity, fail-closed, mutual exclusion, temporal ordering) that unit tests
cannot exhaustively cover. TLA+ model-checking explores all reachable states,
finding violations that require specific interleavings or edge-case sequences
that are impractical to enumerate by hand.

Full specifications: [`docs/tla-plus-formal-verification.md`](tla-plus-formal-verification.md).

### Work Packages

| WP | Subsystem | Priority | Properties | Est. |
|----|-----------|----------|------------|------|
| TLA-1 | Policy Capsule Delegation | Critical | Monotonic strictness, depth bound, tamper→block, fail-closed, no spurious block | 2 days |
| TLA-2 | Work Item Claims + Topology | High | No duplicate claim, disjoint parallelism, unknown-scope conservative, claim-before-work | 2 days |
| TLA-3 | Verify Gate Temporal Ordering | Medium | Fresh stamp required, session binding, green required, coverage complete, workspace coverage | 1 day |
| TLA-4 | Dispatcher Budget & Priority | Low | Budget respected, priority order, first-block-wins, fail-open, always terminates | 1 day |
| TLA-5 | TDD Gate Phase Ordering | Low | Test-first required, preexisting test suffices, evidence persists, exempt paths pass | 0.5 day |

### Safety Properties (Summary)

**TLA-1 Policy Capsule:**
- A child's effective policy is always >= strict as its parent's on every key
- Lineage depth never exceeds 16 (no unbounded delegation recursion)
- Any capsule body modification after writing → all tool calls blocked
- Env asserts capsule + (missing/unreadable/version skew) → block
- Machine-local plumbing keys never propagate from parent to child
- Untampered + valid capsule → never triggers spurious block

**TLA-2 Work Items & Topology:**
- No two live sessions can hold the same item simultaneously
- Items approved for parallel execution have non-overlapping footprints
- An item with no declared scope conflicts with all other items
- No edits to files in an item's scope without holding its claim
- A claim whose worktree is gone can always be reclaimed
- Release always succeeds (no deadlock in the lock path)

**TLA-3 Verify Gate:**
- Stamp older than latest edit + tree changed → gate blocks/advises
- Stamp from session X cannot satisfy gate in session Y
- A red stamp (ok=false) never passes the gate
- Impacted-scope stamp must cover all files edited this session
- Multi-workspace edits require all affected workspaces verified
- Correct edit→verify→stop sequence always passes

**TLA-4 Dispatcher:**
- Total wall-clock never exceeds event budget (modulo one check overrun)
- Checks execute in registry priority order (no reordering)
- After a BLOCK result, no further checks execute
- A check exception never produces BLOCK (fail-open)
- Repeated failures surface advisory only after >= 3 occurrences
- The dispatcher always produces output (never hangs)

**TLA-5 TDD Gate:**
- In enforce mode, impl edit without prior test_edit is blocked
- If accept_preexisting is true and test exists on disk, impl is allowed
- A test_edit event is never lost (append-only log)
- Files matching exempt patterns are never blocked
- test_edit(M) then impl_edit(M) always produces ALLOW

### Implementation Phases

#### Phase 1: Infrastructure (0.5 day)

| Task | Description |
|------|-------------|
| T1.1 | Create `specs/tla/` directory with README |
| T1.2 | Add TLC runner script (`specs/tla/run-all.sh`) |
| T1.3 | Add CI integration (GitHub Actions, `tlaplus/tla-toolbox` Docker) |
| T1.4 | Document local TLA+ setup (Java 11+, `tla2tools.jar`) |

#### Phase 2: TLA-1 Policy Capsule (2 days)

| Task | Description |
|------|-------------|
| T2.1 | Write `PolicyCapsule.tla` modeling agents, capsules, merge, tamper |
| T2.2 | Write `PolicyCapsule.cfg` with small model (4 agents, 3 keys, depth=3) |
| T2.3 | Run TLC; fix spec until all 5 safety + 2 liveness properties pass |
| T2.4 | Mutation tests: remove depth check → TLC finds DepthBound violation |
| T2.5 | Mutation tests: weaken merge → TLC finds MonotonicStrictness violation |
| T2.6 | Mutation tests: skip digest check → TLC finds TamperDetection violation |
| T2.7 | Document findings; file issues for any code-level bugs discovered |

#### Phase 3: TLA-2 Work Items & Topology (2 days)

| Task | Description |
|------|-------------|
| T3.1 | Write `WorkItemClaims.tla` modeling sessions, items, flock, worktree liveness |
| T3.2 | Write `TopologyConflicts.tla` for pairwise disjointness logic |
| T3.3 | Write `.cfg` files (3 items × 3 sessions × 3 worktrees × 3 files) |
| T3.4 | Run TLC; verify NoDuplicateClaim under all interleavings |
| T3.5 | Add stale-claim reclamation scenario (worktree dies, new session claims) |
| T3.6 | Mutation test: remove flock → TLC finds duplicate claim race |
| T3.7 | Mutation test: allow unknown-scope parallelism → TLC finds overlap |

#### Phase 4: TLA-3 Verify Gate (1 day)

| Task | Description |
|------|-------------|
| T4.1 | Write `VerifyGate.tla` modeling edits, stamps, clock, gate evaluation |
| T4.2 | Write `.cfg` with 3 files × 2 workspaces × 2 sessions |
| T4.3 | Run TLC; verify all 5 safety properties and ValidPathClears liveness |
| T4.4 | Mutation test: remove freshness check → TLC finds stale stamp accepted |
| T4.5 | Mutation test: remove session binding → TLC finds cross-session reuse |

#### Phase 5: TLA-4 Dispatcher (1 day)

| Task | Description |
|------|-------------|
| T5.1 | Write `Dispatcher.tla` modeling checks, budget, exceptions, finalization |
| T5.2 | Write `.cfg` with 4 checks, budget=250ms, realistic durations |
| T5.3 | Run TLC; verify budget, ordering, fail-open, termination |
| T5.4 | Mutation test: allow exception to produce block → TLC finds FailOpen violation |
| T5.5 | Trace analysis: budget-exhaustion and exception-then-block scenarios |

#### Phase 6: TLA-5 TDD Gate (0.5 day)

| Task | Description |
|------|-------------|
| T6.1 | Write `TDDGate.tla` modeling modules, evidence set, preexisting tests |
| T6.2 | Write two `.cfg` files (enforce mode + advisory mode) |
| T6.3 | Run TLC in both modes; verify test-first enforcement |
| T6.4 | Mutation test: clear evidence set → TLC finds TestEvidencePersists violation |

#### Phase 7: Integration & Reporting (0.5 day)

| Task | Description |
|------|-------------|
| T7.1 | Run full suite; collect state-space statistics per spec |
| T7.2 | Document bugs found by model checking (if any) |
| T7.3 | Add `fettle tla` CLI command to run specs locally |
| T7.4 | Update ROADMAP.md with TLA+ verification status |

### State-Space Estimates

| Spec | States (est.) | Time | Diameter |
|------|--------------|------|----------|
| PolicyCapsule | ~50K | <30s | 8 |
| WorkItemClaims | ~200K | <2min | 12 |
| VerifyGate | ~10K | <10s | 6 |
| Dispatcher | ~5K | <5s | 5 |
| TDDGate | ~3K | <5s | 4 |

### Value Assessment

| WP | Bugs TLA+ Could Find | Confidence |
|----|----------------------|------------|
| TLA-1 | Policy escalation via merge ordering, lineage overflow, version-field escape | Very High |
| TLA-2 | Race in claim (flock removed/bypassed), parallel items with hidden overlap | High |
| TLA-3 | Stale stamp accepted, cross-session stamp reuse, impacted-scope gap | Medium-High |
| TLA-4 | Priority inversion, silent fail-closed, budget accounting off-by-one | Medium |
| TLA-5 | False positive block, evidence loss on crash | Low-Medium |

### Dependencies

- Requires: Java 11+ (TLC runtime), `tla2tools.jar` from https://github.com/tlaplus/tlaplus/releases
- Optional: TLA+ Toolbox or VS Code TLA+ extension for interactive exploration
- Blocks: none (verification is additive; no code changes required to run specs)
- Informs: any bugs found feed back as code fixes into the relevant release WP

### Success Criteria

1. All 5 specs pass TLC model-checking with zero invariant violations.
2. Mutation tests confirm TLC catches at least one violation per removed guard.
3. State-space exploration completes in under 5 minutes total (CI-feasible).
4. Any real bugs found are fixed and regression-tested before the next release.
5. Specs are maintained alongside code changes to verified subsystems.

---

## 17. Planning Gate Status

- Phase 0 UX: complete in `docs/polyglot-governance.ux-spec.md`.
- Phase 0.5 UI: not applicable; this plan changes CLI, hook, LSP, and protocol
  behavior but introduces no visual interface.
- Phase 1 plan: complete in this document.
- Phase 3.5 UAT scenarios: defined in the UX spec; per-release executable
  scenarios remain required before implementation.
- Feature manifest: not applicable; this repository does not maintain one.
- Implementation authorization: approved for P0–P5.
- P33–P43 status: P33 and P35 are complete; P34 has one accepted full retained
  CI run but awaits measured reproducibility and actionability evidence; P43 has
  two of five planned models but has not met its
  completion contract; P36–P42 remain proposed or evidence-gated.
  UX/BDD additions are recorded in `docs/polyglot-governance.ux-spec.md`.
- P44–P51 status: P44 is complete. Architecture, UX/BDD, and implementation
  contracts are recorded in the change-integrity document set; P45–P51 are not
  authorized until their package proposal review is explicitly accepted.
- P52 status: role-based enforcement is implemented, but its TLA+, adversarial,
  topology, and end-to-end graduation evidence remains.
- P53–P61 status: state-consistency UX/UAT and implementation contracts are
  recorded in the state-consistency document set. P53 is proposed as the next
  contract-only package; P54–P61 are not authorized, and P60 remains blocked on
  P35 and P38.
