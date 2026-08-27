---
fettle-work-item: v2
id: p56-consistency-evaluator
status: done
scope:
  - fettle/consistency_compare.py
  - fettle/consistency_runner.py
  - fettle/state_consistency.py
  - tests/test_consistency_compare.py
  - tests/test_consistency_runner.py
  - tests/test_state_consistency.py
spec: state-consistency-implementation-plan
---

# P56a/SC4 - immediate and eventual consistency evaluation

## Resolution

The runner compares JSON observations with type-preserving exact fingerprints or
recursive Unicode NFC-normalized fingerprints. Raw values remain transient and
are not retained in evidence. Immediate contracts produce `converged` or
`divergent`; eventual contracts poll only mismatching observers until all
converge or the shared monotonic deadline produces `stale`. Evidence records the
last redacted fingerprint, attempt count, and convergence duration.

Malformed comparison evidence remains `unknown`. Adapter and cleanup failures
remain `tool_error`, with cleanup evidence separate from the primary error.
`divergent` and `stale` stay advisory at the CLI boundary.

Snapshot, monotonic, and two-operation temporal evaluation are deferred to P56b
because the frozen v1 schema does not define their capture, ordering, or mutation
contracts.
