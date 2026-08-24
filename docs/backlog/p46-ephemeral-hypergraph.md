---
fettle-work-item: true
id: p46-ephemeral-hypergraph
status: open
scope:
  - fettle/hypergraph.py
  - fettle/graph_builder.py
  - fettle/providers/
  - tests/test_graph_builder.py
  - tests/test_graph_providers.py
spec: change-integrity-implementation-plan
---

# P46 — Deterministic ephemeral hypergraph and native providers

Authorized-in-principle 2026-08-23; dependencies P38, P44, P45 all complete.
Plan: `docs/change-integrity-implementation-plan.md` §5.P46.

Provider adapters over specifications/scenarios, trace markers, work-item
declarations, workspace routing, and Python imports/exports. Canonicalize,
deduplicate, validate references, compute the graph digest only after all
required providers finish; publish atomically within the process; typed
containment edges; integer handles never enter canonical output; external
providers disabled by default; full-build reconciliation fixtures; build
budget measured on small/medium/large corpora.

## Done when

Per §5.P46 acceptance: identical snapshot+policy+manifests → identical
digest; readers never observe partial publication; native semantic links at
parity or documented difference; regrouping never changes node identity;
build budget met on the maintained corpus — each proven in tests.

## Resolution

Delivered `fettle/providers/` (specs, trace markers, work items,
workspaces, Python imports), `fettle/hypergraph.py` (two-phase assembler:
drafts → content-addressed P44 types → atomic frozen generation with
bidirectional incidence indexes; integer handles internal only), and
`fettle/graph_builder.py` facade binding the P45 committed-snapshot digest
into every generation. Determinism proven by double-build digest equality;
dangling references and kind conflicts rejected fail-visible; self-repo
full build ≈7 s (budget 60 s). Documented difference vs `semantic.py`:
filename-similarity links are intentionally NOT carried into canonical
output — only explicit markers create verifies edges. JS/TS/Go/Rust import
coverage is declared incomplete in provider notes pending future providers.
Tests: tests/test_graph_builder.py (6) + test_graph_providers.py (5).
