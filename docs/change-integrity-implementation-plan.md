# Change Integrity Hypergraph Implementation Plan

Status: APPROVED; P44 complete, P45-P51 remain gated by package acceptance

Related documents:

- [Architecture contract](change-integrity-architecture.md)
- [UX and UAT contract](change-integrity.ux-spec.md)
- [Fettle evolution implementation plan](fettle-evolution-implementation-plan.md)
- [Fettle roadmap](ROADMAP.md)

## 1. Outcome

### User Story

As a developer or platform engineer changing a repository, I want Fettle to
derive affected artifacts and required verification from a coherent repository
snapshot, so that omitted dependencies, concurrent work, and stale evidence do
not create a false pass.

### User Flow

```text
select paths or candidate snapshot
              |
              v
inspect graph status and provider completeness
              |
              v
review affected artifacts and required actions
              |
              v
edit, verify, or record an authorized resolution
              |
              v
recompute against the immutable integration candidate
              |
              v
receive graph-bound evidence or an actionable non-pass
```

The first usable release is advisory and command-driven. Strict claims,
integration blocking, durable attestations, and optional persistence arrive
only after their independent graduation evidence exists.

## 2. Assumptions And Boundaries

1. Python 3.11+ and zero core runtime dependencies remain product constraints.
2. Git remains authoritative for committed repository content.
3. The graph-independent kernel owns repository discovery, path containment,
   policy resolution, source-manifest verification, result states, and recovery.
4. Interactive hooks remain bounded and visibly fail-open. No hook builds,
   migrates, or repairs a graph.
5. Required CI and integration checks fail closed on incomplete, unavailable,
   corrupt, or superseded graph evidence.
6. Existing `semantic.py`, `topology.py`, and `verify_gate.py` behavior remains
   authoritative until the corresponding graph consumer graduates from shadow
   mode or an explicit behavior-change review approves a difference.
7. P33 result integrity must close false-clean tool paths before a graph result
   can block. P35 supplies the override contract. P41, or an approved successor,
   supplies durable commit-linked evidence before graph attestations are relied
   upon outside one process.
8. Work-item claims remain the ownership unit. Graph expansion predicts file
   footprints; semantic-region ownership is out of scope.
9. External `kgraph` and Graphify data is optional enrichment unless an approved
   provider contract, source handshake, and completeness policy say otherwise.
10. SQLite is not part of the initial implementation. It is admitted only by
    the measured gate in P51.
11. `codebase-memory-mcp` remains an operator-run advisory experiment. The
    [v0.9.0 evaluation](advisory-code-intelligence-evaluation.md) does not admit
    it as a provider: default coverage was incomplete and results lacked the
    exact dirty source/configuration binding needed for authority.

## 3. Decisions And Tradeoffs

| Decision | Alternative rejected | Reason |
|---|---|---|
| Materialize or fully revalidate provider inputs | Hash the live tree before and after a build | A/B hashing detects some races but cannot prove that providers read one coherent state |
| Start with an ephemeral graph | Introduce SQLite with the graph model | Preserves the roadmap constraint and separates semantic correctness from cache operations |
| Add typed providers behind one graph assembler | Replace each existing analyzer at once | Supports incremental adoption and explicit completeness without a flag-day rewrite |
| Ship advisory CLI before enforcement | Put graph traversal directly in hooks or CI | Allows UX, precision, completeness, and latency measurement before blocking users |
| Migrate one consumer through shadow parity at a time | Make the graph immediately authoritative | Keeps shipped behavior stable and localizes regressions |
| Recompute the immutable integration candidate | Reuse worker evidence after target advancement | Worker evidence cannot prove facts about a different merge result |
| Keep claims as a separate transactional projection | Put live claims in the immutable graph digest | Coordination mutates independently and must not invalidate repository knowledge |

## 4. Authoritative Activity Sequence

