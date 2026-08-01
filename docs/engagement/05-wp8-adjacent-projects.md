# WP8 — Adjacent Projects Review: OpenHive, Graphify, Obsidian

Sources fetched 2026-08-01: aden-hive/hive README (v0.11.0, Apache-2.0,
~10.8k stars); Graphify-Labs/graphify README (v0.9.31, Apache-2.0, ~99.8k
stars, PyPI `graphifyy`); obsidianmd org page (15 repos).

## 1. OpenHive (aden-hive/hive) — execution harness

**What it is**: a production *agent harness* (their framing: "the bottleneck is
no longer the model but the harness"). Define a goal in plain English → a
coding agent compiles a graph-based execution DAG of SDK-wrapped worker
agents → a control plane monitors → on failure the system *evolves the graph*
and redeploys. Features: session isolation, checkpoint-based crash recovery,
budget enforcement (team/agent/workflow level, with throttles and automatic
model degradation), real-time observability, LiteLLM model-agnosticism, and
**human-in-the-loop intervention nodes with configurable timeouts and
escalation policies**.

**Position vs Fettle**: complementary, not competitive. Hive is the *execution*
harness (makes agents run); Fettle is the *quality* harness (makes what they
produce trustworthy). Hive generates and heals workflows; Fettle judges
artifacts and process discipline. The overlap is the audit/observability layer.

**Take for Fettle**:
- **Intervention-node pattern** (pause + timeout + escalation policy) is the
  concrete mechanism WP3's graceful-HITL requirement needs. Fettle's UAT
  runner should model human checkpoints as first-class nodes with explicit
  timeout/escalation semantics, not ad-hoc prompts.
- **Checkpoint recovery** for long-running UAT sessions: persist runner state
  so a crashed exploration resumes rather than restarts — same spirit as
  Fettle's fail-visible posture.
- **Budget enforcement hierarchy** (team → agent → workflow) is a richer model
  than Fettle's flat per-check budgets; relevant when WP4 builds the config
  dependency model.
- **Non-goal confirmed**: Fettle should not grow an orchestrator. Instead,
  expose checks via a runner-pluggable protocol (`fettle.runners`, Stage 4) so
  harnesses like Hive can consume Fettle gates as DAG nodes.

## 2. Graphify (Graphify-Labs/graphify) — semantic layer precedent

**What it is**: `/graphify .` maps a project (code + docs + PDFs + media) into
a queryable knowledge graph. Code is parsed **locally and deterministically
with tree-sitter AST — no LLM, no embeddings, no vector store**; docs/media get
a semantic LLM pass. Every edge carries a confidence tag: `EXTRACTED` (explicit
in source), `INFERRED` (resolved), `AMBIGUOUS`. Leiden community detection,
god-node ranking, `# NOTE:`/`# WHY:` comments and ADRs become first-class
nodes linked to code. Query surface: `query` / `path` / `explain` CLI, MCP
server, HTML viz. Benchmarked (LOCOMO recall@10 0.497 vs mem0 0.048).

**Directly validating for Fettle's non-negotiables**:
- **Knowledge versioned with code, same commit**: `graphify-out/` is *meant to
  be committed*; a git **merge driver union-merges `graph.json`** so two devs
  committing in parallel never hit conflict markers; post-commit hooks rebuild
  (AST-only, zero API cost); `manifest.json` uses relative paths so it's
  portable across checkouts. This is a shipped, popular implementation of
  Fettle's "specs/knowledge versioned with code" pillar — adopt the mechanics.
- **Fail-visible ethos**: `extract` *refuses to overwrite* a larger graph with
  a partial result after a crashed pass (`--allow-partial` to override) —
  the same "incomplete must not read as clean" posture as Stage 0.
- **Hook-nudge architecture**: PreToolUse hooks steer agents from grep to
  graph queries; "strict mode" blocks the first raw source read per session
  then reverts to nudging. Same dispatcher pattern as Fettle — a Fettle
  semantic-layer gate can reuse this exact shape.
- **Work memory**: `save-result` records Q&A outcomes
  (useful/dead_end/corrected); `reflect` aggregates them into `LESSONS.md` and
  a recency-weighted overlay tagging nodes preferred/tentative/contested, with
  "code changed — re-verify" staleness flags. A concrete design for Fettle's
  learn/lean-debt loop maturation.

**Take for Pillar 2 (Stage 6 semantic layer)**: prefer *integration over
reimplementation*. Graphify already provides the code-KG with confidence tags
and git-native versioning; Fettle's differentiator is *gating on* graph facts
(impact-aware review, boundary rules against the real import graph — Fettle
already has import_graph.py/boundary_scan.py as seeds). Decision to make at
Stage 6: consume graphify's `graph.json` as an optional substrate vs extend
Fettle's own extractors. Record as open question, leaning consume-optional.

## 3. Obsidian (obsidianmd) — knowledge substrate conventions

**What it is** (org survey): closed-core app, open ecosystem — `obsidian-api`
type definitions, `obsidian-releases` community plugin registry (~20k stars),
**`jsoncanvas`** (open file format for infinite-canvas data, MIT),
`obsidian-headless` (CLI sync client), eslint/stylelint packs that check
plugins against official developer guidelines.

**Take for Fettle**:
- **Plain markdown + wikilinks as the durable spec substrate** (Pillar 1):
  human-editable, git-mergeable, tool-agnostic; graphify already parses
  `[[wikilinks]]` into reference edges — the formats compose.
- **Open-format spec** precedent: jsoncanvas shows how publishing a tiny,
  versioned JSON format creates an ecosystem; relevant if Fettle publishes
  its trace/spec schemas for third-party runners.
- **Guideline-linting for extensions**: Obsidian ships eslint/stylelint packs
  encoding its reviewer guidelines — the same move as Fettle rule packs;
  validates packaging policy-as-lint for a plugin ecosystem.

## Cross-cutting conclusion

All three converge on the same load-bearing idea Fettle bet on: **the
repository is the database** — knowledge graphs, specs, lessons, and maps live
in git next to code, merged with code, versioned with code. Fettle's role in
that stack is the enforcement layer: it should (a) stay runner-pluggable
(Hive), (b) gate on graph facts rather than rebuild graph infrastructure
(Graphify), and (c) keep every artifact plain-text and mergeable (Obsidian).
