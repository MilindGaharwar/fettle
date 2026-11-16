# Program Plan Index

> Reconciled 2026-11-16 against `461e73b` for documentation publication.
> Dated worklogs retain historical validation results; current audit disposition
> comes from the existing completion record, not older blocked-status prose.
> Proposed priorities are not execution, spending, installation or rollout approval.

Single entry point for Fettle's planning documents. The historical master
plan (`fettle-evolution-implementation-plan.md`) remains the canonical
decision record; per-program details live in the dedicated plans below.
Physical extraction of remaining sections is deferred to avoid link rot —
this index is the navigation layer.

The [current priority order](engagement/TODO.md#current-priority-order) is:
accepted hardening, lifecycle trust repair with the DS/ED checkpoint, then bounded
M-NC1 discovery/build/measurement, followed by evidence-led broader expansion.
The retained audit record records bounded acceptance; new execution still needs
its package approval and applicable current evidence. Code remains
the first proof and an ongoing regression control. The
[preserved commitments](engagement/TODO.md#preserved-coding-and-reliability-commitments)
retain every planned coding and reliability improvement; deferral is not removal.

| Program | Detailed plan | Status | Next actions |
|---|---|---|---|
| Application audit hardening (2026-09-18) | [Prioritized work packages](audit-hardening-implementation-plan.md) + [UX contract](audit-hardening.ux-spec.md) + [worklog](audit-hardening-worklog.md) | AH01-AH06 accepted under amended AH07; AH08 implemented at signed `072bd62` and exact-head push CI `39041471220` passed; full mutation qualification remains `CLOSED_NON_PASS` | Preserve candidate-specific evidence; reconsider broader mutation qualification at H5, or earlier only for a demonstrated critical gap or governing requirement; do not start AH09 without authorization |
| **Work-item lifecycle integrity** | [Implementation plan](work-item-lifecycle-integrity-plan.md) + [UX contract](work-item-lifecycle-integrity.ux-spec.md) | Proposed; planning only; no implementation or corpus migration authorized | After required audit-hardening acceptance, review WP-WLI-0/WLI-1; preserve historical P46 as the red fixture before any live migration |
| **Experience Discipline vNext** | [Implementation and evaluation plan](experience-discipline-vnext-plan.md) + [experience contract](experience-discipline-vnext.ux-spec.md) + [staged revisions](engagement/TODO.md#discipline-broadening-deferred-priority-sequence-2026-10-10) | Proposed; planning only; no skill, eval, package, installer, host, CI, or release change authorized | Post-hardening checkpoint preserves coding controls and resolves WLI-critical conflicts; scope isolated revisions to M-NC1, evaluate before broader revision or separately approved global rollout |
| **Incident learning** | [Implementation plan](incident-learning-implementation-plan.md) + [UX/BDD](incident-learning.ux-spec.md) + [CLI presentation](incident-learning.ui-spec.md) | Proposed; planning and scheduling only | Authorize manual evidence preservation separately; coordinate schema with WLI and retain privacy, pilot and rollout gates |
| **Discipline-suite review** | [Review and update plan](discipline-suite-review-plan.md) | Proposed; historical inventory retained, no active-skill changes | Rebind host/source identities at DS-0; reuse ED evaluation and installation gates |
| **M-NC1: first non-code milestone** | [Scope, authority, stages, and decision gates](engagement/TODO.md#m-nc1-first-non-code-milestone-deferred) | Proposed; P1-NC1; deferred, including discovery; no execution or spending authorized | After accepted hardening and WLI-4, authorize capped discovery for source tables to one XLSX; then one bounded milestone approval covers advisory build, freeze, independent measurement, and decision, including scoped skill/discipline candidates and coding controls |
| Evidence convergence | `fettle-evolution-implementation-plan.md` P66–P71 (inline) | P66–P69 complete; P70/P71 evidence-gated | Accumulate qualifying runs via required PR mutation gate |
| Mutation quality | `mutation-quality-implementation-plan.md` + playbook | Baseline complete; advisory graduation | P64 methodology automation; ratchet decision after qualifying runs |
| **D4 lessons: execution-evidence hardening** | [Implementation plan](d4-lessons-implementation-plan.md) + [backlog item](backlog/d4-lessons-execution-evidence.md) + [TODO P0-XE](engagement/TODO.md#current-priority-order) | Proposed 2026-11-07; planning only; historical main-freeze constraint retained, current D4 state not requalified; no implementation authorized | After D4 run 3 validates: XE-2 `tool_error` classification, XE-6 scope-widening notice, XE-3 timing-test pack, XE-5 container-job pack, XE-4 retained-output rule, XE-1 never-executed-workflow advisory, XE-7 playbook; all advisory, no pass-semantics change |
| **Formal verification conformance and internal assurance (P43 continuation)** | [Implementation plan](formal-verification-conformance-plan.md) + [package checklist](engagement/TODO.md#formal-assurance-continuation) + [UX/BDD](formal-verification-conformance.ux-spec.md) + [CLI presentation](formal-verification-conformance.ui-spec.md) | Planning extension approved 2026-10-16; P2-FM remains deferred; no implementation, execution or promotion authorized | After M-NC1's decision and accepted hardening/WLI-4, gate capsule conformance FM-0 through FM-5, then decide FM-6; proposed follow-ups cover completion obligations FM-7/FM-8, conservative evidence FM-9, authority flow FM-10 and per-claim qualification FM-11. Preserve P0-IL/DS/ED gates, parked models and separate P43 criteria; earlier scheduling needs explicit trust-critical reprioritization |
| Change integrity (hypergraph) | `change-integrity-implementation-plan.md` (+ architecture, UX spec) | P44-P47 complete; P48 contextual advisory implemented but not promoted; P41 successor satisfies the durable-ledger dependency | Preserve existing authority; redesign or separately authorize the P48 consumer path before P49 |
| Contextual impact analysis | `contextual-impact-implementation-plan.md` + UX spec + hypothesis tree | Experimental advisory implementation complete; implementation package CI-3/research CI-2 promotion falsified by 78.05% held-out required recall, 7/20 eligible cases, and inconclusive gain interval | Retain advisory-only behavior; any new ranking attempt requires a new hypothesis, separate approval, and a newly pre-frozen corpus |
| Runtime secret protection | `runtime-secret-protection-implementation-plan.md` + UX spec | Strict pre-tool boundary and truthful host capability reporting implemented and contract-tested | Verify each installed host separately; retain Codex/OpenCode output filtering as unsupported until transport evidence proves replacement capability |
| Quality gate remediation | `quality-gate-remediation-plan.md` | Complete; required scanner failures are fail-visible and the canonical scan is clean | Preserve scanner-status and rule-precision regression coverage |
| State consistency | `state-consistency-implementation-plan.md` (+ UX spec) | P53-P56 complete; P57-P61 package- or evidence-gated | Review and authorize the P57 web/UAT adapter package |
| Agentic UAT strengthening | `uat-strength-plan.md` + hypothesis tree | Controller integrity, browser audit and hard-interruption recovery verified; bounded native input-discovery study matched 12/12 cases; checkpoint review and full 3,466-test suite passed; P77 parity unproven | Verify checkpoint commits through fresh remote CI; structured native denial and general discovery remain open; no release or enforcement promotion |
| **Assurance Integrity** | `assurance-integrity-implementation-plan.md` + `assurance-integrity.ux-spec.md` | **Graduated; 20 shadow assessments accepted and enforcement approved 2026-09-08** | Monitor production enforcement and investigate any false pass or unexplained decision difference |
| Canonical security evidence | `canonical-security-evidence-implementation-plan.md` + `canonical-security-evidence.ux-spec.md` | CS-0-CS-6 complete; release authorized 2026-09-08 | Release v1.13.1 through protected `main` and verify the public artifact contract |
| Add-in assurance pilot | `add-in-assurance-implementation-plan.md` + `add-in-assurance.ux-spec.md` | Proposed; CS-6 prerequisite satisfied; implementation not authorized | Seek separate explicit operator approval before any pilot implementation |
| **Fettle Review** | `fettle-review-implementation-plan.md` + `fettle-review.ux-spec.md` + `fettle-review.ui-spec.md` + hypothesis tree | Proposed; planning only; no implementation or baseline study authorized | Review WP-FR-0, then separately decide whether to authorize the WP-FR-1 comprehension baseline |
| Agent trajectory and ATIF inspection | `agent-trajectory-inspection-decision.md` | **NO_GO as a standalone program**; retained as research provenance | Reconsider only for a named diagnostic consumer that existing evidence or a smaller truthful manifest cannot serve |
| Evidence-guided handoffs pilot | `evidence-guided-handoffs-plan.md` + `evidence-guided-handoffs.ux-spec.md` + hypothesis tree | Proposed research program; CS-6 prerequisite satisfied; implementation and execution not authorized | Seek separate authorization for EH-0 contract/fixture freeze; do not add orchestration or enforcement |
| Assurance Record v1 | `assurance-record-plan.md` | P80-P83 delivered; authority limitations superseded by Assurance Integrity | Preserve compatibility while hardening the aggregate boundary |
| Improvement program (audit) | `improvement-plan.md` | Items 1–6 done; 5 index done; 8 partial | Positioning motion capture (operator) |

## Standing rules

- Advisory-first: no gate enforces until its own graduation evidence lands.
- Fail-visible always; completion is criterion-typed evidence.
- Work is claimed through `fettle work` before edits (claim-before-work).
- P0 trust repair order is audit-hardening acceptance, then authorized lifecycle
  contract/fixture work, validator implementation, corpus reconciliation, and
  required boundary wiring. Feature pilots do not displace this sequence.
- Experience Discipline vNext is the next requested planning review after audit
  hardening, not implicit authorization to displace the lifecycle trust-repair
  sequence or change active host-global skills. Revise skills/disciplines at the
  relevant workflow's preparation, freeze, evaluation, and rollout checkpoints;
  keep code as the first proof, not a retired specialization. Whole-suite rollout
  and the full WLI-6 observation window are not automatic M-NC1 prerequisites.
- Assurance Integrity graduated on 2026-09-08. Every proposed feature program
  still requires explicit authorization; planning status alone never authorizes
  implementation. Existing package gates remain. M-NC1 proposes one bounded
  milestone approval after explicitly authorized, capped discovery; changes to
  authority, data, capabilities, budget, or exclusions require reapproval. It does
  not approve broader DS/ED installation, Review, Add-in, handoff, or host programs.