| ID | Activity | Depends on | Estimate | State |
|---|---|---|---:|---|
| P44 | Define graph, provider, traversal, snapshot, and fixture contracts | P33 design contract | 3-5 days | Complete |
| P45 | Build graph-independent committed and working source snapshots | P44 | 5-8 days | Proposed |
| P46 | Assemble deterministic ephemeral graphs from native providers | P38, P44, P45 | 7-12 days | Proposed |
| P47 | Add advisory graph status, build, impact, and obligation output | P46 | 5-8 days | Proposed |
| P48 | Shadow semantic, topology, and verification consumers | P47 | 7-12 days | Proposed |
| P49 | Bind CI obligations and attestations to immutable candidates | P33, P35, P41, P48 | 7-12 days | Proposed |
| P50 | Add graph-expanded strict claim and integration checks | P49 | 7-12 days | Proposed |
| P51 | Evaluate and, only if admitted, add ephemeral-cache persistence | P46-P50 profiling | 5-10 days | Evidence-gated |

```text
P33 canonical non-pass integrity
          |
          v
P44 contracts --> P45 source snapshots --> P46 ephemeral graph --> P47 advisory UX
   ^                                      ^                         |
   |                                      |                         v
 P38 traceability ------------------------+                  P48 shadow consumers
                                                                    |
P35 overrides + P41 durable evidence -------------------------------+
                                                                    v
                                                         P49 CI attestations
                                                                    |
                                                                    v
                                                         P50 strict coordination
                                                                    |
                                                  measured cost only v
                                                         P51 persistence gate
```

No activity is authorized merely because it appears here. Each package requires
an accepted implementation proposal, current impact analysis, executable tests,
and the package-specific graduation evidence below.

## 5. Work Packages

### P44: Canonical Contracts And Adversarial Corpus

Goal: freeze the data and failure vocabulary before implementing storage,
traversal, or enforcement.

Primary files:

- `fettle/graph_types.py` (new)
- `fettle/provider_contract.py` (new)
- `fettle/traversal_rules.py` (new)
- `fettle/result.py`
- `tests/test_graph_types.py` (new)
- `tests/test_provider_contract.py` (new)
- `tests/test_traversal_rules.py` (new)
- `tests/fixtures/change_integrity/` (new)

Implementation slices:

1. Define versioned immutable records for nodes, hyperedges, incidences,
   provider fact sets, source identities, graph generations, impact closures,
   obligations, and freshness states.
2. Define canonical JSON encoding, Unicode/path normalization, stable ordering,
   full SHA-256 identities, and schema rejection rules.
3. Define provider applicability, trust, completeness, determinism, bounds,
   invalidation, tombstone, and result-state fields.
4. Define bounded typed traversal rules and obligation resolution states.
5. Add fixtures for duplicate facts, cycles, conflicting providers, missing
   providers, malformed attributes, path case, Unicode, symlinks, submodules,
   deletions, and oversized output.
6. Prove canonical output is independent of insertion order, process, and
   checkout path on maintained platforms.

Acceptance:

- Every enforcement fact identifies its provider, inputs, configuration,
  implementation, trust class, completeness, and run state.
- A failed or partial provider cannot be represented as an empty successful
  fact set.
- Unknown fields cannot silently alter or escape digest semantics.
- Cycles and fan-out limits terminate deterministically.

Verification:

```bash
python3 -m pytest tests/test_graph_types.py tests/test_provider_contract.py tests/test_traversal_rules.py -q
```

Completion evidence: immutable source, graph, provider, traversal, freshness,
closure, and obligation contracts are covered by adversarial fixtures and
cross-process canonical identity tests. P45 runtime snapshot construction is
not included.

### P45: Graph-Independent Source Snapshots

Goal: identify and materialize the exact provider inputs without requiring a
working graph or graph store.

Primary files:

- `fettle/source_snapshot.py` (new)
- `fettle/paths.py`
- `fettle/config.py`
- `fettle/policy_capsule.py`
- `fettle/worktrees.py`
- `tests/test_source_snapshot.py` (new)
- `tests/fixtures/change_integrity/snapshots/` (new)

Implementation slices:

1. Build committed snapshot manifests from Git tree objects, including modes,
   symlink text, gitlinks, deletions, and repository-relative identity.
2. Build working snapshot manifests containing relevant index, tracked,
   untracked, and explicitly required ignored inputs with full content hashes.
3. Materialize provider inputs in a restrictive temporary directory or expose a
   complete read-set API with post-run revalidation.
4. Bind effective policy provenance and provider/toolchain manifests into the
   source identity.
5. Detect index conflicts, sparse checkouts, LFS placeholders, dirty submodules,
   file replacement, mode/type changes, and transient edit/restore races.
6. Keep `doctor`, status diagnosis, cache deletion, and rebuild usable when
   materialization fails.

