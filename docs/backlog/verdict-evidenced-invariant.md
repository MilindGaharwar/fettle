---
fettle-work-item: true
id: verdict-evidenced-invariant
status: open
scope:
  - tests/test_invariants.py
spec: improvement-plan
---

# House invariant — "verdict-visible means evidenced"

Adopted from dsh's "model-visible means logged" runtime invariant: any
decision surfaced to an agent or operator must be reconstructable from
retained evidence (artifact path/digest/ledger record). Encode as a house
test, generalizing the P72 UAT rule to all surfaces.

MVP scope: for a fixture session, assert every authorship-gate block,
verify stamp, and UAT report verdict logged via `fettle.trace` has a
corresponding evidence artifact reference (report JSON, ledger record, or
EvidenceArtifact file) recoverable from disk.

## Done when

- Invariant test passes on the standard flows.
- Adversarial case: deleting the backing artifact makes the invariant fail
  loudly (fail-visible), proving it is not vacuous.

## Resolution

Record how it was resolved.
