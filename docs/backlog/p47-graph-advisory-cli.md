---
fettle-work-item: true
id: p47-graph-advisory-cli
status: done
scope:
  - fettle/graph_cli.py
  - fettle/cli.py
  - fettle/hypergraph.py
  - tests/test_graph_cli.py
spec: change-integrity-implementation-plan
---

# P47 — Advisory `fettle graph status|impact` CLI

Authorized-in-principle; sole dependency P46 complete. Plan:
`docs/change-integrity-implementation-plan.md` §5.P47.

## Resolution

Shipped `fettle graph status` (digest, node/edge counts, per-provider
completeness with notes; exit 2 fail-closed on snapshot/tool errors) and
`fettle graph impact <paths>` (advisory undirected blast-radius closure,
seeds resolved by stable-key suffix or attribute path; unmatched paths
reported; JSON or human output). Closure engine lives on EphemeralGraph.
Fixed a latent assembler bug en route: EphemeralGraph node storage was
stable-key-indexed while lookups used canonical ids — every node lookup
silently returned None. Contract coverage in tests/test_graph_cli.py
(6 tests incl. exit-code and fail-closed paths). Advisory-only; no gate
consumes this output yet (P48 shadow parity is the next door).
