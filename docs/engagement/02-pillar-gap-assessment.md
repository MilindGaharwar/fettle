# Deliverable 2 — Pillar-by-Pillar Gap Assessment

Scoring: **absent** / **trace** (an ingredient exists) / **partial** / **substantial** / **complete**.
Every claim cites files. Companion to [01-orientation.md](01-orientation.md).

---

## Pillar 1 — Living specifications replace static documents

**Verdict: trace.** Fettle has spec-*discipline* scaffolding, zero spec *semantics*.

What exists:
- Plan lifecycle: `*plan*.md` freshness gate ([fettle/quality_gate.py](../../fettle/quality_gate.py)
  `scan_planning`), activate/complete stamping (commands/plan-activate.md,
  `.fettle/state/active-plan.json`), structural plan linting
  ([fettle/plan_validator.py](../../fettle/plan_validator.py): WP tables must declare
  TDD/INTEGRATION/REGRESSION/LIVE rows).
- Spec-change coupling: [fettle/spec_audit.py](../../fettle/spec_audit.py) — a changed
  spec/strategy doc requires an updated `docs/spec-audit.md` (heading presence only).
- UX-spec existence: [fettle/ux_spec_gate.py](../../fettle/ux_spec_gate.py) — *any*
  `*.ux-spec.md` anywhere unlocks all frontend edits.
- Doc freshness: `[gates.docs]` soft check.

Gaps to close:
- No spec **format/ontology**: nothing parses spec content into requirements,
  acceptance criteria, or scope. Checks are existence/mtime/filename/heading.
- No **binding** between a specific spec and the files/tests it governs
  (closest: `# traces:` markers in [fettle/trace_requirements.py](../../fettle/trace_requirements.py), report-only).
- No **same-commit co-evolution** enforcement of spec+code+knowledge (spec_audit
  is the seed of this but audits a separate audit-file, not the spec itself).
- Requires: an AI-ergonomic spec schema (structured markdown/frontmatter),
  a spec↔artifact link model, and gates that consume spec *content*. WP-154
  (BDD gate, planned) is the first real step and is unbuilt.

## Pillar 2 — Unified semantic layer as shared memory

**Verdict: trace.** Fettle has four *proto-graphs* in flat-file form, no fusion,
no ontology, no query surface.

