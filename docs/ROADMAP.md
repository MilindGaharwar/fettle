# Fettle Roadmap

> Reconciled 2026-11-16 against `461e73b` for documentation publication.
> Dated worklogs retain historical validation results; current audit disposition
> comes from the existing completion record, not older blocked-status prose.
> Proposed priorities are not execution, spending, installation or rollout approval.

This document tracks future direction. Shipped release history belongs in the
[changelog](../CHANGELOG.md); executed design plans remain in `docs/archive/`
and `docs/engagement/` as provenance.

## Current Baseline

The current package version is v1.13.1. It includes the R1 evidence contract, the
graduated R2 canonical workspace/adapter substrate, scanner and CI result
integrity, deterministic change-integrity contracts, P62's reproducible
full-repository mutation calibration and accepted baseline, and wheel-native
versioned agent transports. The default installer includes every Python runtime
Fettle invokes, and assurance validates producer-bound canonical evidence before
persisting its own portable record. Runtime secret access is blocked pre-tool on
all four hosts; pre-model output protection is limited to Claude Code and Gemini.
Explicit contextual impact analysis is implemented but remains advisory after its
frozen promotion evaluation failed. Changed-scope
mutation policy and narrow formal verification remain advisory or partial and
subject to the graduation triggers below. See the
[README](../README.md) for current capabilities and operational boundaries.

## Priorities

