# Fettle Roadmap

This document tracks future direction. Shipped release history belongs in the
[changelog](../CHANGELOG.md); executed design plans remain in `docs/archive/`
and `docs/engagement/` as provenance.

## Current Baseline

The released package is v1.8.0. It includes the R1 evidence contract and the
graduated R2 canonical workspace/adapter substrate: explicit four-state
results, workspace-aware post-edit lint for Python, JavaScript/TypeScript, Go,
and Rust, and affected-workspace verification. See the [README](../README.md)
for current capabilities and operational boundaries.

## Priorities

| Status | Outcome | Graduation trigger |
|---|---|---|
| Current | Repair verification evidence integrity before adding more gates | Scanner/tool errors cannot become clean; mutation results cannot manufacture a score; every gate has a seeded-defect control and recorded override contract |
| Graduated | Canonical workspace and adapter substrate | Python, JS/TS, Go, and Rust pass dispatcher parity in mixed repositories |
| Next | Independent red/green evidence, expanded evals, traceability, and changed-module mutation | Evidence is reconstructed in CI, benchmark variance is measured, and PR critical path remains at or below 12 minutes |
| Later | Native web, enterprise adapters, advisory framework packs, semantic delta, MCP, and broader LSP | Each surface meets measured demand, latency, precision, and canonical-finding parity |

The authoritative activity sequence, dependencies, estimates, and demand gates
are maintained in the
[Fettle evolution implementation plan](fettle-evolution-implementation-plan.md).

## Formal Verification (TLA+)

Critical protocol subsystems are model-checked via TLA+ (see
[`specs/tla/`](../specs/tla/README.md) and the
[full specification document](tla-plus-formal-verification.md)):

| Spec | Verified properties | States |
|------|-------------------|--------|
| PolicyCapsule | Monotonic strictness, depth bound, tamper detection, fail-closed, plumbing isolation, no spurious block | 1.2K |
| WorkItemClaims | No duplicate active claim, unknown-scope conservative, claim-before-work, lock mutual exclusion | 1.36M |

Specs are CI-gated on changes to verified source files
(`.github/workflows/tla-verify.yml`).

## Deliberate Non-Goals

- No automatic promotion of machine-drafted rules. Humans approve policy
  changes.
- No persistent semantic database until repository-based, on-demand analysis
  proves too slow.
- No whole-system rewrite in Go or Rust without measured Python startup cost
  exceeding hook budgets. Optimize the hot path first.

## Decision Rules

- Trust before reach: correctness and visible failure precede new distribution.
- Evidence before enforcement: a gate graduates only after noise is measured.
- Repository artifacts remain portable and inspectable.
- Hooks improve the session; CI remains an independent assurance boundary.
