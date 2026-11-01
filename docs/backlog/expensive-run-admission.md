---
fettle-work-item: v2
id: expensive-run-admission
status: done
scope:
  - docs/backlog/expensive-run-admission.md
  - docs/engagement/TODO.md
  - .github/workflows/mutation-pr.yml
  - .github/scripts/mutation_reuse_download_guard.sh
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
- A commit that changes no `.py` under the configured mutation paths
  (docs-only or workflow-only) produces `not_applicable` with zero shards and
  publishes `mutation evidence` in under 20 minutes. This follows from
  `write_changed_partition_manifests`, which returns an empty manifest set when
  no configured mutation source changed. Evidence: PR #53 / run 41160480854
  (6m41s), plus the closure PR recorded below.
- A content-identical re-push (same tree, new head SHA) after a green run reuses
  all 256 shard reports with provenance and publishes `mutation evidence` from
  the aggregate in under 20 minutes. Evidence: the E3 probe recorded below.
- A one-file source change re-executes only the shards whose manifest or mapped
  test digests changed.
- Missing, malformed, stale, or conflicting reuse provenance is non-pass.

## Boundary

No change to mutation scope, pass semantics (`passed = skipped == 0`), survivor
handling, or qualification evidence. Reuse is advisory-path only. Rule 13:
when reuse candidates exist but none of their identity-bound artifacts download,
the advisory fails closed with `status: error`, `passed: false`, the candidate
run IDs, and exit 2. Full-matrix fallback applies only when the candidate list
is genuinely empty.

## Resolution

PR #56 delivered the chained-provenance repair, PR #57 supplied the
content-identical E3 provider proof, and PR #58 supplied and merged the final
zero-scope provider proof. The evidence root is
`qualification-248851d-20261022/p0-era-chained-reuse-20261031/`; each provider
run is retained separately as `run-<sha7>-<run_id>/` with an
`evidence-index.json` and SHA-256 manifest.

- **E0 — environment parity:** Python 3.12.13, pinned mutmut 2.5.1, and a
  non-editable package install completed all 219 test files. The retained
  output SHA-256 is
  `b9334399366cc4ed27db84849ba7a5717ba3d47a44bf454aeb5eec8c9a26d589`.
- **E1 — digest-bound source change:** against retained runs 40854281099 and
  41163582112, the exact selector reused 255 reports and re-executed only shard
  252 for `source_digests`. Every reused report retained original provenance to
  run 40854281099. The aggregate completed with `passed: true`.
- **E2 — fail-closed fixtures:** broken aggregator flag, missing runtime
  dependency, removed report, and mismatched manifest digest each exited 2.
- **E3a — offline content-identical projection:** the exact selector reused 255
  reports from run 41195355210 and dispatched only shard 170 for
  `source_digests`, matching the approved one-shard probe projection.
- **Repair provider proof:** run 41195355210 at source head `9e5b427` passed the
  admission gate, all 256 projected fresh shards, and the published aggregate.
  Actual reuse exactly matched the empty projection, and no report carried
  prohibited provenance. PR #56 was squash-merged as `001a190`; source and
  squash trees both equal `b76d74b33419b33ade25aabd7945f72ae60aae70`.
- **E3 — content-identical provider proof:** run 41284457898 at source head
  `6b3bd61` reused 255 reports, dispatched only shard 170, and published a
  passing aggregate. A commit-message-only amend produced head `18a8afd` with
  the same tree `e5ef5ec2e4a14f3228357110e5018a76af9a5305`; run 41289732689
  then reused all 256 reports with an empty matrix. Of those reports, 255 cite
  source run 41195355210 and shard 170 cites run 41284457898. The aggregate
  artifact digest is
  `sha256:dcffa9c459969556240380e9afa1eefa02c93211ea897adeac4abaf4f6cf6b8f`,
  and authoritative end-to-end wall time was 19m45s. PR #57 was squash-merged
  as `f128654`; source and squash trees both equal `e5ef5ec2e4a14f3228357110e5018a76af9a5305`.

The provider sequence was runs 41160480854, 41163582112, 41170984332,
41195355210, 41284457898, 41289732689, and closure run 41291993820. Retained
job intervals total 18,433.46 runner-minutes through closure. Run 41160480854
is the existing 2a proof:
`not_applicable`, zero reused or dispatched shards, published evidence, and
6m41s wall time. Closure run 41291993820 independently repeated that result at
head `620d121`: `not_applicable`, zero reused or dispatched shards, published
aggregate digest
`sha256:eff3f1316d837680399f0c0290c18b6bdc56fc7fccd53cc3c191b9d5668024c0`,
and 5m11s wall time. PR #58 was squash-merged as `af6969c`; source and squash
trees both equal `7de0d4bed26d69e0308b6fac6afbf8f154aaeda8`.

The repair protects the successful advisory supply; it does not make that
supply qualification evidence. No D4 run was dispatched while P0-ERA was open.
