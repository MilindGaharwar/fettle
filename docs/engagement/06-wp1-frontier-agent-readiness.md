# WP1 — Frontier-Agent Readiness Review

Sources (fetched 2026-08-01, all Anthropic engineering/docs):

1. *Building effective agents* (Dec 2024) — workflow/agent taxonomy, ACI.
2. *Writing effective tools for agents* (Sep 2025) — tool ergonomics, evals.
3. *Effective context engineering for AI agents* (Sep 2025) — attention
   budget, compaction, note-taking, sub-agents.
4. *Best practices* (code.claude.com/docs/en/best-practices, current) —
   verification loops, hooks-vs-instructions, parallel sessions, adversarial
   review.

## The readiness question

"Opus-5 readiness" is not about a model version; the sources converge on a
durable thesis: **as models get smarter, prescriptive scaffolding shrinks and
verification infrastructure grows**. ("Smarter models require less
prescriptive engineering… but treating context as a precious, finite resource
will remain central" — source 3; "give Claude a check it can run… it's the
difference between a session you watch and one you walk away from" — source
4.) Fettle is exactly the layer that grows. The audit below scores Fettle
against each principle.

## Principle-by-principle audit

### P1. Closed verification loops (source 4, core)

The escalation ladder in the docs — prompt-level check → goal condition →
**deterministic Stop-hook gate** → **fresh-context second opinion** — maps
directly onto Fettle: stop_quality_gate is the deterministic gate;
cross_review is the second opinion. *Gap*: Fettle's gates emit pass/fail but
the "show evidence, not assertions" norm is only partially met — findings
carry detail, but there is no first-class **evidence artifact** ("the command
run + what it returned") attached to a passing gate. WP2/WP3 should make
evidence a required output of every gate, not just failures.

### P2. Hooks for musts, instructions for shoulds (source 4)

"Unlike CLAUDE.md instructions which are advisory, hooks are deterministic."
Fettle already lives on the right side of this line. *Gap*: several Fettle
disciplines still ship only as command prompts (commands/*.md) — advisory.
The WP-by-WP question is which of those graduate to deterministic checks
(the WP6 doc's gate-invariant table is the pattern).

### P3. Context is the binding constraint (source 3)

Attention budget, context rot, "smallest set of high-signal tokens." Fettle's
outputs *are agent context* — every finding, report, and advisory competes
for the consuming agent's attention budget. *Gaps*:
- Findings/reports have no token-budget discipline: no concise/detailed
  response tiers (source 2 recommends a `response_format` enum), no
  truncation-with-steering.
- Fettle's error messages mostly meet the "actionable, not opaque" bar
  (Stage 0 strengthened this); keep it a review criterion.
- Structured note-taking (source 3) is precisely the worknotes/TODO
  discipline this engagement uses manually — WP5 should productize it.

### P4. Tools designed for agents, measured by evals (source 2)

"Build a few thoughtful tools targeting high-impact workflows"; namespace;
return semantic names not opaque ids; evaluate with realistic multi-step
tasks and held-out sets. *Gaps*:
- Fettle's evals/ scaffolding exists but there is no eval suite measuring
  *agent-facing ergonomics* of Fettle's own CLI/MCP surface (does an agent
  pick the right Fettle command? does it act correctly on a finding?).
  This is the highest-leverage WP1 backlog item: Fettle should eat the
  evaluation discipline it preaches.
- Finding output leans on file:line (good, semantic) but rule ids are
  cryptic; consider one-line "what to do" per finding as the primary field.

### P5. Simplicity ladder (source 1)

Workflows before agents; add autonomy only when it demonstrably improves
outcomes. Fettle's dispatcher is a predefined workflow (right choice), and
WP3's UAT runner should start as an **evaluator-optimizer workflow** (source
1's pattern: generator + evaluator loop with clear criteria) rather than a
free agent — autonomy earned via evals, not assumed.

### P6. Parallel sessions and adversarial review (source 4)

Worktrees for isolation; writer/reviewer split ("a fresh context improves
code review since Claude won't be biased toward code it just wrote");
adversarial diff-vs-plan review as a subagent; the warning that reviewers
prompted to find gaps will always find some — scope them to correctness.
Direct inputs to WP7 (worktrees spine) and cross_review tuning: Fettle's
review prompts should explicitly bound findings to correctness/requirements
to avoid over-engineering churn (matches Fettle's lean-debt stance).

### P7. Fan-out automation (source 4)

`claude -p` loops with `--allowedTools` scoping = the pattern Fettle's CI
and fan-out consumers use. *Gap*: Fettle output formats should stay
machine-first (JSON) with stable schemas — feeds the WP4 config/schema work
and the runners protocol (Stage 4).

## WP1 backlog (feeds later stages; not committed work)

| # | Item | Stage |
|---|---|---|
| 1 | Evidence artifact attached to every gate result (pass and fail) | 3 (WP2) |
| 2 | Agent-ergonomics eval suite for Fettle's own CLI/MCP surface | 3–4 |
| 3 | concise/detailed tiers + token budgets for findings/report output | 4 |
| 4 | "What to do" as the primary field of a finding | 3 |
| 5 | UAT runner as evaluator-optimizer workflow first, agent later | 5 (WP3) |
| 6 | Correctness-scoped adversarial review prompts in cross_review | 5 |
| 7 | Graduate advisory command disciplines to deterministic gates where invariants are checkable | per-WP |
