# Engagement Scratchpad (working memory — not polished)

## 2026-08-01 — Kickoff

Prior state (from repo notes): v1.2.0 released; package reorg done (fettle/ real
package, scripts symlink); 1150+ tests; guard chain commit=fast/push=full-suite;
policy remote (org policy extends); enterprise plan WP-133..153; AI-Native
Manifesto adopted (WP-154 BDD gate, WP-155 kgraph impact gate planned).

### Immediate observations to verify during read
- Fettle today is a *quality harness* (hooks + gates + scans), not an agent
  orchestrator. Pillars 4/5 likely mostly absent; Pillar 2 only via planned
  WP-155 kgraph. Pillar 3 partially planned (WP-154 BDD gate).
- Config surface: config.py DEFAULTS → config_schema.py (anti-drift test) →
  docs/fettle.schema.json → policy_layers merge (defaults→org→repo→env).
  WP4 builds on this; dependency graph between gates does NOT exist yet (verify).
- "No silent failures": check how tool_runner/dispatcher handle missing tools
  (semgrep absent, timeouts) — degrade silently or surface?
- Naming rule: keep legitimate "Claude Code" *product integration* references
  (hooks target that agent runtime); prohibition is on model/author attribution.
  → listed in open questions to confirm interpretation.

## 2026-08-01 — Decisions from Milind (Phase A review)

- D1: One product, two layers (harness = enforcement core; platform on top). AGREED.
- D2: Fail-posture — wants my recommendation on which gates fail closed. → proposed
  below in reply; pending confirmation.
- D3: Semantic layer — wants recommendation w/ pros+cons. → proposed: own ontology +
  SQLite store behind a backend interface; kgraph as optional source; final backend
  call after WP8 Graphify review.
- D4: UAT runners — MUST support headless claude, codex, gemini cli, antigravity,
  opencode + similar. → plan: outbound `fettle.runners` AgentRunner protocol
  mirroring the inbound fettle.agents pattern, conformance-fixture contract,
  capability matrix, claude adapter first.
- D5: Sequencing APPROVED as drafted (Stage 0 → … → WP3 at stage 5).
- D6: Prerit invite — Milind adds manually. CLOSED for me.

## 2026-08-01 — Phase A complete

Key verified findings (details in 01/02/03 docs):
- "No silent failures" broken in 3 places: dispatcher Aggregator collects
  errors/timings/budget-kills but finish() never emits them; command-surface
  scanners (security_review/threat_model/pr_review/deploy_gate) swallow tool
  failures with `pass`; trace/health_telemetry writers swallow OSError.
  → proposed Stage 0 hardening before anything agentic builds on trace.
- Pillar verdicts: P1 trace, P2 trace (Dev-Intel JSONL loop strongest), P3
  trace→partial (tdd_gate ordering only; WP-154 unbuilt), P4 ABSENT (only
  agent-launch primitive = evals_runner._claude_runner), P5 trace ([extends]).
- Config: 30 gate tables in schema, CONFIG.md documents ~7, NO dependency
  graph anywhere → WP4 must precede other WPs' config additions.
- Docs drift: WP-133 number collision, README "12 commands" vs 17 actual,
  2 competing worklog models, ~10 dead plan files with stale statuses.
- Sequencing proposal: 0 fail-visibility → 1 research (WP1/6/8) → 2 WP4 →
  3 spec format+WP2 → 4 WP7+WP5 → 5 WP3 UAT → 6 Pillar-2 layer → 7 WP9.

### Read plan
- Myself: README, ROADMAP, cli.py, dispatcher*.py, config*.py, event/finding/
  result, agents/, hooks/hooks.json, enterprise plan.
- Subagent 1: gates/checks/scans inventory (what, config keys, mode, maturity).
- Subagent 2: docs/plans corpus + commands/ + templates/ (planning state,
  contradictions, weakest areas).
- Subagent 3: test strategy (tests/, fettle/tests/, evals/) + silent-failure
  audit of tool_runner/dispatcher error paths.
