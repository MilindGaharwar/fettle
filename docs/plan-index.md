# Program Plan Index

Single entry point for Fettle's planning documents. The historical master
plan (`fettle-evolution-implementation-plan.md`) remains the canonical
decision record; per-program details live in the dedicated plans below.
Physical extraction of remaining sections is deferred to avoid link rot —
this index is the navigation layer.

| Program | Detailed plan | Status | Next actions |
|---|---|---|---|
| Evidence convergence | `fettle-evolution-implementation-plan.md` P66–P71 (inline) | P66–P69 complete; P70/P71 evidence-gated | Accumulate qualifying runs via required PR mutation gate |
| Mutation quality | `mutation-quality-implementation-plan.md` + playbook | Baseline complete; advisory graduation | P64 methodology automation; ratchet decision after qualifying runs |
| Change integrity (hypergraph) | `change-integrity-implementation-plan.md` (+ architecture, UX spec) | P44–P46 complete; P47 shipped advisory; P48 next | Shadow parity for semantic/topology/verify consumers; P49 deferred on P41 |
| State consistency | `state-consistency-implementation-plan.md` (+ UX spec) | Contracts proposed; P38 prerequisite now closed | Review/authorize P53 contract package |
| Agentic UAT strengthening | `uat-strength-plan.md` + hypothesis tree | P72–P74 done; P75–P77 planned | Claim `docs/backlog/uat-evidence-hardening.md` (done) → P73 charters (done) → P75/P76 |
| **Assurance Record** | `assurance-record-plan.md` | **P80 authorized, in progress** | Build `fettle/assurance.py` v1: aggregate existing artifacts into the canonical record |
| Improvement program (audit) | `improvement-plan.md` | Items 1–6 done; 5 index done; 8 partial | Positioning motion capture (operator) |

## Standing rules

- Advisory-first: no gate enforces until its own graduation evidence lands.
- Fail-visible always; completion is criterion-typed evidence.
- Work is claimed through `fettle work` before edits (claim-before-work).
