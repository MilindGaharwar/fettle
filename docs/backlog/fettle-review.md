---
fettle-work-item: v2
id: fettle-review
status: open
scope:
  - docs/fettle-review.ux-spec.md
  - docs/fettle-review.ui-spec.md
  - docs/fettle-review-implementation-plan.md
  - docs/hypothesis-tree-fettle-review.md
  - docs/plan-index.md
  - docs/ROADMAP.md
  - docs/backlog/fettle-review.md
spec: fettle-review
---

# Fettle Review

## State

Planning only. No runtime, CLI, test, fixture, configuration, policy, HTML, or
Assurance implementation is authorized. WP-FR-1 and every later package require
a separate explicit operator decision.

## Acceptance Criteria

- The UX contract lets a non-engineer distinguish verified, failed, unknown, not
  applicable, and advisory claims for one exact candidate.
- The UI contract provides equivalent terminal and accessible local-HTML paths
  without a score or color-only meaning.
- The implementation plan reuses existing Fettle evidence and Assurance authority
  rather than introducing a parallel quality engine.
- The research protocol measures false-ready decisions, classification accuracy,
  time to highest risk, and recovery-action success on held-out changes.
- Generated explanations remain advisory and cannot alter Fettle decisions.
- Planning validation passes without production-code changes.

## Next Action

Review WP-FR-0 and decide whether to authorize the baseline comprehension study in
WP-FR-1. Do not begin implementation from this backlog entry.

## Verification

Run `uv run python -m fettle.plan_validator
docs/fettle-review-implementation-plan.md`, `uv run fettle config --validate`,
`uv run fettle completion validate`, documentation claims tests, and
`uv run fettle check --changed`.
