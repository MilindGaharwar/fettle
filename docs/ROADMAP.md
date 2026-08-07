# Fettle Roadmap

This document tracks future direction. Shipped release history belongs in the
[changelog](../CHANGELOG.md); executed design plans remain in `docs/archive/`
and `docs/engagement/` as provenance.

## Current Baseline

The released package is v1.9.0. It includes the R1 evidence contract, the
graduated R2 canonical workspace/adapter substrate, scanner and CI result
integrity, and deterministic change-integrity contracts. Mutation evidence,
narrow formal verification, and authorship separation are shipped in advisory
or partial form and remain subject to the graduation triggers below. See the
[README](../README.md) for current capabilities and operational boundaries.

## Priorities

| Status | Outcome | Graduation trigger |
|---|---|---|
| Graduated | Scanner and CI result integrity (P33) | Required scanner failures are canonical non-pass outcomes and cannot become clean CI results |
| Graduated | Canonical workspace and adapter substrate | Python, JS/TS, Go, and Rust pass dispatcher parity in mixed repositories |
| Graduated | Change-integrity contracts and adversarial corpus (P44) | Immutable source, graph, provider, traversal, freshness, closure, and obligation records have deterministic identities and executable adversarial fixtures |
| In progress | Mutation evidence integrity (P34) | Changed and full advisory lanes retain trustworthy evidence across three stable CI runs before a baseline is established |
| In progress | Narrow formal verification (P43) | Policy Capsule and Work Item Claims are model-checked; Verify Gate, Dispatcher, and TDD Gate models plus implementation refinement evidence remain |
| In progress | Authorship separation (P52) | Role-based edit enforcement is implemented; TLA+ role invariants, adversarial path coverage, and an evidenced multi-agent flow remain before graduation |
| Next | Seeded-defect controls, independent red/green evidence, expanded evals, and traceability | Evidence is reconstructed in CI, benchmark variance is measured, and PR critical path remains at or below 12 minutes |
| Proposed | Runtime change-integrity snapshots, ephemeral graph, and advisory impact (P45-P48) | Immutable source snapshots, explicit provider completeness, deterministic graph digests, actionable impact output, and shadow parity exist without changing current authority |
| Evidence-gated | Graph-bound CI, strict claim footprints, and optional persistence | P33/P35/P41 prerequisites pass; exact merge-candidate evidence and claim concurrency are proven; persistence is added only after measured recomputation cost justifies it |
| Later | Native web, enterprise adapters, advisory framework packs, semantic delta, MCP, and broader LSP | Each surface meets measured demand, latency, precision, and canonical-finding parity |

The authoritative activity sequence, dependencies, estimates, and demand gates
are maintained in the
[Fettle evolution implementation plan](fettle-evolution-implementation-plan.md).
The proposed hypergraph program is detailed in the
[change integrity architecture](change-integrity-architecture.md),
[UX specification](change-integrity.ux-spec.md), and
[implementation plan](change-integrity-implementation-plan.md). Runtime work is
not authorized by those planning documents.

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
- Hooks improve the session; CI remains an independent assurance boundary.