| Target KG | Closest existing ingredient | Form |
|---|---|---|
| Architecture KG | [fettle/import_graph.py](../../fettle/import_graph.py) (import/contract resolution), [fettle/boundary_rules.py](../../fettle/boundary_rules.py) + `[gates.architecture_boundaries]`, [fettle/workspace.py](../../fettle/workspace.py) monorepo map | computed on the fly, discarded |
| Code KG | changed-function AST in [fettle/complexity_check.py](../../fettle/complexity_check.py); `changeset.py` | ephemeral |
| Security KG | rule metadata (CWE, citations) in rules/*.yml; [fettle/threat_model.py](../../fettle/threat_model.py) STRIDE template; secret/boundary scans | YAML/markdown, unlinked |
| Dev-Intelligence KG | **strongest**: trace JSONL v2 ([fettle/trace.py](../../fettle/trace.py)), ratchet TP/FP evidence, bench budgets, suppressions ledger, [fettle/report.py](../../fettle/report.py) org rollup | JSONL/JSON, queryable only via bespoke CLIs |

Gaps to close: shared ontology + ID scheme (requirement/code-element/test/defect
entities), persistence + query layer, cross-domain traversal (requirement→code→
test→defect — exactly the planned WP-155 "kgraph semantic impact gate",
[docs/fettle-enterprise-product-plan.md](../fettle-enterprise-product-plan.md), unbuilt),
and write-back so agents update the layer in the same commit (Pillar 1 coupling).
Decision needed: build vs integrate the external `kgraph` tool the plans allude to.

## Pillar 3 — Tests generated from specifications, before code

**Verdict: trace→partial.** Ordering discipline exists; derivation does not.

What exists:
- [fettle/tdd_gate.py](../../fettle/tdd_gate.py) — enforces *test-edited-before-
  implementation ordering* only (self-admittedly not red/green, not spec-derived).
- [fettle/trace_requirements.py](../../fettle/trace_requirements.py) — spec↔test link
  report via naming convention + `# traces:` markers; never gated.
- [fettle/coverage_gate.py](../../fettle/coverage_gate.py) — diff line+branch coverage
  (validates implementation, not specification).
- WP-154 BDD gate is **planned, unbuilt**: `[gates.bdd]` requiring Given–When–Then
  scenarios in the active spec, linked to tests via trace_requirements.

Gaps to close: G-W-T scenario format inside specs; test *generation* from
scenarios (nothing generates anything today); scenario-explosion management
(dedup, equivalence-class pruning, risk-based selection — no plan covers this);
black-box acceptance runner (WP3 UAT is the natural executor); contract-before-
code lock-in (spec freeze + hash, so tests bind to a versioned spec).

## Pillar 4 — Supervised team of specialist agents

**Verdict: absent** (deliberately, so far). Fettle is reactive by design.

What exists (the full list):
- Payload normalization, not execution: [fettle/agents/](../../fettle/agents/).
- Context injection into *host-spawned* subagents: [hooks/subagent_inject.js](../../hooks/subagent_inject.js).
- One agent-launch primitive: `_claude_runner` in [fettle/evals_runner.py](../../fettle/evals_runner.py).
- LLM-as-worker calls: [fettle/cross_review.py](../../fettle/cross_review.py), [fettle/learn.py](../../fettle/learn.py).

Nothing for: personas (zero mentions in the entire docs corpus), supervisor/
delegation, bounded contexts with session resets, skills as first-class
capability units, agent↔MCP wiring, or traceability of an action to a persona.
Closing this is green-field: a persona/agent/skill model, a supervisor loop, an
execution environment (WP7 worktrees are the natural isolation substrate), and
audit binding (trace schema already has the right append-only shape to extend).
**This is the largest single gap and the pivot from "harness" to "platform".**

## Pillar 5 — Reusable blueprints and concurrent workstreams

**Verdict: trace.** Reuse machinery exists for *policy and rules* only.

What exists:
- Org policy distribution: digest-pinned `[extends]`
  ([fettle/policy_remote.py](../../fettle/policy_remote.py)) with local override —
  a genuine blueprint mechanism for one artifact type (config).
- Rule reuse: `rules/learned/` promotion via ratchet; planned WP-150 marketplace
  (`fettle rules add <source>`, signed packs) — unbuilt.
- Templates: [templates/](../../templates/) (CI configs, checklists) — copy-paste, unversioned.

Gaps to close: blueprint *content types* beyond config/rules (personas, spec
templates, skills, KG schemas — all depend on Pillars 1/2/4 existing first);
publish/adopt/adapt lifecycle with versioning; and the concurrent-workstream
lifecycle model (today's gates assume a single developer+agent session; no
notion of parallel security/architecture/verification workstreams engaging
simultaneously). Concurrency support depends heavily on WP7 (worktrees).

---

## Summary matrix

| Pillar | Status | Strongest existing asset | First missing keystone |
|---|---|---|---|
| 1 Living specs | trace | spec_audit + plan lifecycle | spec content schema + binding model |
| 2 Semantic layer | trace | trace/ratchet evidence loop (Dev-Intel proto-KG) | ontology + persistent queryable store |
| 3 Spec-first tests | trace→partial | tdd_gate + trace_requirements | WP-154 BDD gate + generation |
| 4 Agent team | absent | evals_runner's agent-launch primitive | persona/agent/skill model + supervisor |
| 5 Blueprints/concurrency | trace | `[extends]` org policy | generalized blueprint packaging; worktree-based concurrency |

Cross-cutting observation: the pillars are not independent. 1→3 (tests derive
from spec content), 1+2→4 (agents need specs and shared memory to be scoped),
4+7→5 (concurrency needs isolation). Sequencing must respect this; see
[03-open-questions-and-sequencing.md](03-open-questions-and-sequencing.md).
