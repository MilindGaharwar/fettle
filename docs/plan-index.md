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
| State consistency | `state-consistency-implementation-plan.md` (+ UX spec) | P53-P56 complete; P57-P61 package- or evidence-gated | Review and authorize the P57 web/UAT adapter package |
| Agentic UAT strengthening | `uat-strength-plan.md` + hypothesis tree | P72–P76 done; P77 harness done, parity baseline blocked | Record human sessions across the canonical ten seeds and agree the discovery threshold before graduation |
| **Assurance Integrity** | `assurance-integrity-implementation-plan.md` + `assurance-integrity.ux-spec.md` | **AI-0-AI-7 and frozen baseline collector technically complete; graduation open** | Collect 20 real shadow assessments under the frozen protocol, review every difference, and obtain explicit operator approval |
| Canonical security evidence | `canonical-security-evidence-implementation-plan.md` + `canonical-security-evidence.ux-spec.md` | CS-0-CS-5 and frozen baseline collector technically complete; CS-6 blocked | Collect 20 real shadow assessments; keep enforcement and release blocked pending explicit approval |
| Add-in assurance pilot | `add-in-assurance-implementation-plan.md` + `add-in-assurance.ux-spec.md` | Proposed; implementation not authorized; blocked by CS-6 | Review the plan only; do not implement without separate explicit operator approval |
| Evidence-guided handoffs pilot | `evidence-guided-handoffs-plan.md` + `evidence-guided-handoffs.ux-spec.md` + hypothesis tree | Proposed research program; planning complete; implementation and execution blocked by CS-6 | After CS-6, seek separate authorization for EH-0 contract/fixture freeze; do not add orchestration or enforcement |
| Assurance Record v1 | `assurance-record-plan.md` | P80-P83 delivered; authority limitations superseded by Assurance Integrity | Preserve compatibility while hardening the aggregate boundary |
| Improvement program (audit) | `improvement-plan.md` | Items 1–6 done; 5 index done; 8 partial | Positioning motion capture (operator) |

## Standing rules

- Advisory-first: no gate enforces until its own graduation evidence lands.
- Fail-visible always; completion is criterion-typed evidence.
- Work is claimed through `fettle work` before edits (claim-before-work).
- Assurance Integrity is the only authorized new feature program until it
  graduates; maintenance and defect correction continue.