Acceptance:

- Two committed snapshots of the same tree have identical portable identities.
- No provider can contribute to a consequential graph after reading mixed live
  states.
- Existing untracked-file content changes alter working snapshot identity.
- Materialization failure preserves user files and returns an actionable
  canonical non-pass.

Verification:

```bash
python3 -m pytest tests/test_source_snapshot.py tests/test_paths.py tests/test_policy_capsule.py tests/test_worktrees.py -q
```

### P46: Deterministic Ephemeral Graph And Native Providers

Goal: build and validate a complete in-memory generation for an immutable
snapshot without introducing persistent state.

Primary files:

- `fettle/hypergraph.py` (new)
- `fettle/graph_builder.py` (new)
- `fettle/providers/` (new)
- `fettle/semantic.py`
- `fettle/spec_model.py`
- `fettle/import_graph.py`
- `fettle/workspace.py`
- `fettle/work_items.py`
- `tests/test_graph_builder.py` (new)
- `tests/test_graph_providers.py` (new)

Implementation slices:

1. Add provider adapters for specifications/scenarios, trace markers, work-item
   declarations, workspace routing, and Python imports/exports.
2. Make unsupported syntax, parse failure, excluded inputs, and incomplete
   language coverage explicit in provider completeness.
3. Canonicalize, deduplicate, validate references, and compute the graph digest
   only after all required providers finish.
4. Publish a completed generation atomically within the process. Never expose
   the mutable assembly graph.
5. Build bidirectional sparse incidence indexes for node-to-edge and edge-to-node
   traversal. Compact integer handles may optimize one completed generation but
   remain non-canonical and never enter provider output, stable JSON, evidence,
   attestations, or graph digests.
6. Represent containment and hierarchy through typed edges and incidences;
   prohibit ancestry, nesting position, and dot notation from canonical IDs.
7. Add full-build reconciliation fixtures before admitting any incremental
   provider output to enforcement.
8. Keep external providers disabled by default and label all imported trust and
   source-handshake limitations.

Acceptance:

- Identical snapshot, policy, provider manifest, and rule set produce identical
  graph digests.
- A generation is either complete and validated or unavailable; readers never
  observe partial publication.
- Existing native semantic links are represented with parity or documented,
  approved differences.
- Overlapping memberships traverse in both directions without changing node
  identity when an entity is regrouped; no durable output exposes local integer
  handles.
- Full graph construction stays within an agreed explicit-command budget on a
  maintained small, medium, and large repository corpus.

Verification:

```bash
python3 -m pytest tests/test_graph_builder.py tests/test_graph_providers.py tests/test_semantic.py tests/test_import_graph.py -q
```

### P47: Advisory CLI And Operator Recovery

Goal: make graph capability useful and understandable before any graph fact can
block work.

Primary files:

- `fettle/cli.py`
- `fettle/graph_commands.py` (new)
- `fettle/graph_render.py` (new)
- `fettle/doctor.py`
- `tests/test_graph_commands.py` (new)
- `tests/test_output_schema.py`
- `docs/CONFIG.md`
- `docs/change-integrity.ux-spec.md`

Implementation slices:

1. Add `graph status`, `graph build`, `impact`, and report-only `obligations`
   commands with stable human and JSON contracts.
2. Render first-time, cleared-empty, filtered-empty, loading, populated,
   incomplete, superseded, corrupt, unavailable, and offline states.
3. Group direct impact, transitive impact, required actions, uncertain review,
   provider gaps, and the exact next command within the default output budget.
4. Add graph-independent diagnosis and safe derived-state cleanup.
5. Verify `NO_COLOR`, non-TTY progress, cancellation, bounded output, exit codes,
   and machine-readable schema compatibility.
6. Run the UX scenarios in a fresh sample repository; do not rely only on unit
   fixtures.

Acceptance:

- First useful advisory impact requires one command when native providers apply.
- Empty complete impact is visibly different from incomplete or no-provider
  analysis.
- Every non-pass has one specific recovery or broader-verification action.
- No interactive hook builds, migrates, or repairs graph state.

Verification:

```bash
python3 -m pytest tests/test_graph_commands.py tests/test_output_schema.py tests/test_doctor.py -q
NO_COLOR=1 python3 -m fettle.cli graph status
python3 -m fettle.cli impact fettle/semantic.py --json
```

