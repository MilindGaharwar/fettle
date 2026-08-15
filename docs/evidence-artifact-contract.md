# Portable Evidence Artifact Contract

Status: P66 contract frozen, 2026-08-09; P67 verification pilot implemented,
2026-08-15. The schema remains the frozen portable contract. Runtime adoption
is currently limited to `fettle verify`; CI, trace, and other producers retain
their existing authority boundaries until P68-P70.

P66 itself does not change any current writer, reader, policy decision, or
authority boundary; the active verification behavior is the separately tested
P67 implementation.

## Purpose And Boundary

An evidence artifact is a portable, immutable observation envelope. It answers:

- what was observed and with what result;
- which producer and version made the observation;
- which source, policy, and scope the observation covers;
- whether the observation is complete and how it may be trusted; and
- which execution occurrence produced it.

Artifacts do not make policy decisions, grant overrides, or become
attestations merely because they have a digest. Findings, decisions,
attestations, diagnostics, and aggregate statistics remain separate objects
that may reference artifacts. Domain reports retain stronger invariants; the
common envelope never replaces mutation fingerprints, provider facts, graph
digests, UAT scenarios, or CI run records.

Memory, model confidence, advisory graph output, and external indexes cannot
grant authority. Missing or invalid evidence is a canonical non-pass for every
consequential consumer.

## Representation Inventory

| Surface | Current representation and owner | Schema / identity | Persistence and retention | Current authority | P66 target |
|---|---|---|---|---|---|
| Finding | `CheckFinding` and two-field `EvidenceReference` in `fettle/finding.py`; transported by `fettle/dispatcher_types.py` | Finding `0.6.0`; optional opaque `evidence_id`; reference has ID plus kind | Host response and bounded trace | Finding and dispatcher state drive the current decision | Finding remains a domain object; additive reference v2 is specified below |
| Trace | `build_evidence` and audit entries in `fettle/trace.py` | Trace v1 tolerated, writer v2; truncated `ev-` hash over a small projection | JSONL under `XDG_STATE_HOME`; rotates near 5 MiB / 5,000 entries | Audit/diagnostic only; local trace is not attestation | Read-only legacy input; P68 may retain artifact references additively |
| Verify | Stamp in `fettle/verify_gate.py` | Unversioned `evidence_id`; session, HEAD, dirty digest, scope | `.fettle/verify.json`, replaced per run | Fresh matching stamp can satisfy verify gate | Read-only until P67 pilot; migrate only after exact source/policy/scope binding exists |
| CI | Stamp and GitHub run records in `fettle/ci_gate.py` | Unversioned `evidence_id`; SHA and timestamp; CI policy digest calculated separately | `.fettle/ci-status.json`, replaced per query; remote retention is provider-owned | Fresh SHA-bound stamp informs CI gate and exact override lookup | Read-only until P68; canonical artifact must remain independently recomputed from local evidence |
| Coverage | `coverage.json` plus bounded reference in `fettle/coverage_gate.py` | Tool format is external; current reference is opaque | Project tool output; retention is project-owned | Fresh changed-line result may advise or block | Domain report referenced by artifact after P69; never flatten line/branch data |
| UAT | Session checkpoint/transcript and operator records in `fettle/uat/` | Unversioned `evidence_id`; scenario IDs and labeled source | Worktree `.fettle/uat-session.json`, transcript, `.fettle/uat-attestations.json` | UAT reconciliation and operator attestation remain distinct | Wrap outcomes after P69; preserve scenario, source, redaction, and could-not-attempt semantics |
| Integrations | `IntegrationReport` in `fettle/integration_base.py` | Five-state domain enum and opaque evidence reference | Usually transient/host output | Adapter policy maps availability and result | Preserve report; artifact records producer, trust, completeness, and bindings after P69 |
| Mutation | Schema-v2 report and baseline in `fettle/mutation_test.py` and `fettle/mutation_baseline.py` | Full SHA-256 fingerprints and report digests; exact run-pair identity | Retained CI artifacts; committed accepted baseline | Complete reports and independent calibration pair are authoritative | Reference complete report after P69; never replace fingerprints, manifests, counts, or calibration |
| Overrides | `OverrideRecord` in `fettle/overrides.py` | Strict schema v1; content-derived `ov-` ID; exact revision/policy/evidence/scope/surface match | Committed/project `.fettle/overrides.json`; explicit expiry | An exact active record changes disposition, never raw result | Keep strict v1 until P69 adds expected artifact kind and full binding migration |
| Ratchet | Aggregate `Evidence` in `fettle/ratchet.py` | Ratchet schema v1; mutable counters, no source-window digest | `.fettle/ratchet.json` plus trace/FP windows | Supports rule promotion/demotion | Remains aggregate statistics; rename to `RuleEvidenceStats` during P69, not P66 |
| Compliance | `ControlEvidence` in `fettle/compliance.py` | Unversioned 30-day aggregate over trace | Computed on demand | Explicitly not a certification or primary observation | Remains aggregate; rename to `ControlCoverageSummary` during P69 |
| Provider facts | `ProviderFactSet` in `fettle/provider_contract.py` | Canonical full digest; producer/config/input, state, completeness, trust | In-memory contract today | Future graph consumers must validate stronger provider invariants | Domain report referenced by artifact; provider trust never upgrades artifact authority |
| Graph | Immutable records in `fettle/graph_types.py` | Graph/canonicalization v1; full canonical SHA-256 identities | Ephemeral by default; any future store is untrusted derived cache | Advisory contracts only until consumer graduation | Graph records reference accepted artifacts under P71; graph confidence cannot grant authority |
| Dispatcher | `CheckResult` in `fettle/dispatcher_types.py` | Canonical state, decision, findings, references | Host response and trace | Current hook authority boundary | Keep wire format unchanged in P66; P67 compatibility tests gate additive v2 transport |

