# UAT Strength Plan — Agent Acceptance At Par With, Then Stronger Than, Human UAT

Status: proposed (P72–P77) · Research basis: `docs/hypothesis-tree-uat.md` ·
Backlog: `docs/backlog/uat-p7[2-7]-*.md` work items

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
- Optional heavy dependencies (playwright, axe) stay behind the
  `finefettle[uat]` extra; core remains stdlib-only.
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

`fettle/uat/*` session/reconcile cores, doctor probes, optional-extra
packaging, new `docs/uat/` benchmark area. No change to spec discovery,
mutation, or completion gates except additive references. Existing
`test_uat_*` suites must stay green at every phase boundary.

## Milestones

| ID | Goal | Completion criteria (evidence-typed) | Depends on |
|---|---|---|---|
| P72 | Evidence hardening: screenshots + a11y-tree/DOM snapshots + HTTP logs retained per scenario step; reconciler verifies against artifacts | success: scenario verdict without artifact → `unknown`, regression-tested; error-path: tampered transcript exposed by artifacts | — |
| P73 | Beyond-spec charters (SBTM tours, personas, fuzzing) producing attestation-gated candidate scenarios + coverage accounting | success: charter run yields artifact-backed candidates, none auto-promoted; boundary: coverage accounting totals equal discovered-surface inventory | P72 |
| P74 | Web surface driver S5.5 (`finefettle[uat]`) with per-state axe-core capture feeding P72 channel | success: demo-app web session drives UI-only end-to-end; error-path: missing playwright → exit 2 + manual script | P72 |
| P75 | Statefulness: persistent profile, restart/interruption probes, realistic seeded data | success: restart-probe persistence verdict reconciles from artifacts; success: data diversity measured, not asserted | P72 |
| P76 | Judgment layer: independent evaluator pass over transcript+artifacts hunting wrong-reason passes; severity routing to attest | error-path: adversarial fixture flagged where primary reconciler accepted; contract: no finding resolves without artifact reference | P72 |
| P77 | Seeded-defect parity benchmark ("mutation testing for UX") over ≥10 seeds with recorded human baseline | success: metrics reproduce from canonical retained evidence; gate: zero false-verdicts and agreed discovery threshold unblocks enforcement mode | P73, P74, P75, P76 |

Estimates follow the house pattern of 3–8 days each; P77 is the largest.

## Task decomposition contract

Each claimed item decomposes at execution time into tasks of one concern,
2–5 minutes each, naming exact file paths and a verification command, ordered
so the suite stays green after every task — per `discipline-planning`.

## Non-goals

- Replacing operator judgment: SHIP/REJECT stays human via attest/completion.
- Auto-repairing product code from UAT findings.
- Mobile/desktop-native surfaces (future plan if demand appears).
- Any enforcement mode before P77 publishes its baseline.
