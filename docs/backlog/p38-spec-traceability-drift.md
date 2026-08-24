---
fettle-work-item: true
id: p38-spec-traceability-drift
status: done
scope:
  - fettle/spec_model.py
  - fettle/semantic.py
  - fettle/verification.py
  - docs/
  - tests/
spec: change-integrity-implementation-plan
---

# P38 — Consolidated specification traceability and drift evidence

Enables: hypergraph P46 and state-consistency P60. Deps P33/P35 complete.

Consolidate every specification-to-artifact trace surface behind one
canonical query, and add drift evidence that detects when traced artifacts
change without the spec (or the spec changes without the artifact).

## Done when

- One canonical function returns spec→artifact links with deterministic
  identities; ad-hoc per-module tracing is retired or delegated.
- Editing a traced artifact without touching its spec produces drift
  evidence; editing the spec alone does too; both fail-visible.
- Regression tests cover link, no-link, drift-spec, and drift-artifact paths.

## Resolution

Delivered `fettle/trace_canonical.py` as the single canonical query:
stable-ID marker index (`<spec-id>/<scenario-id>`), marker validation,
executed-result binding (declaration = linked; only a pass verifies), and
drift evidence separating uncovered scenarios, unknown markers, orphan
tests, governed-without-review advisories, and executed coverage.
Filename inference in `trace_requirements.py` deprecated (default off,
report flags when enabled). Contract coverage in
`tests/test_trace_canonical.py` (8 tests); existing spec/semantic suites
green.
