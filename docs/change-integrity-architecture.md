# Change Integrity Hypergraph Architecture

Status: APPROVED; P44 contract implementation complete

Related documents:

- [Change integrity UX specification](change-integrity.ux-spec.md)
- [Change integrity implementation plan](change-integrity-implementation-plan.md)
- [Fettle evolution implementation plan](fettle-evolution-implementation-plan.md)
- [Fettle roadmap](ROADMAP.md)

## 1. Purpose

Fettle should become knowledge- and dependency-aware: repository artifacts,
agent activity, impact obligations, and verification evidence should form one
typed, traversable model. Actions and enforcement can then follow explicit
rules over that model rather than isolated path heuristics.

The hypergraph is Fettle's **semantic foundation**, but not its bootstrap,
security, or recovery dependency. A small graph-independent kernel must remain
available when graph construction, providers, or optional storage fail.

The enforceable guarantee is:

> Fettle performs a graph-dependent critical action only against a named,
> immutable source snapshot, effective-policy digest, provider manifest,
> traversal-rule version, and graph digest. If that binding cannot be proven,
> the result is non-pass.

This is intentionally narrower than "the graph is always current." Fettle
cannot prevent an unrelated editor or process from changing a working tree.
It can prevent stale or incoherent graph state from authorizing a critical
action or producing a successful attestation.

## 2. Current System Baseline

This design extends current behavior; it does not assume a graph substrate that
does not yet exist.

| Capability | Current implementation | Current guarantee | Limitation relevant to this design |
|---|---|---|---|
| Semantic links | `fettle/semantic.py` | Deterministic pairwise graph recomputed from repository artifacts | No transitive impact closure, provider completeness, snapshot identity, or hyperedges |
| Python dependencies | `fettle/import_graph.py` | Static absolute-import and exported-name checks | Python-only; relative/dynamic imports and parse failures do not produce complete dependency evidence |
| Work-item footprint | `fettle/topology.py` | Scope globs plus one reverse-import hop; unknown scope conflicts with everything | Advisory prediction, not a transitive or polyglot ownership model |
| Work items and claims | `fettle/work_items.py` | Versioned work items; locked, atomic, shared runtime item claims | Claim ownership is per item, not graph-expanded impact; uses Unix `fcntl` |
| Worktree isolation | `fettle/worktrees.py` | Per-item branches/worktrees; shared Git common directory; dirty removal refusal | Optional; no immutable source-manifest abstraction |
| Topology activity | `fettle/topology_apply.py` | Shared mutable manifest joined with claims and trace | Runtime projection is not revision- or graph-bound |
| Verification | `fettle/verify_gate.py` | Session-bound stamp, affected-workspace coverage, stale checks | Dirty digest omits content changes within already-untracked files |
| CI | `fettle/ci.py` | Independently fail-closed boundary for owned gates | No graph generation or immutable merge-candidate binding |
| Policy | `fettle/config.py`, `fettle/policy_capsule.py` | Canonical layered policy resolution and delegation continuity | Effective policy includes repository-external and environment-derived inputs |
| Evidence | `fettle/trace.py` | Bounded, redacted, content-derived evidence IDs and fail-visible audit writes | Best-effort mutable JSONL is not durable, commit-linked attestation |
| Hook execution | `fettle/dispatcher.py` | Isolated checks, bounded output, fail-open session behavior | 250/400/600 ms event budgets can skip graph work |
| Workspaces | `fettle/workspace.py`, `fettle/adapters/` | Canonical polyglot routing and four-state adapter outcomes | Dependency extraction is not yet polyglot or completeness-aware |

The historical Stage 6 decision deliberately avoided persistence while
recomputation was cheap. This architecture preserves that decision: an
ephemeral graph is the first implementation. Persistent storage is admitted
only after measured cost and operational evidence satisfy Section 14.

## 3. Architectural Boundaries

### 3.1 Graph-Independent Kernel

The following capabilities must work without a graph or graph store:

- Repository discovery and path containment.
- Effective policy resolution and delegated-policy tamper protection.
- Source-manifest construction and digest verification.
- Destructive-command and release protections that inspect a single event.
- Configuration and schema validation.
- `fettle doctor`, graph status diagnosis, cache deletion, and rebuild.
- Canonical result states and concise failure rendering.
- CI's ability to report graph construction as failed or unknown.