Current bare evidence IDs are locator-like labels, not independently verifiable
content identities. No current surface is silently reinterpreted as an
`EvidenceArtifact`.

## EvidenceArtifact Schema V1

The JSON object has exactly these fields. Optional fields may be omitted; JSON
`null` is not a substitute.

| Field | Type | Contract |
|---|---|---|
| `schema_version` | string | Exactly `"1"` |
| `artifact_digest` | string | `sha256:` plus 64 lowercase hex characters over the content projection |
| `kind` | string | Stable namespaced evidence kind, 1-128 UTF-8 bytes |
| `producer` | object | Exactly `id`, `version`, and `implementation_digest`; all non-empty |
| `result_state` | string | `pass`, `violation`, `overridden`, `tool_error`, `unknown`, or `not_applicable` |
| `completeness` | string | `complete`, `partial`, or `unknown` |
| `trust_class` | string | `authoritative`, `derived`, `heuristic`, or `external` |
| `source` | object | Exactly one stable source binding: `snapshot_digest` and optional `revision` |
| `policy_digest` | string | Full SHA-256 of effective policy; required even when policy is empty |
| `scope_digest` | string | Full SHA-256 of canonical selected scope |
| `observation_id` | string | Unique execution occurrence ID, 1-128 UTF-8 bytes; not content identity |
| `observed_at` | string | UTC RFC 3339 instant with `Z`, second or finer precision |
| `payload` | object | Bounded, kind-specific canonical JSON; no authority is inferred from its keys |
| `parents` | array | Optional sorted, unique `EvidenceReference` v2 objects; maximum 64 |

The **content projection** contains every artifact field, including optional
`parents`, except `artifact_digest`, `observation_id`, and `observed_at`. Thus
schema, kind, the complete producer identity, source, policy, scope, result,
completeness, trust class, payload, and parent references all participate.
Consequently independent executions may share content identity while retaining
distinct occurrence identity. Occurrence fields are protected by transport
integrity or a later attestation; the content digest is not an attestation of
when or where execution happened.

`pass` does not imply complete. A consequential consumer accepts a pass only
when its contract also requires and observes `completeness = complete`, an
allowed trust class, and exact requested bindings. `overridden` remains a
non-pass disposition and requires its separate override record.

## EvidenceReference V2

V2 is an additive successor to the current `{evidence_id, kind}` shape:

```json
{
  "artifact_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "kind": "fettle.verify",
  "schema_version": "1",
  "expected": {
    "source_snapshot_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "policy_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "scope_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "producer_id": "fettle.verify"
  }
}
```

`expected` contains only bindings the consumer requires. Omission means “not
requested,” never “matched.” A consequential consumer must require every
binding needed for its decision. The reference does not embed a mutable path,
URL, TTL, result state, or policy disposition. Artifact availability is a
separate transport concern.

## Canonical Encoding And Bounds

- Encode UTF-8 JSON with NFC-normalized strings, keys sorted by UTF-8 byte
  order, no insignificant whitespace, and no byte-order mark.
