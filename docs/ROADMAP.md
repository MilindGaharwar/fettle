# Fettle Roadmap

This document tracks future direction. Shipped release history belongs in the
[changelog](../CHANGELOG.md); executed design plans remain in `docs/archive/`
and `docs/engagement/` as provenance.

## Current Baseline

v1.7.0 provides four-agent event normalization, advisory-first session gates,
unified layered policy resolution with provenance (org/team packs, digest-
pinned central policy, per-directory overrides), guided workflows installable
into every supported agent environment, central reporting, living-spec and
verification evidence, governed delegation primitives, quarantined rule
proposals, and reliable-session artifacts. The 2026-08 dual external audits
are fully remediated. See the [README](../README.md) for capabilities and
operational boundaries.

## Priorities

| Priority | Outcome | Graduation trigger |
|---|---|---|
| 1 | v1.8: canonical result, finding, and evidence contracts | Tool failures cannot appear clean; every non-pass result has a recovery action |
| 2 | v1.8: Python and TypeScript agent-ergonomics baseline | Repair, turns, recurrence, bytes, and indeterminate runs are recorded |
| 3 | v1.9: canonical workspace and adapter substrate | Python, JS/TS, Go, and Rust pass dispatcher parity in mixed repositories |
| 4 | v1.10–v1.12: native web, enterprise adapters, and advisory framework packs | Each stack passes clean, violation, error, routing, and behavioral-eval gates |
| 5 | v1.13+: semantic delta, MCP, and broader LSP | Each surface meets measured demand, latency, precision, and canonical-finding parity |

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