Direction: reduce workslop across AI work by making readiness claims accountable
to evidence. Code remains the first domain and first proof, backed by the existing
coding investment and required verification gates; wider effectiveness is not yet
established. The [post-hardening sequence](engagement/TODO.md#post-hardening-strategic-sequence-2026-10-11)
puts accepted hardening and lifecycle trust repair first, then the bounded M-NC1
spreadsheet milestone, before optional platform/depth expansion. All new work,
including discovery and skill/discipline revision, waits for operator-confirmed
hardening acceptance and the applicable authorization. The retained audit record
now records bounded acceptance; mutation qualification remains CLOSED_NON_PASS.
The [preserved commitments](engagement/TODO.md#preserved-coding-and-reliability-commitments)
retain all planned coding and reliability improvements; only sequencing changes.

| Status | Outcome | Graduation trigger |
|---|---|---|
| Recorded bounded acceptance; WLI authorization pending | Audit hardening, then WLI lifecycle integrity | Candidate-bound hardening criteria and operator acceptance, followed by authorized WLI-0 through WLI-4 with contradiction fixtures and required boundary validation; a mutation run alone is insufficient |
| Proposed; staged with trust repair and M-NC1 | Skills and discipline generalization | Preserve coding controls at the post-hardening DS/ED checkpoint; revise demonstrated pilot needs, freeze isolated candidate versions, evaluate coding and spreadsheet behavior, and approve broader exact-version rollout separately |
| Proposed; P1-NC1; all stages deferred | [First non-code milestone: source tables to one XLSX](engagement/TODO.md#m-nc1-first-non-code-milestone-deferred) | After P0 and bounded approval, cap discovery at two weeks, build minimum advisory verification/receipt, freeze independent grading, and compare three arms across all tasks and total human effort; decide continue/revise/stop, not automatic enforcement |
| Graduated | Scanner and CI result integrity (P33) | Required scanner failures are canonical non-pass outcomes and cannot become clean CI results |
| Graduated | Canonical workspace and adapter substrate | Python, JS/TS, Go, and Rust pass dispatcher parity in mixed repositories |
| Graduated | Change-integrity contracts and adversarial corpus (P44) | Immutable source, graph, provider, traversal, freshness, closure, and obligation records have deterministic identities and executable adversarial fixtures |
| Enforced changed-scope gate; operational evidence ongoing | Mutation evidence integrity and quality ratchet (P34/P62-P65) | Independent full calibrations reproduce exactly, the committed 49.1 floor is established, and changed-scope survivors block merges; P65 continues measured operation per the [mutation quality plan](mutation-quality-implementation-plan.md) |
| Partial; planning extended 2026-10-16; execution deferred behind M-NC1's decision | Narrow formal verification and internal assurance (P2-FM/P43 continuation) | Qualify capsule model-to-implementation conformance first; separately gate completion obligations, conservative evidence aggregation and authority-flow checks, each with independent fault/UAT evidence. Existing Verify Gate, Dispatcher and TDD Gate models plus implementation refinement evidence remain open; the extension neither completes P43 nor changes existing acceptance authority |
| Graduated | Authorship separation (P52) | Role-based edit enforcement, TLA+ role invariants, adversarial path coverage, topology guidance, and an evidenced two-role flow are verified |
| Proposed, priority | First-class portable evidence (P66-P71) | Consequential results bind producer, source, policy, scope, completeness, freshness, and occurrence; producers graduate independently with measured cost per verified change |
| Retained coding controls; additional expansion separately gated | Seeded-defect controls, independent red/green evidence, expanded evals, and traceability | Evidence is reconstructed in CI, benchmark variance is measured, and PR critical path remains at or below 12 minutes |
| Execution kernel complete; later surfaces gated | State consistency contracts (P53-P61) | P53-P55 and P56a exact/normalized immediate/eventual evaluation are complete; snapshot/monotonic evaluation remains proposed; web/UAT, stateful sequences, evidence binding, and graduation remain independently gated without treating tool failure or intentional snapshots as defects |
| Advisory implementation complete; promotion blocked | Runtime change-integrity snapshots, ephemeral graph, impact, shadow, and contextual ranking (P45-P48) | Contextual ranking remains explicit after 78.05% held-out required recall, 7/20 eligible cases, and inconclusive paired gain; any replacement experiment needs a new hypothesis and pre-frozen corpus |
| Implemented; installed verification remains local | Runtime secret boundary | Pre-tool blocking is contract-tested on all four hosts; Claude Code/Gemini output protection is supported, while Codex/OpenCode output filtering remains explicitly unsupported |
| Evidence-gated | Graph-bound CI, strict claim footprints, and optional persistence | P33/P35/P41 prerequisites pass; exact merge-candidate evidence and claim concurrency are proven; persistence is added only after measured recomputation cost justifies it |
| Report-only; parity evidence pending | Agentic UAT strengthening (P72-P77) | Artifact-bound scenarios, exploration, web capture, stateful restart probes, and independent judgment are implemented; the canonical ten-seed harness exists, but real human evidence and an agreed discovery threshold remain required before any enforcement or parity claim |
| Deferred behind M-NC1's decision; authorization required | Plain-English Fettle Review | After separate approval, a baseline and held-out study show non-engineers correctly classify at least 90% of changes with zero false-ready decisions using an evidence-linked assurance case; the full program is not required for M-NC1's minimal receipt |
| Deferred behind M-NC1's decision; authorization required | Evidence-guided handoff pilot | CS-6 is complete; after separate approval, 20 accepted matched pairs must show candidate-bound handoffs and preservation obligations improve verified completion or regression detection within frozen integrity and cost thresholds |
| Later; no second M-NC1 workflow | Research briefs, documents/slides, browser effects, remote artifacts, and physical core/pack split | Select each domain from measured need, revise its skills/disciplines and acceptance checks, and earn independent evidence; split packages only after a second workflow demonstrates reuse |
| Later | Native web, enterprise adapters, advisory framework packs, semantic delta, MCP, and broader LSP | Each surface meets measured demand, latency, precision, and canonical-finding parity |

The current scheduling and approval overlay lives in the
[engagement backlog](engagement/TODO.md#current-priority-order); the
[Fettle evolution implementation plan](fettle-evolution-implementation-plan.md)
retains historical decisions and package-specific dependencies and gates.
The proposed non-engineer review surface is defined in the
[Fettle Review plan](fettle-review-implementation-plan.md). It is a read-only
consumer of existing evidence and Assurance decisions; it is not authorized for
implementation and cannot create a second quality authority.
The hypergraph program and its remaining evidence gates are detailed in the
[change integrity architecture](change-integrity-architecture.md),
[UX specification](change-integrity.ux-spec.md), and
[implementation plan](change-integrity-implementation-plan.md). Contextual output
is explicit and advisory; no default rollout, enforcement, or Assurance authority
is authorized.

External code intelligence and memory remain advisory inputs. The completed
[`codebase-memory-mcp` evaluation](advisory-code-intelligence-evaluation.md)
found useful local retrieval but insufficient source/configuration identity and
completeness for provider or evidence authority. No agent integration is planned.

The state-divergence program is defined in the
[state consistency UX specification](state-consistency.ux-spec.md) and
[implementation plan](state-consistency-implementation-plan.md). It begins with
explicit contracts rather than inferred field-name relationships. P53-P56 are
complete; P57-P61 stay package- or evidence-gated. Scheduling does not itself
authorize implementation.

## Formal Verification (TLA+)

Two of five planned critical protocol subsystems are model-checked via TLA+ (see
[`specs/tla/`](../specs/tla/README.md) and the
[full specification document](tla-plus-formal-verification.md)):

| Spec | Verified properties | States |
|------|-------------------|--------|
| PolicyCapsule | Monotonic strictness, depth bound, tamper detection, fail-closed, plumbing isolation, no spurious block | 1.2K |
| WorkItemClaims | No duplicate active claim, unknown-scope conservative, claim-before-work, lock mutual exclusion | 1.36M |

Specs are CI-gated on changes to verified source files
(`.github/workflows/tla-verify.yml`), and the `tla_sync` hook advises developers
when modeled source changes. Verify Gate, Dispatcher, and TDD Gate models,
property/state-machine tests, and implementation refinement maps remain before
P43 can graduate.

The [extended implementation plan](formal-verification-conformance-plan.md) and
[P2-FM activity checklist](engagement/TODO.md#formal-assurance-continuation)
retain capsule conformance as the first bounded claim. After its decision gate,
proposed FM-7 through FM-11 cover completion obligations, conservative evidence
aggregation and information flow into authority. Existing WLI, domain evaluators
and Assurance retain their ownership; no new generic verifier or second decision
authority is planned. Each package needs separate approval after accepted
hardening/WLI-4 and M-NC1's decision. These follow-ups do not authorize the parked
models, qualify an unbounded proof, or become new prerequisites for P0/M-NC1.

## Deliberate Non-Goals

- No automatic promotion of machine-drafted rules. Humans approve policy
  changes.
- No persistent semantic database until repository-based, on-demand analysis
  proves too slow and the change-integrity persistence admission gate passes.
- No whole-system rewrite in Go or Rust without measured Python startup cost
  exceeding hook budgets. Optimize the hot path first.

## Decision Rules

- Trust before reach: correctness and visible failure precede new distribution.
- Evidence before enforcement: a gate graduates only after noise is measured.
- Repository artifacts remain portable and inspectable.
- Authority comes from explicit policy and independently valid evidence, never
  model confidence, inferred memory, or an unbound graph result.
- Optimize cost per independently verified outcome, with software changes as the
  first proof; count total human effort, false-ready outcomes, and abstention,
  not token reduction in isolation.
- Revise skills and disciplines alongside each workflow, preserving proven coding
  controls and keeping unsupported criteria unverified. Broader rollout needs
  behavioral evidence, explicit approval, and tested rollback.
- Hooks improve the session; CI remains an independent assurance boundary.
- Fettle may validate cross-role handoffs, but supported hosts remain responsible
  for scheduling and executing agents.
