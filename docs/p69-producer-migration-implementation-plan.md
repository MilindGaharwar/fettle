# P69 Producer Migration And Override Integrity

Status: approved for implementation by the P66-P69 evidence contracts.

## User Outcome

As a maintainer relying on coverage, UAT, integrations, mutation testing, or an
override, I want each consequential result bound to portable canonical evidence
without losing its domain report, so that missing, stale, tampered, or
misapplied evidence cannot silently become a pass.

## Assumptions And Boundaries

- The P66 artifact schema and P67-P68 kernel are frozen and remain the common
  validation authority.
- Existing domain reports, verdicts, output states, and recovery instructions
  remain unchanged. Canonical artifacts are additive sidecars.
- Producer migration is enabled independently and can be rolled back to the
  legacy writer without deleting or rewriting legacy records.
- P70 shadow-run graduation, P71 graph/persistence work, state-consistency
  producers, attestations, and a global evidence database are out of scope.
- A canonical mutation artifact references the complete schema-v2 report and
  calibration identities; it never copies or replaces mutant-level records.

## Approach And Tradeoffs

Use producer-owned adapters over one generic producer framework. A small shared
module owns only canonical hashing, atomic sidecar persistence, reference
construction, and validation plumbing. Each producer owns its kind, bindings,
trust class, completeness rules, payload schema, invalidation, and recovery.

This duplicates a small amount of builder code but keeps domain authority
visible and allows independent rollback. A generic store or producer base class
would reduce repetition while creating a new authority boundary and obscuring
stronger domain invariants.

## Blast Radius

- Evidence kernel consumers and finding serialization.
- Coverage Stop decisions and coverage report retention.
- UAT checkpoints, transcripts, reconciliation reports, and manual attestations.
- Integration report construction across SonarQube, Black Duck, and Pact.
- Mutation report production, aggregation, baseline comparison, and calibration.
- CI and mutation override selection plus ratchet demotion.
- Ratchet and compliance report JSON names and reproducibility metadata.

`kgraph impact fettle/evidence.py` reports broad shared-schema reach and a stale
index; all direct imports and full tests are therefore required before shipping.

## Compatibility Contract

| Producer | Legacy authority retained | Canonical kind | Rollback |
|---|---|---|---|
| Coverage | `coverage.json` and current decision | `fettle.coverage` | `canonical_evidence = false` |
| UAT session/report | checkpoint, transcript, report, attestation | `fettle.uat.session`, `fettle.uat.report` | `uat.canonical_evidence = false` |
| Integration | `IntegrationReport` | `fettle.integration` | constructor/config opt-out |
| Mutation | schema-v2 report and baseline/calibration identities | `fettle.mutation.report` | canonical wrapping is consumer-local; legacy report production is unchanged |
| Overrides | strict v1 remains readable but cannot satisfy v2 resolution | `fettle.override` expected kind | use legacy reader; no v2 downgrade rewrite |
| Ratchet/compliance | existing JSON shape | aggregate summaries, not artifacts | type rename has no wire change |

## Detailed Tasks And Checks

1. Add shared canonical sidecar helpers in `fettle/producer_evidence.py`.
   Check deterministic hashes, atomic writes, exact references, malformed and
   missing sidecars in `tests/test_producer_evidence.py`.
2. Extend coverage configuration and `fettle/coverage_gate.py` to persist a
   canonical sidecar that references the complete `coverage.json`, edited-line
   scope, thresholds, branch availability, result, and recovery command.
   Check pass/violation/stale, parity, tampering, and rollback in
   `tests/test_coverage_gate.py`.
3. Extend `fettle/uat/session.py` and `fettle/uat/reconcile.py` with separate
   session and report artifacts. Preserve scenario IDs, every five-state
   verdict, could-not-attempt semantics, redaction count, report digest, and
   transcript non-embedding. Check complete, blocked, unobserved, redacted,
   write failure, tampering, and rollback in UAT tests.
4. Extend `fettle/integration_base.py` so reports explicitly carry provider,
   tool identity, trust, determinism, applicability, completeness, source,
   policy, and scope bindings. Keep all five statuses unchanged. Check every
   status, absent version, findings, path normalization, and rollback in
   integration tests.
5. Add mutation artifact construction beside complete schema-v2 reports. Payload
   contains report location/digest, report schema, identity digests, counts,
   run/calibration IDs, and baseline references only. Check incomplete reports,
   digest mismatch, calibration mismatch, aggregate output, and rollback in
   mutation tests.
6. Introduce strict override schema v2 with source snapshot digest and expected
   artifact kind. Keep v1 records readable and visible. Resolve v2 evidence
   before selection and return a typed non-pass for missing, malformed,
   tampered, stale, or wrong-bound artifacts. Check every binding independently,
   expiry, duplicate IDs, mixed ledgers, and no automatic rewrite.
7. Update CI, mutation baseline, and ratchet override callers with exact kind and
   source bindings. Check no unrelated override can authorize a decision.
8. Rename `ratchet.Evidence` to `RuleEvidenceStats` and
   `compliance.ControlEvidence` to `ControlCoverageSummary`. Add source-window
   start/end and content digest where the aggregate is persisted or returned.
   Check deterministic digest, empty input, malformed lines, and unchanged
   policy/report semantics.
9. Document producer payload schemas, retention, invalidation, recovery, and
   rollback in `docs/evidence-artifact-contract.md`; update roadmap status only
   after all completion evidence passes.
10. Run focused suites after each producer, then Ruff, full pytest, CLI UAT,
    Fettle changed scan, completion validation, and independent diff review.

## Success Criteria

- Every P69 producer has a complete domain report reachable from its canonical
  reference and an independently tested rollback path.
- Legacy and canonical paths yield identical domain decisions and messages.
- Wrong source, revision, policy, scope, surface, check, kind, producer,
  completeness, validity period, or unresolved artifact cannot authorize an
  override.
- Mutation fingerprints, manifests, counts, and calibration identities remain
  in the schema-v2 report and survive round trips unchanged.
- Aggregate reports identify their source window and digest and are never
  accepted as primary observations.
- Focused and full automated tests pass; CLI error recovery is manually checked;
  `fettle check --changed` and completion validation pass.

## UAT Scenarios

Scenario: Inspect migrated producer evidence
  Given a producer has emitted its existing domain report
  When a maintainer follows the canonical reference
  Then the exact complete domain report is reachable and all bindings validate

Scenario: Recover from invalid canonical evidence
  Given a canonical sidecar is missing, malformed, stale, or tampered
  When a consequential consumer evaluates it
  Then the result is non-pass and names the producer-specific regeneration action

Scenario: Roll back one producer
  Given one migrated producer is incompatible in an installation
  When its canonical evidence switch is disabled
  Then its legacy behavior and output remain unchanged without affecting others

Scenario: Reject a misbound override
  Given an active override references evidence of the wrong kind or binding
  When a consequential check selects the override
  Then authorization is refused and the underlying result remains non-pass