This prevents circular startup and recovery dependencies. Graph construction
may consume kernel outputs; the kernel must never need a successful graph to
repair the graph.

### 3.2 Graph-Dependent Capabilities

The hypergraph may become authoritative, after individual graduation, for:

- Semantic links and orphan detection.
- Change impact and required-action closure.
- Impacted test and workspace selection.
- Work-item footprint expansion and overlap detection.
- Claim-scope enforcement.
- Requirement, scenario, implementation, and evidence traceability.
- Verification obligation resolution.
- Integration eligibility and graph-bound attestations.

Existing direct implementations remain authoritative until each consumer
passes shadow parity or an explicit behavior-change review.

### 3.3 Deliberate Non-Goals

- A universal agent scheduler, model runtime, or supervisor daemon.
- Automatic semantic rewriting of callers, tests, or documentation.
- A mandatory graph server or mandatory third-party Python dependency.
- Claiming that hooks mediate direct filesystem writes or `--no-verify` use.
- Treating heuristic similarity as authoritative dependency evidence.
- Persisting source bodies, prompts, secrets, or unrestricted tool output.
- Replacing Git as the source of authoritative repository artifacts.

## 4. Three Linked Planes

### 4.1 Knowledge Plane

Versioned or reproducible facts about the repository:

- Repository, workspace, file, directory, module, symbol, and package nodes.
- Specifications, requirements, scenarios, work items, and declared scopes.
- Tests, fixtures, schemas, configuration, dependency manifests, and lockfiles.
- Generators, generated artifacts, documentation, APIs, and contracts.
- Typed relationships extracted by providers.

### 4.2 Activity Plane

Runtime events and coordination:

- Agent, operator, session, worktree, branch, work-item claim, and lease.
- Edit, command, impact calculation, obligation transition, and integration attempt.
- Provider run, graph build, graph publication, and recovery event.

Activities are append-only events. Current claims and leases are mutable
projections over those events, not immutable graph facts.

### 4.3 Evidence Plane

Why a decision was accepted:

- Source snapshot, graph, policy, provider, and traversal-rule digests.
- Analyzer, test, build, CI, UAT, and approval evidence.
- Obligation resolutions, overrides, expiry, actor, and rationale.
- Candidate commit, target commit, and synthetic or platform merge identity.

Evidence may reference knowledge and activity nodes but must retain its original
immutable decision context.

## 5. Source Snapshot Contract

### 5.1 Snapshot Classes

Fettle recognizes two source classes:

1. **Committed snapshot:** an immutable Git tree or commit. This is preferred
   for CI, integration, replay, and durable attestation.
2. **Working snapshot:** a materialized, content-addressed manifest of the
   worktree and index inputs required by selected providers. This supports
   local advisory analysis without pretending the mutable filesystem is atomic.

Digest-before/build/digest-after remains a race detector. It is not the proof
that providers read a coherent state. Providers for a consequential graph must
read from the materialized snapshot or report a complete read set whose path,
type, mode, and content hashes are revalidated before publication.

### 5.2 Source Manifest Fields

The canonical source manifest includes:

- Manifest schema version and canonicalization version.
- Repository identity and normalized root, without using the absolute path as
  portable identity.
- HEAD commit and tree identities, including unborn or detached state.
- Index tree identity and index conflict stages.
- For every included path: normalized repository-relative path, object type,
  executable bit, content hash, size, and deletion/tombstone state.
- Symlink link text and type; resolved target identity only where policy permits
  following an in-repository target.
- Submodule gitlink commit and declared handling mode; dirty submodule content
  is either recursively manifested or explicitly reported incomplete.
- Relevant untracked inputs with full content hashes.
- Relevant ignored inputs only when a provider declares them semantic inputs;
  otherwise their exclusion is explicit in provider completeness.
- Sparse-checkout and Git LFS state when they change provider-visible content.
- Effective-policy digest and policy-layer provenance digest.
- Provider/toolchain manifest digest.

The manifest excludes `.git/`, ephemeral logs, caches, virtual environments,
editor state, Fettle runtime claims, and reproducible build output unless a
provider explicitly declares an excluded path authoritative.

### 5.3 Snapshot Identity

Use full SHA-256 over canonical UTF-8 JSON:

```text
source_snapshot_id = sha256(canonical(source_manifest))
```

No enforcement decision may rely on a truncated digest. Short display forms
are presentation only.

### 5.4 Action Binding and TOCTOU

