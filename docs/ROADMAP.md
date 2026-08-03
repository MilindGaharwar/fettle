# Fettle Roadmap

This document tracks future direction. Shipped release history belongs in the
[changelog](../CHANGELOG.md); executed design plans remain in `docs/archive/`
and `docs/engagement/` as provenance.

## Current Baseline

v1.6.0 provides four-agent event normalization, advisory-first session gates,
central policy and reporting, living-spec and verification evidence, governed
delegation primitives, quarantined rule proposals, and reliable-session
artifacts. See the [README](../README.md) for capabilities and operational
boundaries.

## Priorities

| Priority | Outcome | Graduation trigger |
|---|---|---|
| 1 | Remediate audit findings in normalized hook enforcement, delegated-policy handling, MCP trust, and policy-resolution consistency | Regression coverage demonstrates identical intended decisions on every affected surface |
| 2 | Graduate selected advisory gates, including UAT/BDD/verify/CI | Field evidence shows acceptable false-positive and environment-error rates |
| 3 | Add evaluator-optimizer UAT retries with reconciler feedback | A representative UAT verdict corpus exists |
| 4 | Add a semantic impact gate for broken requirement-to-scenario-to-test chains | Link coverage is stable enough to block without routine false positives |
| 5 | Improve distribution: Homebrew, Windows, hosted documentation | Installation and integration tests cover each target |
| 6 | Harden editor support and expand beyond Python | LSP behavior matches documented CLI findings for each added language |

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