- Object keys are strings and must remain unique after NFC normalization.
- Numbers are integers only. Floats, NaN, infinity, duplicate keys, arbitrary
  objects, and implicit stringification are rejected.
- Repository paths in a kind-specific payload use `/`, are NFC normalized,
  non-empty, and repository-relative after POSIX normalization. Absolute paths,
  `..` escapes, drive prefixes, and ambiguous normalized aliases are rejected.
- Arrays preserve semantic order unless their field explicitly says sorted and
  unique. `parents` sort by `(artifact_digest, kind, schema_version)`.
- All identity fields use full SHA-256. Truncated legacy IDs are never promoted
  to artifact digests.
- Maximum canonical artifact size is 1 MiB; payload is at most 768 KiB; string
  values are at most 64 KiB; nesting depth is at most 32; objects have at most
  4,096 keys; arrays have at most 10,000 items except `parents` (64).
- Payloads must pass the maintained secret and absolute-path filters before
  persistence. Redaction changes content and therefore changes the digest.
- V1 rejects unknown top-level, producer, source, reference, and expected-binding
  fields. Kind-specific payload readers may define their own versioned extension
  fields inside `payload`.
- The digest is lowercase `sha256:` plus the SHA-256 of canonical UTF-8 bytes of
  the content projection. A supplied digest mismatch is `tampered`; a duplicate
  observation ID with different content is `duplicate_id`; equal digests with
  unequal canonical content is `digest_collision` and fails closed.

## Validity And Consequential Mapping

Validation is distinct from policy disposition. It returns one of:

| Validity | Meaning | Consequential result |
|---|---|---|
| `valid` | Schema, digest, availability, required bindings, and consumer constraints match | Consumer may evaluate domain policy |
| `missing` | Required reference or artifact absent | `unknown` |
| `unavailable` | Locator/store/provider cannot be reached | `tool_error` |
| `malformed` | JSON, type, bounds, normalization, secret, or path contract fails | `unknown` |
| `unsupported` | Schema, kind, producer, or producer version is not admitted | `unknown` |
| `tampered` | Supplied digest differs from canonical content | `unknown` |
| `digest_collision` | One digest names unequal canonical content | `unknown` |
| `duplicate_id` | One observation ID names unequal occurrences/content | `unknown` |
| `incomplete` | Completeness is not sufficient for the requested decision | `unknown` |
| `stale` | Explicit freshness/invalidation contract is not satisfied | `unknown` |
| `wrong_source` | Requested source binding differs | `unknown` |
| `wrong_policy` | Requested policy binding differs | `unknown` |
| `wrong_scope` | Requested scope binding differs | `unknown` |
| `wrong_producer` | Requested producer binding differs | `unknown` |

No validity failure maps to pass, clean, allow, or not-applicable. Interactive
surfaces may remain policy-controlled fail-open, but must expose the non-pass
state and recovery action. CI and other consequential boundaries fail closed.
A generic age TTL cannot establish freshness; the consumer evaluates exact
source, policy, scope, producer, and kind-specific invalidation inputs.

## Compatibility Matrix

| Existing representation | P66/P67 handling | Authority and expiry |
|---|---|---|
| Trace v1 entries | Read-only tolerant diagnostic | Read forever as currently promised; never artifact authority |
| Trace v2 bounded `ev-` evidence | Read-only legacy reference | Retain under current rotation; truncated ID cannot become v1 digest |
| Finding bare `evidence_id` and reference v1 | Read-only on existing host wires | No independent artifact validation; new consequential uses require v2 |
| Verify stamp | P67 writes and validates a canonical artifact alongside it; legacy-only stamps remain readable for rollback | A stamp claiming canonical evidence must pass digest, occurrence, source, policy, scope, producer, completeness, and trust validation; invalid claimed evidence is non-pass |
| CI status stamp | Read-only until P68 | Existing SHA/timestamp gate remains authoritative; local verify evidence cannot substitute |
| Coverage and UAT records | Read-only until per-producer P69 migration | Existing domain semantics and retention remain |
| Integration report | Read-only until P69 | Existing adapter policy remains; unavailable cannot become pass |
| Override schema v1 | Strict read as today; no automatic rewrite | Exact current matching remains; P69 must migrate expected kind/bindings explicitly |
| Mutation report schema v2 and baseline v1 | Reference, never flatten or migrate in P66 | Existing report/baseline validators remain authoritative |
| Provider fact sets and graph records v1 | Reference after producer/consumer graduation | Current contracts remain advisory; cache presence grants no authority |
| Ratchet `Evidence` / compliance `ControlEvidence` | Keep as aggregate; planned names only | Never accepted as primary observations; rename only in P69 implementation |
| Unknown future schema/version | Reject for consequential use; retain bytes only when transport policy permits | No compatibility by guess, coercion, or field-name similarity |