No worktree freshness check can eliminate the interval between validation and
an irreversible external action. Critical operations therefore use snapshot
semantics:

- Fettle states that the operation and evidence apply to immutable snapshot S.
- CI uses the exact checked-out candidate, preferably the hosting platform's
  merge-group commit, or records base SHA, candidate SHA, merge algorithm, and
  resulting tree SHA for a synthetic merge.
- Integration recomputes required graph facts against the resulting immutable
  tree instead of trusting a worker's older worktree graph.
- A mutable-target operation requires an explicit compare-and-swap precondition
  or cooperative lease through its commit point; otherwise Fettle cannot attest
  that the target remained unchanged.

## 6. Hypergraph Model

### 6.1 Core Records

```text
Node
  id, kind, stable_key, attributes, provenance

Hyperedge
  id, type, attributes, provider_fact_set, confidence

Incidence
  edge_id, node_id, role, direction, ordinal

ProviderFactSet
  provider_id, provider_version, config_digest, input_digest,
  run_state, completeness_scope, deterministic, authoritative
```

A hyperedge is used only when one relationship genuinely joins multiple roles.
Ordinary binary relationships remain binary edges represented by the same
incidence model.

Example:

```text
edge type: api-contract
  contract   -> schema node
  defines    -> implementation symbol
  consumed-by-> caller symbols
  verified-by-> contract tests
  documented-by -> public documentation
```

### 6.2 Identity and Canonicalization

- Node IDs derive from kind plus stable repository-relative identity, not
  insertion order or absolute paths.
- Edge IDs derive from type, ordered canonical incidences, enforcement-relevant
  attributes, and provider fact-set identity.
- Duplicate equivalent facts collapse deterministically while retaining all
  provenance records.
- Strings use documented Unicode normalization; paths use `/`, preserve case,
  and include platform case-sensitivity in the provider manifest.
- Canonical ordering is bytewise over normalized fields.
- Unknown fields are rejected for digest construction until a schema version
  defines whether they are enforcement-relevant.

```text
graph_digest = sha256(
  source_snapshot_id
  + graph_schema_version
  + traversal_rule_set_digest
  + canonical_nodes
  + canonical_edges
  + canonical_incidences
  + provider_fact_sets
)
```

Mutable claims, current leases, timestamps, and obligation resolutions do not
change the immutable graph digest.

## 7. Provider Contract

Every provider declares:

- Stable identifier, semantic version, implementation digest, and owner.
- Supported artifact kinds, languages, and workspace types.
- Complete input classes, configuration inputs, and environment allowlist.
- Output node, edge, and incidence types.
- Trust class: `authoritative`, `derived`, `heuristic`, or `external`.
- Determinism declaration and canonical output rules.
- Applicability and completeness scope.
- Incremental invalidation rule and deletion/tombstone behavior.
- Runtime, files, bytes, output, and finding limits.
- Explicit outcomes: `pass`, `violation`, `tool_error`, `unknown`, and
  `not_applicable` where the canonical result layer supports it.

Provider identity proves which implementation ran; it does not prove the
provider is correct. A traversal rule separately lists accepted trust classes
and required completeness.

Provider failures never become empty successful fact sets. A required missing,
partial, conflicting, timed-out, malformed, or failed provider makes the
dependent traversal `unknown` or `tool_error`.

### 7.1 Initial Native Providers

| Provider | Existing source | Initial status |
|---|---|---|
| Specifications and scenarios | `spec_model.py`, `semantic.py` | Derived, deterministic |
| Test trace markers | `spec_model.py`, `semantic.py` | Derived, deterministic |
| Work items and scopes | `work_items.py` | Authoritative declaration plus derived glob expansion |
| Workspace routing | `workspace.py` | Derived; completeness limited to known markers |
| Python imports and exports | `import_graph.py` | Derived, incomplete; advisory until parse failures and unsupported forms are explicit |
| UAT verdicts and attestations | `semantic.py`, UAT modules | Evidence facts, bound to their recorded context |
| Graphify | optional `graphify-out/graph.json` | External enrichment; never silently authoritative |
| `kgraph` | optional external process | External enrichment; source-digest handshake required for enforcement use |

## 8. Traversal and Obligation Rules

Traversal rules are versioned policy artifacts, not arbitrary reachability.
Each rule declares:

