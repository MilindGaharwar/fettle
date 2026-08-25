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

MVP scope: for the `examples/assurance-loop/` fixture session (and one UAT
session fixture), assert every authorship-gate block, verify stamp, and UAT
report verdict logged via `fettle.trace` has a corresponding evidence
reference recoverable from disk — checking all three verdict sources:
trace JSONL entries, `.fettle/uat-report.json`, and evidence ledger
records.

## Done when

- Invariant test passes on the standard flows.
- Adversarial case: deleting the backing artifact makes the invariant fail
  loudly (fail-visible), proving it is not vacuous.

## Resolution

Record how it was resolved.
