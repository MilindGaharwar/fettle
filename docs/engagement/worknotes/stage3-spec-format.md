# Work note — Stage 3: living spec format + WP2 seed

Commits: ea9a080 (S3.1), e1eb881 (S3.2), 69425d2 (S3.3), this commit (S3.4).
Design doc: 08-stage3-spec-format-and-wp2.md.

## What shipped

- **S3.1 — fettle/spec_model.py**: markdown spec format detected by the
  `fettle-spec` frontmatter key (never by filename). Frontmatter: `id`
  (kebab), `status` (draft|active|superseded), `scope` (glob list).
  Body grammar: `## Requirements` with `R<n>.` items; `## Scenarios` with
  `### S<n>. title (traces R<n>)` + Given/When/Then bullets. Stable IDs
  `<spec-id>/R<n>` and `<spec-id>/S<n>` seed the Stage 6 ontology.
  `fettle spec lint|list` CLI; every lint finding carries a concrete
  `fix` (WP1 backlog #4 — action-first findings).
- **S3.2 — scenario coverage**: `# traces: <spec-id>/S<n>` markers in
  test files (py + js/ts variants) map tests to scenarios. `fettle spec
  coverage [--json]` emits an evidence artifact (WP1 backlog #1):
  per-scenario covered/covered_by, coarse spec-level markers reported
  separately (NOT counted as coverage), unknown trace targets surfaced
  (never dropped), totals with coverage_percent.
- **S3.3 — [gates.bdd]**: off by default; advisory|enforce (WP4
  MODE_ENUMS). PostToolUse on Write/Edit: an edited file inside an
  *active* spec's scope must have every scenario of that spec traced by
  at least one test. Deterministic — checks the contract exists, never
  runs tests (the suite proves red/green, same stance as tdd_gate).

## Decisions

- **D-S3.1** Spec detection by frontmatter key, not filename — specs can
  live anywhere in docs/ without a naming convention.
- **D-S3.2** Whole-spec trace markers do not count as scenario coverage —
  evidence honesty over easy green.
- **D-S3.3** `fettle spec coverage` always exits 0 — it is a report, not
  a gate; enforcement lives in `[gates.bdd]`.
- **D-S3.4** bdd_gate is PostToolUse-only in this slice. Stop-event
  integration (whole-session sweep) deferred — deliberate, revisit when
  Stage 5 UAT defines session-end evidence requirements.
- **D-S3.5** Scope matching uses fnmatch (where `*` crosses slashes), so
  `src/checkout/**` governs any depth. Documented behavior, not accident.

## Verification

- 50 new tests (26 + 14 + 10) — module suites + config-schema anti-drift
  pin (MODE_ENUMS keys == `.mode` paths in DEFAULTS) all green.
- Fettle self-check on changed files: 1 pre-existing WARNING
  (fail-visible print in config.py, Stage 0 by design); no ERRORs.
- docs/fettle.schema.json regenerated; consistency guard chain passed on
  every commit; full suite runs on push.

## Follow-ups

- Stop-event bdd sweep (D-S3.4) — Stage 5.
- Spec IDs → semantic layer ontology — Stage 6.
- Advisory→gate graduation telemetry for [gates.bdd] (WP1 backlog #7).