### P48: Shadow Consumer Migration

Goal: measure graph correctness against shipped semantic, topology, and
verification-selection behavior before changing authority.

Primary files:

- `fettle/semantic.py`
- `fettle/topology.py`
- `fettle/topology_apply.py`
- `fettle/verify_gate.py`
- `fettle/graph_shadow.py` (new)
- `fettle/trace.py`
- `tests/test_graph_shadow.py` (new)
- `tests/test_semantic.py`
- `tests/test_topology.py`
- `tests/test_verify_gate.py`

Implementation slices:

1. Execute graph-native semantic links in shadow mode and compare nodes, edges,
   orphan decisions, result states, and rationale.
2. Compare graph-expanded predicted footprints with current scope plus
   reverse-import behavior; retain unknown-scope conservative conflict.
3. Compare graph-selected workspaces/tests with current affected-workspace and
   Python impacted-test selection.
4. Record bounded parity evidence by snapshot and graph digest without source
   bodies or repository identity in aggregate telemetry.
5. Classify every mismatch as graph defect, legacy defect, expected unsupported
   case, or proposed behavior change.
6. Promote one consumer only after its own review; do not use one consumer's
   parity to authorize another.

Acceptance:

- Maintained parity fixtures have no unexplained narrower graph result.
- Provider incompleteness never becomes "unaffected."
- Added latency stays outside hook budgets or uses a previously built exact
  generation; no hidden synchronous rebuild occurs in hooks.
- Every authority change has rollback and independent regression coverage.

Verification:

```bash
python3 -m pytest tests/test_graph_shadow.py tests/test_semantic.py tests/test_topology.py tests/test_verify_gate.py -q
```

### P49: CI Obligations And Graph-Bound Attestations

Goal: make required change-integrity decisions reproducible against the exact
immutable merge candidate.

Primary files:

- `fettle/ci.py`
- `fettle/verify_gate.py`
- `fettle/trace.py`
- `fettle/provenance_gate.py`
- `fettle/obligations.py` (new)
- `fettle/graph_attestation.py` (new)
- `.github/workflows/ci.yml`
- `tests/test_obligations.py` (new)
- `tests/test_graph_attestation.py` (new)
- `tests/test_ci.py`

Implementation slices:

1. Generate impact and obligations from the platform merge commit or a recorded
   synthetic merge identity, never only from the worker base.
2. Require each obligation to be updated, verified unchanged, not applicable
   with reason, or validly overridden through P35.
3. Bind source, policy, provider, traversal, graph, impact, obligation,
   evidence, candidate, and target identities into one attestation.
4. Use P41's tamper-evident retention and commit linkage; best-effort local
   trace alone is not durable attestation.
5. Reject superseded, incomplete, malformed, untrusted, expired, or mismatched
   evidence with canonical non-pass states.
6. Keep graph checks advisory until precision, runtime, override, and recovery
   graduation thresholds are approved.

Acceptance:

- Target advancement invalidates worker-only graph evidence.
- Missing required providers and unresolved obligations fail closed after
  graduation and never serialize as pass before graduation.
- An attestation can be reproduced from recorded immutable identities and
  bounded evidence.
- CI remains independently useful when local hooks were bypassed.

Verification:

```bash
python3 -m pytest tests/test_obligations.py tests/test_graph_attestation.py tests/test_ci.py tests/test_verify_gate.py -q
python3 -m fettle.cli ci --root .
```

### P50: Strict Claims And Integration Coordination

Goal: prevent strict concurrent work or integration from relying on incomplete
or overlapping graph-expanded footprints.

Primary files:

- `fettle/work_items.py`
- `fettle/topology.py`
- `fettle/topology_apply.py`
- `fettle/worktrees.py`
- `fettle/claims_gate.py`
- `tests/test_work_items.py`
- `tests/test_topology.py`
- `tests/test_claims_gate.py`
- `specs/tla/WorkItemClaims.tla`

Implementation slices:

1. Bind accepted predicted footprints to work item, base snapshot, graph digest,
   provider completeness, and policy.
2. Acquire or reject incompatible strict claims under the existing locked,
   atomic coordination path.
3. Treat unknown or incomplete footprint as conflicting with every strict claim
   unless P35 authorizes a recorded coordination override.
4. Emit a scope-change event and recalculate when an actual edit falls outside
   the accepted footprint.
