---
fettle-work-item: true
id: p64-methodology-automation
status: done
scope:
  - .github/workflows/mutation.yml
  - tests/test_ci.py
  - tests/test_p64_methodology.py
spec: fettle-evolution-implementation-plan
---

# P64 — Automated methodology and evidence staging (status record)

Per-item disposition against evolution-plan checklist items 21–31:

| # | Item | Status | Evidence |
|---|---|---|---|
| 21 | Full-mutation workflows require successful preflight | DONE | `tests/test_ci.py::test_full_mutation_workflow_gates_fanout_on_retained_preflight` |
| 22 | Unpinned tools / missing retained preflight detected | DONE | `requirements-mutation.txt` hash-pinned; doctor reports pinned engine readiness; workflow consumes `--retained-preflight` |
| 23 | Parallel authoritative calibrations forbidden | DONE | Playbook invariant ("run authoritative calibrations sequentially") + serialized scheduling introduced with the replay gate (#11) |
| 24 | Adversarial regression tests on canonicalization changes | DONE | Multi-hunk f-string fixture (P63 incident) in `tests/test_mutation_test.py` |
| 25 | Preflight bound to revision/policy/scope/mapping/engine/manifest | DONE | Preflight identity contract tests in `tests/test_mutation_test.py` |
| 26 | Workers consume preflight+manifest with exact identities | DONE | `--resume-manifest` validation chain (revision + manifest digests) asserted in workflow tests |
| 27 | Staged model applied to other expensive providers | PARTIAL | Graph program built staged-by-construction (advisory→shadow→enforce); remaining legacy consumers tracked as P48 |
| 28 | Readiness/outcomes/policy kept separate per provider | PARTIAL | New providers (snapshots, ledger, graph) return distinct status envelopes; legacy consumer separation lands with P48 |
| 29 | Caches untrusted; full identity validation before reuse | DONE | `mutation_cache_reusable` identity validation; external caches disabled-by-default in hypergraph doctrine |
| 30 | Bounded diagnostics: stage/subject/reason/evidence/recovery | PARTIAL | Dispatcher trace events + failure ingest (Stage 0); new providers return reason+recovery envelopes; full sweep pending P48 graduation |
| 31 | Narrow replay suites before expensive end-to-end per provider | PARTIAL | Mutation replay shipped (#11); snapshots/ledger/graph covered by narrow unit contracts; UAT replay arrives with P72 artifacts |

## Resolution

Items 21–26 and 29 closed with cited evidence; 27–28 and 30–31 remain open
ONLY where they depend on P48 shadow graduation of legacy consumers — that
dependency is recorded here and in plan-index.md. Consolidated regression:
`tests/test_p64_methodology.py` pins the workflow-level guarantees.
