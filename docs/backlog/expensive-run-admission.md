---
fettle-work-item: v2
id: expensive-run-admission
status: open
scope:
  - docs/backlog/expensive-run-admission.md
  - docs/engagement/TODO.md
  - .github/workflows/mutation-pr.yml
  - fettle/mutation_test.py
spec: mutation-quality-playbook
---

# Expensive-run admission: gate job and digest-bound result reuse

Recorded 2026-10-25 after three consecutive commit-bound mutation advisory runs
(~12 h each) were lost in three days to defects that were each reproducible
offline in minutes: a shard 2 s over a deadline projected from local timings
(run 39798005789), an aggregator flag never exercised on real reports
(39946934259), and a test dependency present locally but absent in CI
(40050518426 / CI 40050515114). The preventing rule existed as prose in TODO
H2/H3 ("cheapest discriminating check before expensive qualification") and was
not a mechanism. Fettle's own thesis is that prose does not bind agents;
mechanisms do. This item makes it one, for Fettle and for every repository that
adopts Fettle's mutation workflows.

## Priority

First infrastructure change on `main` after the audit-hardening merge, before
any D4 full-scope run. Not part of PR #46.

## Package 1 — Gate job before fan-out (workflow + fixture)

- Add a job the 256-shard matrix `needs:`. In the same runner image and with the
  same dependency installation as the shards, it runs the real path end to end
  on a two-shard fixture corpus: prepare manifests → shard command → advisory
  aggregate → publication step. Expected: `passed: true` on the fixture;
  non-pass on one removed report; non-pass on one altered manifest digest.
- Runs the full test suite in that environment, so a dependency present only in
  a developer's editable install fails here.
- Budget: under 10 minutes. Failure stops the fan-out; nothing else runs.
- Tests assert the `needs:` edge exists and that the gate uses the real entry
  points (no mocks of `aggregate_shards` or the shard command).

## Package 2 — Digest-bound reuse of unchanged shard results (engine + workflow)

- A shard report is reusable for a new head when, and only when, all of these
  are byte-identical between the retained run and the new head: the shard's
  manifest digest; the digest of every source file in the shard's ranges; the
  digest of every mapped test file for those ranges; the pinned mutation
  runtime (`requirements-mutation.txt` digest); and the policy digest.
- The advisory aggregate accepts a reused report only with its provenance
  (source run id, attempt, original revision) recorded, and marks the aggregate
  `reused_shards: [...]`. Missing or stale provenance is non-pass.
- A workflow or test-only change then costs minutes, not a full rerun. A change
  to any mutated source or mapped test re-executes exactly the affected shards.
- Not a qualification mechanism: `qualification_eligible: false` is retained;
  D4 "stable" runs must be full fresh executions by definition.

## Package 3 — Projection from observed data

- Pre-dispatch per-shard budget check uses the retained observed ledger from the
  target runner (engine seconds per shard, P95), never local timings. Any shard
  projected above 85% of the engine budget blocks dispatch with the shard,
  module, and s/mutant named.

## Acceptance

- A deliberately broken aggregator flag, a missing runtime dependency, and a
  mismatched manifest digest each fail the gate job within 10 minutes with no
  shard dispatched (three retained negative fixtures).
- A docs-only or workflow-only commit after a green run reuses all 256 shard
  reports and publishes `mutation evidence` from the aggregate in under 20
  minutes, with provenance recorded.
- A one-file source change re-executes only the shards whose manifest or mapped
  test digests changed.
- Missing, malformed, stale, or conflicting reuse provenance is non-pass.

## Boundary

No change to mutation scope, pass semantics (`passed = skipped == 0`), survivor
handling, or qualification evidence. Reuse is advisory-path only.