5. Recompute the integration candidate and reject stale footprint or obligation
   evidence after target advancement.
6. Extend the existing TLA+ model only if the concrete transition design meets
   P43 entry criteria; derive multiprocess regression tests from any new
   invariant or counterexample.

Acceptance:

- Concurrent acquisition cannot authorize two incompatible strict footprints.
- Process crash, stale claim, worktree loss, and scope expansion preserve the
  current reclaim and no-lost-update guarantees.
- Advisory users do not acquire mandatory claims or suffer new blocking.
- Semantic-region claims remain absent.

Verification:

```bash
python3 -m pytest tests/test_work_items.py tests/test_topology.py tests/test_claims_gate.py -q
specs/tla/run-all.sh
```

### P51: Persistence Admission And Optional Cache

Goal: decide from measurements whether persistence is justified; "do not add a
store" is a valid successful outcome.

Entry evidence:

- Representative cold-build and repeated-build p50/p95 measurements.
- Profile identifying provider or assembly cost rather than assumed I/O cost.
- Demonstrated benefit from incremental reuse large enough to justify locking,
  migration, corruption, privacy, and recovery complexity.

Primary files only if admitted:

- `fettle/graph_store.py` (new)
- `fettle/graph_builder.py`
- `fettle/doctor.py`
- `tests/test_graph_store.py` (new)
- `tests/test_graph_store_faults.py` (new)
- `docs/CONFIG.md`

Implementation slices if admitted:

1. Use standard-library SQLite as a local, derived, untrusted cache with
   immutable generation rows and atomic current-generation publication.
2. Separate immutable graph generations, append-only activity, and mutable
   projections into explicit schemas and retention policies.
3. Validate schema and canonical digests before every authoritative read.
4. Bound lock wait and handle crash, disk full, corruption, read-only state,
   migration failure, concurrent readers/builders, and unsupported filesystems.
5. Keep migrations and large rebuilds out of hooks. Cache failure returns
   unavailable or unknown, never a superseded success.
6. Demonstrate byte-identical graph digests with and without persistence and
   complete recovery by deletion and rebuild.

Acceptance:

- The admission record names measured repositories, budgets, benefit, costs,
  and the explicit go/no-go decision.
- Cache loss cannot destroy Git-authoritative facts or durable evidence.
- Unsupported filesystem semantics are rejected rather than guessed.
- If benefit is insufficient, P51 closes with a documented no-go and no runtime
  storage code.

Verification if admitted:

```bash
python3 -m pytest tests/test_graph_store.py tests/test_graph_store_faults.py tests/test_graph_builder.py -q
```

## 6. Cross-Cutting Verification

### Contract Matrix

| Concern | Required evidence |
|---|---|
| Determinism | Repeated process/platform builds produce identical full digests |
| Snapshot coherence | Transient edit/restore and concurrent mutation cannot publish mixed input |
| Completeness | Missing, failed, partial, excluded, and unsupported inputs remain non-pass or explicitly limited |
| Security | Containment, symlink, oversized payload, untrusted cache, query parameterization, and redaction tests |
| Concurrency | Multiprocess build publication and claim acquisition preserve atomicity |
| Recovery | Corrupt or unavailable derived state can be deleted and rebuilt without graph access |
| Compatibility | Existing consumers remain authoritative until individual shadow graduation |
| UX | All states and adversarial BDD scenarios in the UX spec are exercised |
| Performance | Hook budgets remain unchanged; explicit cold/warm command p50/p95 is reported |

### Required Package Gate

For every behavior-changing package:

1. Refresh `kgraph` and run impact analysis for each primary file.
2. Add contract, error-path, boundary, and regression tests before promotion.
3. Run focused tests, then the full suite for shared result, policy, snapshot,
   graph, claim, verification, or CI changes.
4. Run the Fettle quality scan and package smoke test.
5. Exercise the operator flow in a clean repository for at least two minutes.
6. Record unresolved provider gaps and unsupported repository shapes.
7. Update schema, UX, architecture, roadmap, and changelog when the public
   contract changes.

## 7. Security And Privacy Requirements

- Resolve every input and derived-state path through centralized containment.
- Execute external providers as bounded argv arrays with `shell=False`.
- Never persist source bodies, prompts, secrets, unrestricted environment
  values, or unrestricted analyzer output by default.
