---
id: plan-uat-strength
---

# UAT Strength Plan — Agent Acceptance At Par With, Then Stronger Than, Human UAT

Status: shipped repository-local capabilities retained; P77 parity baseline and
enforcement graduation pending; further strengthening deferred until Assurance
Integrity graduates · Research basis: `docs/hypothesis-tree-uat.md` · Backlog:
`docs/backlog/uat-p7[2-7]-*.md` work items

## User story and job

As an operator shipping a product through Fettle, I want `fettle uat run`
to exercise the running product the way a skilled human acceptor does —
and to observe, remember, and account for coverage better than any human
can — so that SHIP decisions rest on acceptance evidence I did not have to
perform by hand and cannot refute.

The bar is deliberately two-sided: reach parity on human strengths
(exploration beyond scripts, skepticism, statefulness) and exceed humans on
their weak axes (observation reliability, memory, coverage accounting).

## Where we stand

Stage 5 agentic UAT already ships `doctor/run/report/manual/attest`, worktree
isolation, GWT-scenario persona prompts, transcript reconciliation, HITL
permission posture, and manual fallbacks. The active-specs-as-contract
design already answers the industry's dominant failure ("agents cannot
define correct"). The gaps versus human UAT are exploration breadth,
independent observation, statefulness, judgment depth, and — critically —
the absence of any instrument that could falsify a parity claim.

2026 external evidence (agentic-QA landscape; TestExplora; GBQA;
session-based exploratory practice) contributes three constraints the plan
must respect:

1. Agents pattern-match known failure modes and miss genuinely novel bugs —
   breadth must come from structured tours, not bigger prompts.
2. Confidently-wrong passes are worse than honest failures — verdicts must
   bind to artifacts, never self-report.
3. Autonomy is earned per rung (assistive → augmented → agentic); report-only
   stays until held-out measurement proves parity.

## Assumptions

- Active specs remain the sole definition of "correct"; candidate scenarios
  from exploration require operator attestation.
- The default v1.13.1 package includes the Playwright Python library. Browser
  binaries remain an explicit external installation; axe capture is driven by
  the target application or runner rather than silently assumed.
- Human sessions can be recorded once to seed the benchmark's human baseline.

## Tradeoffs considered

- **Smarter prompts vs more channels:** prompt-only improvement was rejected —
  it does not address confidently-wrong passes. Chosen: artifact-bound
  verification first (P72).
- **Auto-promote discovered scenarios vs attest-gate:** auto-promotion grows
  subtly-wrong suites (documented industry failure). Chosen: attestation gate,
  reusing the existing command.
- **Build benchmark first vs last:** first would stall visible capability
  behind harness work; last risks unfalsifiable claims in between. Chosen:
  capability phases P72–P76 with report-only posture, P77 as the gate that
  unblocks enforcement modes.

## Blast radius

`fettle/uat/*` session/reconcile cores, doctor probes, default-package
capability checks, new `docs/uat/` benchmark area. No change to spec discovery,
mutation, or completion gates except additive references. Existing
`test_uat_*` suites must stay green at every phase boundary.

## Milestones

| ID | Goal | Completion criteria (evidence-typed) | Depends on |
|---|---|---|---|
| P72 | Evidence hardening: screenshots + a11y-tree/DOM snapshots + HTTP logs retained per scenario step; reconciler verifies against artifacts | success: scenario verdict without artifact → `unknown`, regression-tested; error-path: tampered transcript exposed by artifacts | — |
| P73 | Beyond-spec charters (SBTM tours, personas, fuzzing) producing attestation-gated candidate scenarios + coverage accounting | success: charter run yields artifact-backed candidates, none auto-promoted; boundary: coverage accounting totals equal discovered-surface inventory | P72 |
| P74 | Web surface driver S5.5 with per-state axe-core capture feeding P72 channel | success: demo-app web session drives UI-only end-to-end; error-path: missing browser runtime → exit 2 + manual script | P72 |
| P75 | Statefulness: persistent profile, restart/interruption probes, realistic seeded data | success: restart-probe persistence verdict reconciles from artifacts; success: data diversity measured, not asserted | P72 |
| P76 | Judgment layer: independent evaluator pass over transcript+artifacts hunting wrong-reason passes; severity routing to attest | error-path: adversarial fixture flagged where primary reconciler accepted; contract: no finding resolves without artifact reference | P72 |
| P77 | Seeded-defect parity benchmark ("mutation testing for UX") over ≥10 seeds with recorded human baseline | success: metrics reproduce from canonical retained evidence; gate: zero false-verdicts and agreed discovery threshold unblocks enforcement mode | P73, P74, P75, P76 |

Estimates follow the house pattern of 3–8 days each; P77 is the largest.

P75 and P76 are implemented in report-only mode. P77 now has a packaged
ten-seed manifest and reproducible retained-evidence scorer exposed through
`fettle uat benchmark`; parity and enforcement graduation remain blocked until
all ten seeds have real human evidence and reviewers commit a discovery
threshold.

The repository contains duplicate historical work-item IDs for parts of
P72-P74 with inconsistent open/done metadata. Those records do not override the
capability status above and must be reconciled before any future UAT milestone
claims completion.

## Deferred Packaging Direction

No additional UAT implementation or enforcement is authorized while Assurance
Integrity is open. After it graduates, evaluate a separately versioned
first-party `finefettle-uat` distribution that owns runtime startup/readiness,
fixtures and fault controls, cleanup, incremental persistence, browser/model
probes, diagnostics, independent artifacts, and adaptive risk-guided
exploration. Core should consume its canonical evidence through the same strict
authority boundary as every other producer.

This is a packaging hypothesis, not a committed extraction. Validate external
consumer compatibility, installation UX, and ownership boundaries before
moving repository-local modules. Containers remain optional unless a concrete
isolation or reproducibility requirement justifies them.

## Sequencing and concurrency

P72 first — every later phase consumes its artifact contract. P73–P75 may
then proceed in any order, but they share session/reconcile cores: concurrent
execution is coordinated through distinct `fettle work` claims (one claim per
milestone; same-file edits serialize under claim-before-work). P76 builds on
the P72 artifact contract; P77 is last because its instrument needs
P73–P76 capabilities to be meaningful.

## Task decomposition contract

Each claimed item decomposes at execution time into tasks of one concern,
2–5 minutes each, naming exact file paths and a verification command, ordered
so the suite stays green after every task — per `discipline-planning`.

## Non-goals

- Replacing operator judgment: SHIP/REJECT stays human via attest/completion.
- Auto-repairing product code from UAT findings.
- Mobile/desktop-native surfaces (future plan if demand appears).
- Any enforcement mode before P77 publishes its baseline.
