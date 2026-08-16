# Portable Evidence Artifact Contract

Status: P66 contract frozen, 2026-08-09; P67-P68 verification, CI, trace, and
inspection bindings implemented by 2026-08-15; P69 producer migration
implemented on 2026-08-16 pending clean full-suite verification. The schema
remains the frozen portable contract, and each migrated domain report retains
its existing authority boundary.

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
| Coverage | `coverage.json` plus `fettle.coverage` sidecar | Full report, source, policy, and edited-line scope digests | Project-owned report and `.fettle/coverage-evidence.json` | Legacy changed-line decision remains authoritative | Additive canonical reference; line and branch data stay in `coverage.json` |
| UAT | Session checkpoint/transcript, report, attestations, and two sidecars | `fettle.uat.session` and `fettle.uat.report`; scenario and report bindings | Worktree `.fettle`; sidecars follow their domain records | Reconciliation and operator attestation remain distinct | Transcript content is referenced by digest, never embedded |
| Integrations | `IntegrationReport` plus in-memory `fettle.integration` artifact/reference | Five-state enum plus provider, trust, completeness, applicability, and bindings | Transient with the report unless the caller retains it | Adapter policy remains authoritative | Canonical wrapping does not change any adapter status |
| Mutation | Schema-v2 report plus consumer-local `fettle.mutation.report` artifact | Full report and identity digests; exact run/calibration identities | Retained report/baseline under existing policy | Complete reports and independent calibration remain authoritative | Strict consumers wrap the report without flattening mutant records |
| Overrides | `OverrideRecord` schemas v1 and v2 | V2 binds full artifact, source, revision, policy, scope, surface, check, and kind | Project `.fettle/overrides.json`; explicit activation and expiry | Only resolved, valid v2 evidence authorizes canonical consumers | V1 is readable and selectable only through explicit legacy rollback |
| Ratchet | Aggregate `RuleEvidenceStats` | Source window, digest, and completeness metadata | `.fettle/ratchet.json` plus trace/FP windows | Supports rule promotion/demotion | Aggregate only; never primary observation |
| Compliance | Aggregate `ControlCoverageSummary` | Source window, digest, and completeness metadata | Computed on demand | Not a certification or primary observation | Aggregate only; malformed source evidence remains visible |
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

## P69 Producer Payloads And Operations

| Kind | Payload and stronger guarantee | Invalidation and recovery | Rollback |
|---|---|---|---|
| `fettle.coverage` | References complete `coverage.json`; carries edited lines, effective thresholds, branch availability, stale state, and recovery command | Source edit, policy/scope change, stale report, missing/tampered report, or write failure invalidates it; run `pytest --cov --cov-report=json` | `gates.coverage.canonical_evidence = false` |
| `fettle.uat.session` | References the redacted transcript by portable name and digest; carries surface, scenario IDs, status, and redaction count | Transcript/checkpoint change or sidecar failure invalidates it; rerun `fettle uat run` | `uat.canonical_evidence = false` |
| `fettle.uat.report` | References the complete report by digest; carries all scenario verdicts and completion counts without transcript observations | Session/report change or sidecar failure invalidates it; rerun reconciliation | `uat.canonical_evidence = false` |
| `fettle.integration` | Embeds the bounded domain report and records provider, tool identity, trust, determinism, applicability, and explicit bindings | Any provider result or effective config/scope change invalidates it; rerun the named integration | Per-adapter `canonical_evidence = false` |
| `fettle.mutation.report` | References a complete schema-v2 report and carries identity digests, counts, and run/calibration IDs; mutant records remain in the report | Incomplete/tampered report, report digest mismatch, or calibration mismatch rejects construction; rerun mutation/calibration | No producer writer is replaced; consumers may stop requesting the wrapper |

Sidecars have the same retention horizon as the domain records they reference.
They are written atomically where persisted. A failed additive write never
changes the legacy domain result, but it is recorded or logged and cannot be
used by a consequential canonical consumer.

## Compatibility Matrix

| Existing representation | P66/P67 handling | Authority and expiry |
|---|---|---|
| Trace v1 entries | Read-only tolerant diagnostic | Read forever as currently promised; never artifact authority |
| Trace v2 bounded `ev-` evidence | Read-only legacy reference | Retain under current rotation; truncated ID cannot become v1 digest |
| Finding bare `evidence_id` and reference v1 | Read-only on existing host wires | No independent artifact validation; new consequential uses require v2 |
| Verify stamp | P67 writes and validates a canonical artifact alongside it; legacy-only stamps remain readable for rollback | A stamp claiming canonical evidence must pass digest, occurrence, source, policy, scope, producer, completeness, and trust validation; invalid claimed evidence is non-pass |
| CI status stamp | Read-only until P68 | Existing SHA/timestamp gate remains authoritative; local verify evidence cannot substitute |
| Coverage and UAT records | Additive P69 sidecars; legacy records unchanged | Existing domain semantics and retention remain; switches independently disable sidecars |
| Integration report | Additive in-memory P69 artifact/reference | Existing adapter policy remains; unavailable cannot become pass |
| Override schema v1 | Strict read with no automatic rewrite | Selectable only through explicit legacy rollback; canonical consumers require v2 |
| Mutation report schema v2 and baseline v1 | Reference, never flatten or migrate in P66 | Existing report/baseline validators remain authoritative |
| Provider fact sets and graph records v1 | Reference after producer/consumer graduation | Current contracts remain advisory; cache presence grants no authority |
| Ratchet `RuleEvidenceStats` / compliance `ControlCoverageSummary` | Aggregate with source-window metadata | Never accepted as primary observations |
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

## P41 Attestation Integration Boundary

P68 publishes an integration point, not an attestation implementation. After
P38 and P41 receive separate authorization, a durable attestation may reference:

- the canonical `EvidenceArtifact.artifact_digest` without rewriting or
  flattening the artifact;
- the artifact's `observation_id` when one execution occurrence must be named;
- the immutable candidate identity independently established by the CI or
  governance provider; and
- the attestation producer, signing mechanism, verification material, issuance
  time, and validity policy in a separate P41-owned versioned object.

The attestation must bind the full artifact digest and immutable candidate
identity in its signed statement. It must not treat trace presence, an
`evidence_id`, a truncated digest, `observed_at`, or local filesystem metadata
as proof. Signature absence, verification failure, candidate mismatch, artifact
unavailability, or artifact validation failure remains non-pass for any future
consumer that requires attestation. P41 owns key lifecycle, platform identity,
revocation, transparency, retention, and durable commit linkage; P68 owns none
of those guarantees and trace labels canonical references `diagnostic_only`.

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