- Treat provider output and optional cache contents as untrusted input.
- Bound files, bytes, runtime, nodes, edges, incidences, attributes, diagnostics,
  depth, fan-out, and total traversal results.
- Reject digest, schema, referential, path, and policy mismatches before use.
- Preserve delegated-policy monotonicity for advisory, strict, and regulated
  modes.
- Do not claim mediation of direct writes, hook bypass, external model hosts, or
  mutable targets outside Fettle's compare-and-swap boundary.

## 8. Performance Budgets

- Existing hook totals remain 250 ms PreToolUse, 400 ms PostToolUse, and 600 ms
  Stop unless a separately approved product decision changes them.
- Hooks may consume only an already-complete exact generation and bounded
  traversal; otherwise they report visible advisory unavailability.
- Warm `graph status` and bounded impact target p95 below 500 ms on the
  maintained corpus.
- Cold build shows progress after one second and supports cancellation without
  partial publication.
- CI graph work runs outside the three-minute first-feedback lane where needed
  and must preserve the verification program's 12-minute blocking p95 budget.
- P51 receives no implementation authorization without before/after profiles.

## 9. Blast Radius

Highest-risk surfaces:

- `fettle/result.py`: canonical pass/non-pass semantics.
- `fettle/config.py` and `fettle/policy_capsule.py`: effective policy identity
  and delegated strictness.
- `fettle/paths.py` and `fettle/worktrees.py`: containment and snapshot safety.
- `fettle/semantic.py`, `fettle/import_graph.py`, and `fettle/spec_model.py`:
  current semantic facts and parse limitations.
- `fettle/topology.py`, `fettle/work_items.py`, and `fettle/claims_gate.py`:
  concurrent ownership and no-lost-update behavior.
- `fettle/verify_gate.py`, `fettle/ci.py`, and `fettle/trace.py`: stale evidence,
  fail-closed boundaries, and durable decision context.
- `fettle/cli.py` and `fettle/doctor.py`: operator recovery must remain usable
  when every graph component fails.

Required containment:

- Add new modules before redirecting existing consumers.
- Land one provider and one consumer migration at a time.
- Keep graph state derived and deletable.
- Do not add a runtime dependency or daemon.
- Do not alter claims, CI, or verification authority in the advisory packages.

## 10. Program Success Criteria

The program is complete only when:

1. Critical graph decisions identify an immutable source snapshot, effective
   policy, providers, traversal rules, graph, impact closure, and evidence.
2. No required missing, failed, partial, stale, corrupt, or superseded input can
   produce pass or unaffected.
3. Identical immutable inputs produce identical graph digests across maintained
   platforms and checkout locations.
4. Existing semantic, topology, and verification consumers graduate separately
   with parity or explicitly approved behavior changes.
5. CI reconstructs the exact merge candidate and does not reuse stale worker
   evidence after target advancement.
6. Strict concurrent claims cannot authorize overlapping or unknown footprints.
7. Graph failure never disables graph-independent safety, diagnosis, or rebuild.
8. Hooks remain bounded and visibly fail-open; required CI remains fail-closed.
9. Durable attestations use the approved P41 evidence substrate and valid P35
   overrides.
10. Persistence exists only if P51's measured admission record approves it.

## 11. Planning Gate Status

- Phase 0 UX: complete in `docs/change-integrity.ux-spec.md`.
- Phase 0.5 UI: not applicable; the proposed surface is terminal and protocol
  output with no visual application.
- Phase 1 plan: complete in this document.
- Phase 3.5 UAT: adversarial BDD scenarios are defined in the UX specification;
  executable automation is required in each authorized package.
- Implementation authorization: granted for P44; not granted for P45-P51.

### Staged authorization decision (2026-08-23)

Program direction approved with per-package authorization retained:

- **P45 authorized** to start (sole dependency P44 is complete).
- **P38 promoted** to next-up enabling work: its completion (deps P33, P35
  both complete) unlocks P46 here and state-consistency P60 in the evolution
  plan. P46 may start only after P38 closes.
- **P46-P48, P50** approved in principle; each still requires its own package
  proposal review plus current impact analysis at start time.
- **P49 deferred**: requires P41 or an approved successor before durable
  graph-bound attestations may be relied upon, and P48 must graduate first.
- **P51** remains evidence-gated by construction; a no-go close is acceptable.
