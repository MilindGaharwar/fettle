# Work note — Stage 1: Research WPs (WP1, WP6, WP8)

Status: complete (2026-08-01)

## What was done

Three research reviews, each from primary sources fetched live:

| WP | Doc | Sources |
|---|---|---|
| WP6 | 04-wp6-wayfinder-review.md | mattpocock/skills wayfinder SKILL.md (full text) |
| WP8 | 05-wp8-adjacent-projects.md | aden-hive/hive, Graphify-Labs/graphify, obsidianmd org |
| WP1 | 06-wp1-frontier-agent-readiness.md | 4 Anthropic engineering/docs posts |

## Key decisions recorded

- **D-S1.1** (WP6): adopt index-vs-store, claim-before-work, HITL/AFK typing,
  fog-of-war as WP5 design inputs; reject hard tracker dependency and
  enforced one-decision-per-session. Four candidate gate invariants tabled.
- **D-S1.2** (WP8): Fettle stays the *enforcement* layer — runner-pluggable
  (Hive), consume-graph-optional rather than rebuild (Graphify, open question
  for Stage 6), plain-text mergeable artifacts (Obsidian). OpenHive's
  intervention-node (timeout + escalation) pattern chosen as the WP3
  graceful-HITL mechanism.
- **D-S1.3** (WP1): readiness thesis = scaffolding shrinks, verification
  grows; 7-item backlog mapped to stages. Highest-leverage: agent-ergonomics
  eval suite for Fettle's own surface; evidence artifacts on passing gates.

## Rejected alternatives

- Summarizing secondary commentary instead of primary sources — rejected;
  every claim in the three docs traces to a fetched source.
- Turning research directly into implementation in the same increment —
  rejected per protocol; backlog items land in their owning stages.

## Verification

Docs-only increment; guard chain (scrub, fettle check, consistency tests)
ran on commit; pre-push full suite ran on push.