- Trigger node kinds and change classes.
- Permitted edge types, roles, directions, and trust classes.
- Maximum depth, cycle handling, fan-out cap, and total result cap.
- Required provider completeness.
- Produced impact classifications and obligations.
- Advisory or enforcing surfaces.
- Recovery and exact rerun command for every non-pass result.

An impact closure contains changed nodes, traversed facts, affected nodes,
provider completeness, generated obligations, and its own digest.

Every required obligation resolves as exactly one of:

- `updated`
- `verified_unchanged`
- `not_applicable` with reason
- `overridden` with authorized actor, reason, expiry, revision, policy digest,
  graph digest, and prior evidence identifier

Mechanical generators may update outputs when the generator relationship and
command are authoritative and reproducible. Semantic relationships create
obligations; they do not authorize blind rewriting.

## 9. Freshness, Publication, and Recovery

### 9.1 Generation Lifecycle

```text
requested
  -> source materialized
  -> providers running
  -> graph assembled
  -> canonicalized
  -> validated
  -> atomically published
```

Readers see only a previously completed generation or the new completed
generation, never a partial generation. Publication uses compare-and-swap:
generation G may become current only if the requested source identity still
matches its publication precondition.

### 9.2 Freshness States

- `current`: exact requested snapshot and required providers are complete.
- `building`: no completed matching generation yet.
- `incomplete`: generation exists but one or more required facts are unknown.
- `superseded`: valid immutable generation, but not for the requested snapshot.
- `corrupt`: digest, schema, or referential validation failed.
- `unavailable`: graph construction or optional storage cannot be used.

There is no stale-success fallback. A superseded graph may support explicitly
labelled historical display but cannot authorize a current action.

### 9.3 Incremental Invalidation

Incremental output may contribute to enforcement only when the provider's
invalidation rule is demonstrated sound for modifications, additions,
deletions, renames, type/mode changes, configuration changes, workspace
remapping, and provider upgrades. Otherwise the provider performs a full build
for critical decisions or remains advisory.

Periodic full reconciliation measures incremental correctness; it is not a
repair mechanism that makes known-unsound blocking behavior acceptable.

## 10. Activity, Claims, and Concurrent Agents

The work-item claim remains the operator-facing ownership unit. Its declared
scope is the seed for a graph-derived predicted footprint.

Strict-mode claim acquisition eventually requires:

1. A live work-item claim and isolated worktree.
2. Base commit and source snapshot identities.
3. Predicted footprint and footprint digest.
4. No overlap with another live strict claim's accepted footprint.
5. Unknown or incomplete footprint conflicts conservatively with all strict
   claims unless an authorized coordination override exists.

Actual edits outside the accepted footprint create a visible scope-change
event and require recalculation. They are not silently accepted as proof that
the original prediction was sufficient.

Semantic-region claims are deferred. Current analyzers cannot identify stable,
cross-language semantic regions reliably enough for ownership enforcement.

Runtime coordination remains separate from immutable snapshots. The current
locked claims file remains authoritative until a later stage proves any new
transactional projection under multiprocess and cross-platform tests.

## 11. Evidence and Attestation

A successful graph-dependent attestation records:

- Full source snapshot and graph digests.
- Effective policy and traversal-rule-set digests.
- Provider fact-set identities and completeness.
- Impact closure and resolved obligation identities.
- Actor, session, work item, worktree, base commit, candidate commit, and target.
- Commands, result states, bounded outputs, tool versions/digests, and timestamps.
- Resulting commit or merge-tree identity where Fettle owns that operation.

Best-effort trace remains useful operational telemetry, but it is not sufficient
for durable attestation. Commit-linked, tamper-evident evidence depends on the
P41 verification-integrity work or its approved successor.

## 12. Failure Semantics

| Surface | Graph unavailable/incomplete | Permitted behavior |
|---|---|---|
| Interactive advisory hook | Visible advisory after bounded retry or chronic escalation | Continue session; emit no successful graph attestation |
| Interactive enforcing hook | Follow explicit gate policy, while preserving dispatcher fail-open host safety | A fail-open is recorded as unknown/error, never pass |
| Explicit `fettle impact`/verification | Non-zero with recovery instruction | No success output |
| CI/integration | Fail closed when graph rule is required | Canonical non-pass evidence |
| Historical query | May show superseded generation with label | Cannot authorize current action |
| `doctor`/recovery | Graph-independent | Diagnose, delete derived cache, rebuild |

## 13. Security, Privacy, and Resource Controls

