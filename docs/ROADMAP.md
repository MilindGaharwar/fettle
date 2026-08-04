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
| 1 | Graduate selected advisory gates, including UAT/BDD/verify/CI | Field evidence shows acceptable false-positive and environment-error rates |
| 2 | Add evaluator-optimizer UAT retries with reconciler feedback | A representative UAT verdict corpus exists |
| 3 | Add a semantic impact gate for broken requirement-to-scenario-to-test chains | Link coverage is stable enough to block without routine false positives |
| 4 | Improve distribution: Homebrew, Windows, hosted documentation | Installation and integration tests cover each target |
| 5 | Harden editor support and expand beyond Python | LSP behavior matches documented CLI findings for each added language |

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
