# Stage 10 — WP-146 Compliance Evidence

Date: 2026-08 · Scope: enterprise plan WP-146 (compliance mapping) · Commit: see below

## What shipped

1. **Canonical mapping** — `fettle/compliance.py`. `ControlMapping(cwe, asvs, soc2)`
   for every bundled rule (23 across the three packs) plus the ruff S-codes the
   security review runs. CWE for ruff codes is *derived* from
   `security_review._CWE_MAP` — one source of truth, no duplicated labels.
   Empty string means honestly unmapped (e.g. `datetime-now-pipeline` has no
   defensible CWE; it carries only SOC 2 CC8.1 as a change-management gate).

2. **Mirrored YAML tags** — `metadata.compliance: {cwe, asvs, soc2}` added to
   each rule in `rules/llm-antipatterns.yml`, `go-antipatterns.yml`,
   `ts-antipatterns.yml`. The runtime never parses these (stdlib-only — no
   PyYAML in production); they exist so the rule files are self-describing for
   humans and external tooling.

3. **Sync pin** — `tests/test_compliance.py::TestMappingSync` parses the YAML
   (PyYAML is a dev dependency) and asserts bidirectional equality with
   `RULE_COMPLIANCE`. Adding a rule without tags, or tagging YAML without
   updating Python, fails the suite.

4. **Evidence report** — `fettle report --compliance [--json]`. Joins the
   mapping with `trace.get_recent_decisions`: per framework (CWE / OWASP ASVS
   v4 / SOC 2 CC) → per control → enforcing rules + findings + blocked counts
   in the window. Rules that fired but map to nothing are listed as
   *unmapped*, never dropped. Footer states the posture explicitly: "evidence
   of enforcement, not a certification."

## Design decisions

- **Mapping lives in Python, not YAML.** The runtime is stdlib-only;
  `evals_runner.py` is the only yaml importer and it's dev-side. Parsing rule
  packs at report time would add a runtime dependency for a static fact.
- **Block detection uses trace `status`** (`"blocked"`/`"block"`), matching
  `report.py`'s existing vocabulary — an earlier draft guessed a `decision`
  key that doesn't exist in the trace schema.
- **Conservative tagging.** SOC 2: CC7.1 = vulnerability identification,
  CC7.2 = anomaly/failure monitoring, CC8.1 = change management. Where a CWE
  would be a stretch, it's omitted rather than padded.

## Verification

- `tests/test_compliance.py` — 13 tests: sync pin (3), full_mapping (3),
  report computation incl. window filtering + unmapped surfacing (3), render
  smoke (1), CLI table/JSON/contract (3). Plus test_cli.py unaffected.
- Live smoke on this repo's real trace: 547 CWE-390 (swallowed-failure)
  findings in the last 30 days rendered correctly; JSON round-trips.

## Follow-ups

- WP-147 (supply chain: Sigstore, SBOM, provenance) and WP-148 (opt-in
  telemetry) are the remaining v1.3.x items — next stages.
- Custom org rules can't be tagged yet; a `[compliance]` overlay in
  .fettle.toml would let orgs map their own rule ids (deferred until asked).