- Resolve and validate every path through the centralized containment API.
- Reject graph/cache paths that are symlinks or escape approved state roots.
- Parameterize all storage queries and validate schema versions.
- Store no source bodies by default; attributes are bounded and redacted.
- Apply per-provider limits for files, bytes read, runtime, nodes, edges,
  incidences, attributes, diagnostics, and output bytes.
- Apply traversal depth, fan-out, cycle, and total-result caps.
- Give derived state restrictive filesystem permissions.
- Treat persisted graph data as an untrusted cache: verify canonical digests
  before use and rebuild after corruption.
- Never store secrets, unrestricted environment values, raw prompts, or
  unrestricted analyzer output.
- Refuse authoritative operation on unsupported network filesystems rather than
  assuming SQLite locking semantics.

## 14. Persistence Admission Gate

The initial hypergraph is ephemeral and computed on demand. SQLite through the
standard library is the preferred candidate only if all of these are measured:

1. Representative full graph builds exceed agreed interactive or explicit-command budgets.
2. Incremental reuse produces a material measured improvement.
3. Identical snapshots produce byte-identical graph digests with and without persistence.
4. Cache deletion and rebuild recover every authoritative fact.
5. Multiprocess lock, crash, disk-full, corruption, read-only, and migration tests pass.
6. Local-filesystem requirements and unsupported-filesystem behavior are documented.
7. Hook reads remain bounded; hooks never perform schema migration or large rebuilds.
8. A cache lock or failure returns unavailable/unknown, never a stale success.

If admitted, immutable graph generations, append-only events, and mutable
operational projections use separate logical schemas and retention rules.

## 15. Migration Strategy

1. Define canonical contracts and adversarial fixtures.
2. Build an ephemeral graph from immutable committed snapshots.
3. Add working-snapshot manifests for local advisory analysis.
4. Run graph-native links, topology, impact, and verification selection in
   shadow mode beside existing implementations.
5. Compare result state, affected scope, rationale, latency, and provider
   completeness for identical inputs.
6. Promote one consumer at a time only after parity or approved semantic change.
7. Evaluate persistence only after profiling.
8. Add graph-expanded strict claims only after provider completeness and claim
   concurrency evidence exist.
9. Enable Fettle self-governance before recommending strict adoption elsewhere.

## 16. Architectural Invariants

1. A source snapshot identifies one complete materialized input state.
2. Every enforcement fact is attributable to provider, version, configuration,
   input digest, run state, completeness, and trust class.
3. Missing, stale, partial, conflicting, or failed required providers cannot produce pass.
4. A graph generation is immutable after atomic publication.
5. Mutable operational state cannot alter an immutable graph digest.
6. Traversal is typed, directed, deterministic, bounded, and cycle-safe.
7. Unknown scope conflicts conservatively in strict concurrency decisions.
8. Database loss cannot destroy Git-authoritative knowledge or manufacture success.
9. Interactive failure remains visible and fail-open; required CI failure is non-pass.
10. Existing behavior remains authoritative until shadow graduation.
11. No graph failure disables the graph-independent safety and recovery kernel.
12. Every critical action and attestation names the exact immutable snapshot it governs.

## 17. Decision Record

| ID | Decision | Rationale |
|---|---|---|
| CI-D1 | Hypergraph is the semantic foundation, not the bootstrap kernel | Avoid circular recovery and a universal failure domain |
| CI-D2 | Critical actions use immutable snapshot semantics | Filesystem freshness checks cannot eliminate TOCTOU |
| CI-D3 | Start ephemeral; persistence is evidence-gated | Preserves the current roadmap and Stage 6 decision |
| CI-D4 | Separate immutable, append-only, and mutable state | Preserve reproducibility while supporting coordination |
| CI-D5 | Provider completeness is first-class | Missing edges must not be interpreted as unaffected |
| CI-D6 | Traversal rules are explicit versioned policy | Reachability alone must not become enforcement |
| CI-D7 | Work-item claim expands to file footprint; semantic-region claims deferred | Smallest reliable concurrency extension |
| CI-D8 | External graph tools enrich but do not silently define authority | Preserve portability and explicit trust |
| CI-D9 | Existing consumers migrate through shadow parity | Prevent a graph rewrite from changing shipped behavior silently |
| CI-D10 | P33/P41 integrity work gates blocking graph evidence | Enforcement must not build on false-clean or mutable evidence |
