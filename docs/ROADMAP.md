# Fettle Roadmap

This document tracks future direction. Shipped release history belongs in the
[changelog](../CHANGELOG.md); executed design plans remain in `docs/archive/`
and `docs/engagement/` as provenance.

## Current Baseline

The released package remains v1.7.0. The current mainline additionally has R1
evidence-contract work and the graduated R2 canonical workspace/adapter
substrate described in the [unreleased changelog](../CHANGELOG.md): explicit four-state results,
workspace-aware post-edit lint for Python, JavaScript/TypeScript, Go, and Rust,
and affected-workspace verification. See the [README](../README.md) for current
capabilities and operational boundaries.

## Priorities

| Status | Outcome | Graduation trigger |
|---|---|---|
| Current | Complete R1 evidence and agent-ergonomics graduation | Every gate emits a canonical state; Python and TypeScript baselines are recorded; every non-pass path has a recovery action |
| Graduated | Canonical workspace and adapter substrate | Python, JS/TS, Go, and Rust pass dispatcher parity in mixed repositories |
| Next | Native web, enterprise adapters, and advisory framework packs | Each stack passes clean, violation, error, routing, and behavioral-eval gates |
| Later | Semantic delta, MCP, and broader LSP | Each surface meets measured demand, latency, precision, and canonical-finding parity |

The authoritative activity sequence, dependencies, estimates, and demand gates
are maintained in the
[Fettle evolution implementation plan](fettle-evolution-implementation-plan.md).

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
