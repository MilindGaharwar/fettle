# Work notes — Stage 6: Semantic layer (Pillar 2, thin slice)

Design: docs/engagement/11-stage6-semantic-layer.md. Commits: 42922a5
(S6.1 link fusion + `fettle links`), S6.2 (graphify enrichment + docs).

## Decisions

- **D-S6.1 — No persisted index.** The graph is recomputed on demand from
  artifacts already versioned in git (specs, trace markers, work items,
  UAT reports, attestations). Recompute is cheap, can never go stale, and
  needs no merge driver. Revisit only if measured cost bites.
- **D-S6.2 — Query surface is a CLI, not a gate.** `fettle links` and
  `--orphans` are report-only (exit 1 on orphans for CI use). Gating on
  graph facts (WP-155 semantic impact gate) waits for the graduation
  pattern (WP1 #7) once the link model proves stable.
- **D-S6.3 — Graphify is consume-optional (open question D3 closed).**
  If `graphify-out/graph.json` exists, spec scope globs are matched
  against graphify's extracted file list to add `scopes` edges; absent or
  malformed input degrades silently to identical behavior. Fettle never
  requires, shells out to, or reimplements graphify (per 05: gate on
  graph facts, don't rebuild graph infrastructure).
- **D-S6.4 — Orphan rules encode the evidence chain**: a requirement
  needs a scenario; a scenario needs a test OR UAT evidence (verdict or
  attestation — operator evidence counts, per D-S5.7); a work item's
  `spec:` must resolve. Each orphan carries a concrete fix.
- **D-S6.5 — Unknown IDs are a usage error with suggestions** (exit 2 +
  closest known ids), consistent with the no-silent-failure posture.

## Deferrals

- Persistent store / MCP query server — only if recompute cost bites.
- Architecture/security KG fusion (import_graph modules, rule metadata as
  nodes) — the Graph node/edge shape accepts them when needed.
- WP-155 semantic impact gate — after link-model stability evidence.
