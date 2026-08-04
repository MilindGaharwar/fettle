# Deliverable — Open Questions & Proposed Sequencing (Phase A output)

Status: awaiting decisions. Nothing below is implemented.

## A. Open questions (decisions I need from you)

### Strategic
1. **Scope of the pivot.** Fettle's shipped identity is a *reactive harness*
   ("Human in Control", fail-open, ≤400 ms budgets). The brief's target is an
   *agent platform* (supervisor, personas, UAT agents, semantic layer). Do you
   want (a) one product with two layers (harness remains the enforcement core;
   platform builds on it), or (b) the platform as a separate package/namespace
   that depends on the harness? My recommendation: (a) — the audit trail,
   config, and gate machinery are exactly the platform's enforcement substrate.
2. **Fail-open vs no-silent-failures.** Today the dispatcher is fail-open *and*
   partially silent (orientation §7.1). The non-negotiable is "no silent
   failures", not "fail-closed". I propose: keep fail-open for latency-budgeted
   hooks, but every failure/skip/budget-kill becomes a trace event + surfaced in
   `doctor`/`report`, and repeated failures escalate to a visible advisory.
   Confirm this interpretation.
3. **Semantic layer: build or integrate?** Plans reference an external `kgraph`
   tool (WP-155, your CLAUDE.md lists `kgraph impact`). Is kgraph yours, and
   should Fettle integrate it as the Pillar-2 backbone, or should Fettle grow
   its own graph store (my default: integrate if it's maintained; wrap behind an
   interface either way)?
4. **Model/runtime assumptions for agent execution.** WP3/Pillar-4 agents need a
   runner. Options: `claude -p` headless (already used by evals), OpenCode, or
   an abstraction over both. Headless `claude -p` runs on your subscription —
   acceptable for background UAT workloads (cost/rate limits)?
5. **Frontier readiness (WP1).** I will research prompting best practice for
   the current top frontier agent models. Confirm the deliverable should live
   in docs/ (it will name vendor models — product-integration naming, which
   is fine).
6. **Naming rule confirmation.** The attribution rule — I read this as: no
   tool-vendor authorship/attribution in docs, commits, or code comments.
   Legitimate *product integration* references (Claude Code hooks, `claude
   -p` runner, `~/.claude/plugins` paths) must stay or the docs would be
   wrong. Confirm.
7. **GitHub collaborator invite.** The API invites by *username*, not email.
   Please confirm Prerit's GitHub username (or I can send the invite if the
   email search resolves unambiguously — see admin note in the report).

### Design-level (can proceed on my judgment if you prefer)
8. **WP2/WP3 boundary.** I propose: WP2 = the discipline (spec-derived
   functional tests, fixtures, contract tests, flake quarantine, gates) for the
   *target repo's own* test suite; WP3 = the independent agentic UAT layer that
   *doesn't trust* that suite. Confirm the split.
9. **UAT trigger points** (WP3): my default = on plan-complete, on pre-push,
   and on-demand; not per-edit (too slow/expensive). Acceptable default?
10. **Worklog model conflict.** Shipped daily worklog vs the continuity plan's
    per-work-item model contradict each other. WP5 will propose one model;
    OK to deprecate the loser?
11. **Dead plan files.** ~10 executed/stale plan docs remain in docs/ with
    "ACTIVE/Pending" statuses. May I move them to docs/archive/ with a status
    header as part of WP9 hygiene?
12. **Budget for new dependencies.** Fettle is proudly stdlib-only at runtime.
    WP3 (browser automation — playwright), Pillar 2 (graph store), WP5 may need
    real dependencies. Rule: optional extras (`pip install finefettle[uat]`),
    never in the core install path?

## B. Proposed sequencing (draft — for agreement)

Rationale: dependencies flow spec → tests → UAT; config safety and
failure-visibility are prerequisites for everything agentic; research WPs are
cheap and front-loadable.

| Stage | Content | Depends on |
|---|---|---|
| 0 | **Failure-visibility hardening** (fix orientation §7.1–7.3: dispatcher error/budget trace events, scanner tool-error surfacing, telemetry write monitoring). Small, ships value immediately, satisfies non-negotiable #1 before anything new is built on trace. | — |
| 1 | **WP1** research + review (docs only) · **WP6** Wayfinder review · **WP8** adjacent projects. All research; parallelizable. | — |
| 2 | **WP4** config schema + dependency model + validation. Every later WP adds config; the dependency validator must exist *first* or WP9 consistency is unenforceable. | 0 |
| 3 | **Pillar 1 spec format** + **WP2** functional-testing architecture (incl. WP-154 BDD gate). Specs before tests-from-specs. | 2 |
| 4 | **WP7** worktrees (isolation substrate) + **WP5** coordination substrate (both are infrastructure for agents; WP5 decision informed by WP8's Obsidian review). | 2 |
| 5 | **WP3 agentic UAT** — the headline. Needs: spec format (reconcile findings against spec), worktrees (isolation), WP5 (work notes), failure-visibility (non-negotiable #6), WP4 (its config). Staged so a v0 (backend-only, naive-explorer, report-back) ships before browser UAT. | 0,2,3,4 |
| 6 | **Pillar 2 semantic layer** (fed by WP8 Graphify findings; WP-155). Can start earlier as a thin ontology + ID scheme inside stage 3's spec format. | 3 |
| 7 | **WP9** consistency pass + consolidated roadmap update. | all |

Note WP3 is "highest priority" in the brief but has the deepest dependency
chain. The staging above ships a useful UAT v0 at stage 5 without waiting for
Pillar 2; if you want UAT even earlier, stages 3–4 can be trimmed to just the
minimal spec-frontmatter + worktree-provisioning slices UAT needs.

## C. Risks flagged early

- **Latency-budget culture vs agentic workloads**: hooks live in a ≤600 ms
  world; UAT/agent supervision live in a minutes world. They need a separate
  execution plane (background daemon or CI-style runner), not the dispatcher.
- **Scenario explosion (Pillar 3)** has no owner in any existing plan.
- **Worktrees + monorepo workspace detection** (fettle/workspace.py) will
  interact; `.git`-file (vs dir) handling needs an audit.
- **finefettle PyPI name vs fettle repo name** complicates blueprint/marketplace
  naming later (WP-150).
