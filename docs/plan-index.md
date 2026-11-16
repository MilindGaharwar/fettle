# Program Plan Index

Single entry point for Fettle's planning documents. The historical master
plan (`fettle-evolution-implementation-plan.md`) remains the canonical
decision record; per-program details live in the dedicated plans below.
Physical extraction of remaining sections is deferred to avoid link rot —
this index is the navigation layer.

| Program | Detailed plan | Status | Next actions |
|---|---|---|---|
| Application audit hardening (2026-09-18) | [Prioritized work packages](audit-hardening-implementation-plan.md) + [UX contract](audit-hardening.ux-spec.md) + [worklog](audit-hardening-worklog.md) | Accepted: PR #46 source `9791109` landed as tree-equivalent squash `2605978`; PR #47 source `a572f80` landed as tree-equivalent squash `023f9b3`; exact-tip main CI passed | Begin P0-ERA before any fresh D4 full-scope provider run; full mutation qualification remains `CLOSED_NON_PASS` |
| Evidence convergence | `fettle-evolution-implementation-plan.md` P66–P71 (inline) | P66–P69 complete; P70/P71 evidence-gated | Treat PR mutation evidence as advisory input only; qualification requires its own complete evidence |
| Mutation quality | `mutation-quality-implementation-plan.md` + playbook | D4 closed: run 1 passed; run 2 is a formal non-pass because its aggregate rejected a rescued shard, a defect fixed by the bounded selector; full-corpus qualification remains `CLOSED_NON_PASS` | No third run was made. On 2026-11-14 the owner amended the criterion from three consecutive passing runs to the two executions measured here. No baseline or ratchet is proposed. Open mutation programme questions are deferred to TR-8 of the trust remediation plan. |
| Change integrity (hypergraph) | `change-integrity-implementation-plan.md` (+ architecture, UX spec) | P44-P47 complete; P48 contextual advisory implemented but not promoted | Preserve existing authority; P49 remains deferred on P41 |
| Contextual impact analysis | `contextual-impact-implementation-plan.md` + UX spec + hypothesis tree | Experimental advisory implementation complete; implementation package CI-3/research CI-2 promotion falsified by 78.05% held-out required recall against the required 100%, 7/20 eligible cases, and inconclusive gain interval | After TR-9, begin with read-only analysis of misses in `docs/contextual-impact-corpus/evaluation.json`; a new hypothesis and plan, separate approval, and a fresh pre-frozen corpus are required before implementation (owner decision 2026-11-16) |
| Runtime secret protection | `runtime-secret-protection-implementation-plan.md` + UX spec | Strict pre-tool boundary and truthful host capability reporting implemented and contract-tested | Verify each installed host separately; retain Codex/OpenCode output filtering as unsupported until transport evidence proves replacement capability |
| Quality gate remediation | `quality-gate-remediation-plan.md` | Complete; required scanner failures are fail-visible and the canonical scan is clean | Preserve scanner-status and rule-precision regression coverage |
| State consistency | `state-consistency-implementation-plan.md` (+ UX spec) | P53-P56 complete; P57-P61 package- or evidence-gated | Review and authorize the P57 web/UAT adapter package |
| Agentic UAT strengthening | `uat-strength-plan.md` + hypothesis tree | Controller integrity, browser audit and hard-interruption recovery verified; bounded native input-discovery study matched 12/12 cases; checkpoint review and full 3,466-test suite passed; P77 parity unproven | Verify checkpoint commits through fresh remote CI; structured native denial and general discovery remain open; no release or enforcement promotion |
| **Assurance Integrity** | `assurance-integrity-implementation-plan.md` + `assurance-integrity.ux-spec.md` | **Graduated; 20 shadow assessments accepted and enforcement approved 2026-09-08** | Monitor production enforcement and investigate any false pass or unexplained decision difference |
| Canonical security evidence | `canonical-security-evidence-implementation-plan.md` + `canonical-security-evidence.ux-spec.md` | CS-0-CS-6 complete; release authorized 2026-09-08 | Release v1.13.1 through protected `main` and verify the public artifact contract |
| Add-in assurance pilot | `add-in-assurance-implementation-plan.md` + `add-in-assurance.ux-spec.md` | Proposed; implementation not authorized; blocked by CS-6 | Review the plan only; do not implement without separate explicit operator approval |
| Evidence-guided handoffs pilot | `evidence-guided-handoffs-plan.md` + `evidence-guided-handoffs.ux-spec.md` + hypothesis tree | Proposed research program; planning complete; implementation and execution blocked by CS-6 | After CS-6, seek separate authorization for EH-0 contract/fixture freeze; do not add orchestration or enforcement |
| Assurance Record v1 | `assurance-record-plan.md` | P80-P83 delivered; authority limitations superseded by Assurance Integrity | Preserve compatibility while hardening the aggregate boundary |
| Trust remediation (2026-11-13 audit) | `trust-remediation-implementation-plan.md` + `trust-remediation.ux-spec.md` | Authorized 2026-11-14; D4 closed; TR-0 and TR-1 merged; TR-2 is in progress | Complete TR-2, then merge TR-3 and TR-4 in order. In TR-9 replace planning and agent-instruction `kgraph` references with advisory `fettle graph impact` (owner decision 2026-11-16) |
| Improvement program (audit) | `improvement-plan.md` | Items 1–6 done; 5 index done; 8 partial | Positioning motion capture (operator) |
| Work-item lifecycle integrity | [Implementation plan](work-item-lifecycle-integrity-plan.md) + [UX contract](work-item-lifecycle-integrity.ux-spec.md) | Proposed; planning only; by the [2026-11-14 sequencing decision](engagement/TODO.md#sequencing-decision-2026-11-14) it is delivered inside trust remediation TR-5, not as a separate program | When TR-5 starts, WP-WLI-0/WLI-1 freeze the schema and preserve historical P46 as the red fixture before any live migration |
| Disciplines: suite review, experience discipline, opt-in pack | `discipline-suite-review-plan.md` + `experience-discipline-vnext-plan.md` + `experience-discipline-vnext.ux-spec.md` + [inventory](discipline-inventory-2026-11-14.md) | Direction decided 2026-11-14; inventory complete; no skill, package, installer or host change authorized yet; sealed evaluation and advisory pilot deferred | Narrow update in the disciplines repository after TR-3 merges; opt-in pack in Fettle after TR-4 merges |
| M-NC1: first non-code milestone | [Scope, authority, stages, and decision gates](engagement/TODO.md#m-nc1-first-non-code-milestone-deferred) | Proposed; deferred, including discovery; no execution or spending authorized | After TR-5 merges, authorize capped discovery for source tables to one XLSX |
| Incident learning and improvement roster | `incident-learning-implementation-plan.md` + `incident-learning.ux-spec.md` + `incident-learning.ui-spec.md` | Proposed; planning only; no runtime implementation authorized | Not before TR-5 merges; needs its own authorization |
| D4 lessons: execution-evidence hardening | [Implementation plan](d4-lessons-implementation-plan.md) + [backlog item](backlog/d4-lessons-execution-evidence.md) | Proposed 2026-11-07; planning only; no implementation authorized | Review together with the mutation decisions D1 to D5 in trust remediation TR-8 |
| Formal verification conformance and internal assurance (P43 continuation) | [Implementation plan](formal-verification-conformance-plan.md) + [UX/BDD](formal-verification-conformance.ux-spec.md) + [CLI presentation](formal-verification-conformance.ui-spec.md) | Planning extension approved 2026-10-16; deferred; no implementation, execution or promotion authorized | After M-NC1's decision; needs its own authorization |
| Fettle Review | `fettle-review-implementation-plan.md` + `fettle-review.ux-spec.md` + `fettle-review.ui-spec.md` + hypothesis tree | Proposed; planning only; no implementation or baseline study authorized | Review WP-FR-0, then separately decide whether to authorize the WP-FR-1 comprehension baseline |
| Agent trajectory and ATIF inspection | `agent-trajectory-inspection-decision.md` | **NO_GO as a standalone program**; retained as research provenance | Reconsider only for a named diagnostic consumer that existing evidence or a smaller truthful manifest cannot serve |

## Standing rules

- Advisory-first: no gate enforces until its own graduation evidence lands.
- Fail-visible always; completion is criterion-typed evidence.
- Work is claimed through `fettle work` before edits (claim-before-work).
- Assurance Integrity is the only authorized new feature program until it
  graduates; maintenance and defect correction continue.

## November 16 integration review

See the [integration review](main-merge-review-20261116.md). The November 14
sequencing decision and trust-remediation ownership remain authoritative.
