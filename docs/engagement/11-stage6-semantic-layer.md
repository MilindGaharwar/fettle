# Stage 6 — Semantic Layer (Pillar 2, thin slice)

Inputs: 02 (pillar gap assessment), 03 (open question D3), 05 (Graphify
review — consume-optional lean), 08/10 (stable ID scheme + UAT evidence).

## 1. Position

Pillar 2's end state is a queryable shared memory across requirement → code →
test → defect. Stage 3–5 already built the ontology seed *as artifacts in
git*: spec IDs (`<spec-id>`, `<spec-id>/R<n>`, `<spec-id>/S<n>`), trace
markers in tests (`# traces: <spec-id>/S<n>`), work items (`spec:` link),
and UAT evidence (verdicts + operator attestations keyed by scenario ID).

Stage 6 therefore does **not** build a graph database. The repository is the
database (05, cross-cutting conclusion). What is missing is only *fusion and
a query surface*: nothing today can answer "show me everything attached to
`greeter/S1`" or "which requirements have no evidence at all?"

## 2. Design

New module `fettle/semantic.py` — a deterministic, stdlib-only link builder
computed on demand from the artifacts already in the working tree (no
persisted index; recompute is cheap and can never go stale).

**Nodes** (id → kind): spec, requirement, scenario, test file, work item,
uat-verdict, operator attestation.
**Edges** (directed, labeled): scenario —traces→ requirement; test —covers→
scenario; work-item —implements→ spec; verdict —observes→ scenario;
attestation —observes→ scenario.

Query surface (CLI, no new gate):

- `fettle links <id> [--json]` — the neighborhood of any known ID, plus the
  full evidence chain for scenarios (requirement ← scenario ← test/verdict/
  attestation). Unknown ID → exit 2 with the closest known IDs.
- `fettle links --orphans [--json]` — fusion lint: requirements with no
  scenario, scenarios with no test *and* no UAT evidence, work items whose
  `spec:` points nowhere. Exit 1 when orphans exist (report, not gate).

## 3. Graphify decision (D3 closed)

**Consume-optional, confirmed.** If `graphify-out/graph.json` exists, `fettle
links` enriches scenario nodes with the code files its scope globs touch as
reported by graphify's deterministic extraction; when absent, scope globs
alone are shown. Fettle never shells out to graphify, never requires it, and
degrades to identical behavior minus enrichment. No reimplementation of
code-KG extraction (05: "gate on graph facts rather than rebuild graph
infrastructure").

## 4. Slices

- **S6.1** — `fettle/semantic.py` (nodes/edges from specs, trace markers,
  work items, UAT reports in managed worktrees, attestations) + `fettle
  links <id>` / `--orphans`. Tests.
- **S6.2** — graphify consume-optional enrichment + docs (README, CHANGELOG,
  work note with decisions).

## 5. Deferrals

- Persistent store / MCP query server — only if recompute cost ever bites.
- Gating on graph facts (WP-155 semantic impact gate) — after the link model
  proves stable; graduation pattern per WP1 #7.
- Architecture/security KG fusion (import_graph, rules metadata) — later
  arc; the link builder's node/edge shape is designed to accept them.