Legacy compatibility has no calendar-based implicit expiry. A writer is removed
only after all maintained readers and known external consumers complete a
documented migration window under P70.

## Threat Model

Protected properties are content integrity, exact applicability, completeness,
portable interpretation, bounded handling, and visible failure. The contract
does not claim confidentiality after artifact export, execution sandboxing,
producer honesty, signature authenticity, durable availability, or prevention
of an authorized producer emitting false observations.

| Threat | Required defense |
|---|---|
| Content tampering or collision substitution | Recompute full digest; compare canonical bytes on duplicate digest; fail closed |
| Replay against another revision/policy/scope | Validate every required expected binding; TTL alone is insufficient |
| Producer or version substitution | Bind producer ID, version, and implementation digest; consumer allowlist |
| Partial result presented as success | Orthogonal result/completeness fields; consequential consumer requires complete |
| Duplicate occurrence identity | Reject unequal records sharing an observation ID |
| Unicode/path aliasing or path disclosure | NFC and repository-relative normalization; reject collisions, absolute paths, and escapes |
| Oversized/deep payload denial of service | Enforce byte, item, key, depth, and parent limits before expensive processing |
| Secret persistence | Filter before write; reject or explicitly redact and re-digest |
| Unknown fields or schemas changing meaning | Reject at authority boundary; no best-effort authoritative parse |
| Missing store, trace, graph, or cache | Visible `unavailable`/`missing`; recompute or fail closed, never authorize from absence |
| Advisory graph or external memory authority escalation | Preserve trust class and domain authority boundary; such output cannot grant authority |
| Artifact confused with attestation | Digest proves content identity only; signatures and commit-linked attestations remain P41-owned |

The machine-readable fixture corpus is `tests/fixtures/evidence/`.
`adversarial-v1.json` names a base artifact and applies these deterministic
operations before validation:

- `replace` replaces the value at an existing RFC 6901 JSON Pointer while
  preserving the supplied digest.
- `add` adds a value at an absent RFC 6901 JSON Pointer while preserving the
  supplied digest.
- `collide` performs `replace`, preserves the supplied digest, and validates
  beside the unmodified base artifact already registered under that digest.
- `duplicate_observation` performs `replace`, recomputes the content digest,
  and validates beside the base occurrence with the same `observation_id`.
- `prefix_bytes` prepends the named bytes (`utf8_bom` is `EF BB BF`) to the
  serialized base artifact.
- `reverse_top_level_keys` serializes the base object with its top-level keys
  in reverse UTF-8 byte order.
- `add_nfc_duplicate_keys` inserts both supplied keys and values into the
  target object before serialization; the two keys must normalize to one NFC
  value.
- `generate_string`, `generate_nesting`, `generate_object`, and
  `generate_array` replace the target with, respectively, an ASCII string of
  `byte_count`, nested one-item arrays of `depth`, an object with `key_count`
  distinct keys, or an array with `item_count` integer items.

JSON operations act on the parsed base and serialization operations act last.
Except where an operation explicitly recomputes it, `artifact_digest` remains
the base value. Every case runs in isolation with the unmodified base artifact
pre-registered. The base artifact's source, policy, scope, producer, and kind
are the consumer's expected context. `missing` and `unavailable` are transport
outcomes and therefore belong to P67 store/locator tests, not transformations
of an available artifact. Advisory-authority and attestation confusion remain
consumer-policy tests. These transformations and expected outcomes are frozen
inputs for P67's executable validator harness; P67 must run the same cases
rather than replace them with implementation-shaped fixtures.

## P66 Acceptance Boundary

P66 is complete only when this inventory, schema, examples, compatibility
matrix, threat model, and adversarial fixture corpus are reviewed together.
P66 deliberately makes no runtime behavior authoritative. Any change to
`fettle/finding.py`, `fettle/trace.py`, producer writers, readers, or host wire
formats belongs to P67 or later and requires its own compatibility evidence.
