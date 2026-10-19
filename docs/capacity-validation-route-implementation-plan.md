# Capacity Model-Validation Route Implementation Plan

Status: authorized by `AH-CAPACITY-ROUTE-20261015-B` on 2026-10-15.

Narrow repair authorized by `AH-UNTIMED-DIAGNOSTIC-20261018-A` on
2026-10-18. This repair does not renew or consume the separately reported
12,000-minute calibration allowance.

Related UX contract:
[capacity-validation-route.ux-spec.md](capacity-validation-route.ux-spec.md)

## User Story

As a maintainer, I want a candidate-bound, deterministic, non-authoritative
sample route so I can validate mutation cost predictions within explicit
provider limits without starting calibration or qualification.

## Assumptions

- `.github/workflows/mutation.yml` is registered and dispatchable from the
  integration branch.
- Canonical enumeration remains owned by mutation preflight functions.
- Selected fingerprint execution remains owned by
  `execute_pending_mutations`; no second engine is introduced.
- Provider job timeout is a containment control, not proof of instantaneous
  termination. Cancellation latency remains charged and disclosed.
- This change delivers a dormant route only. No provider run is authorized.

## 2026-10-18 Frozen Untimed Diagnostic Contract

- Historical comparison candidate:
  `9eef2fab60c504e26be176db123164bc46e593fe`.
- Historical runs: `31850858224` and `31865158733`, each with 514 retained
  artifacts. Their 28,723 distinct terminal checkpoint fingerprints have
  canonical digest
  `75807358bcaaed80efb2f0f3cd5ed99e9f573f2ded26c50e2c6281c851abe5b3`.
- Direct canonical matching against retained candidate `5d24a3bd...` gives
  27,718 fingerprints (digest
  `cc57b1f709083447884b31ac5f67d647d9fc15a73b2e84bda18d68e06e0aa1de`)
  in 154 files (file-list digest
  `c2c042b5c4fd497f1854c65faed5269e01e06b730d9cbdee16b8975dd3976957`).
  This exact reconstruction supersedes the earlier 27,850 scheduling estimate.
- An **untimed file** is a candidate file with no canonical fingerprint matched
  to either frozen historical run. Historical data remains modeling-only and
  incompatible with exact-head qualification.
- Ownership is the tuple `(manifest shard, file)`. A unit contains every
  manifest range for that file in that shard and every canonical corpus record
  carrying the same validated shard/file identity. Mutation-line containment is
  deliberately not an ownership rule. Every corpus fingerprint must be owned
  exactly once before selection.
- Candidate preparation sorts historically unmeasured file windows by mapped
  test count, mapped-test digest, file, and shard. It divides that fixed order
  into six deterministic equal-rank cost strata and selects the lowest and
  highest fingerprint-count unit in each stratum, with deterministic file/shard
  tie breaks. The resulting 12-unit plan and its SHA-256 are frozen before any
  execution. No substitution or rerun is allowed.
- The reported 10,800 runner-minute launch cutoff and 1,740-second worker window
  come only from `docs/calibration-budget-contract-amendment.md`. At most one
  compatible continuation yields two windows, or 3,480 seconds, per shard.
  They are comparison context, not renewed authority.
- For this diagnostic, **material reserve** means at least 20% of the reported
  10,800-minute launch cutoff: 2,160 runner-minutes. A favorable projection
  therefore must not exceed 8,640 runner-minutes and must fit every shard within
  two 1,740-second windows. The diagnostic cannot itself prove that projection;
  it can reject the model, support a separately reviewed next step, or remain
  inconclusive.
- Twelve purposively selected units cannot establish corpus-wide percentiles or
  affordability. Timeouts are censored evidence. Recurring file regeneration,
  setup, and mapped-test baseline costs are file-window costs and must not be
  multiplied again as per-fingerprint costs.

## Decision and Tradeoffs

Use one isolated `capacity-validation` mode with explicit `prepare`, `execute`,
and terminal `readback` stages in the registered workflow.

- Chosen over a standalone workflow because registration on a non-default
  branch is not guaranteed.
- Chosen over calibration mode because calibration artifacts and accounting are
  authoritative and use incompatible budgets.
- Chosen over parent-corpus reuse because canonical identity is revision-bound.
- Three dispatches add two operator steps but make enumeration cost, the frozen
  pre-measurement sample independently reviewable.

## Frozen Contracts

### Preparation

Inputs: mode, stage, exact candidate SHA, experiment ID, committed selection
policy digest. Outputs: full candidate manifests, complete canonical aggregate,
exactly 12 selected range units, plan digest, environment/test-mapping identity,
predictions, rationale, and coverage limitations.

### Execution

Inputs: exact candidate SHA, experiment ID, preparation run ID, and exact plan
SHA-256. Outputs use only `capacity-validation-*` schemas and artifact names.
They always declare `qualification_eligible=false`, `billing_authority=false`,
and `authoritative_predecessor=false`.

### Deadlines and accounting

- Queue delay is outside the worker ledger until provider `started_at`.
- Worker ledger begins at provider job `started_at` and includes setup,
  execution, cleanup, and cancellation wind-down until terminal.
- Outer worker timeout: 20 minutes.
- Internal mutation deadline: 12 minutes, bounded by a 14-minute execution
  step, preserving nominal setup/cleanup headroom.
- Provider cancellation latency cannot be guaranteed exactly; accounting
  reserves the full 20 minutes per admitted worker and any indeterminate or
  contradictory provider timing is non-pass.
- Three batches contain four units each. Later batches require terminal prior
  workers, valid artifacts, restoration evidence, and remaining worker/support
  reserve.
- Worker, routine-support, and cancellation-controller ledgers never transfer
  authority or headroom.

## Blast Radius

- `fettle/mutation_test.py`: strict sample-plan, unit execution, and readback
  schemas; existing preflight/fingerprinting/execution owners are reused.
- `.github/workflows/mutation.yml`: one dormant explicit mode; generic jobs must
  exclude it; ordinary push/PR/schedule behavior remains unchanged.
- `tests/test_mutation_test.py`: contract, boundary, partial-write, and
  adversarial consumer tests.
- `tests/test_ci.py`: parsed workflow, actual scripts, concurrency, deadline,
  permission, dormant-mode, and artifact namespace tests.
- `docs/behavior-map.md` and mutation docs: extension ownership and operator
  contract.

`kgraph impact` identified `tests/test_ci.py`, `fettle/staged_preflight.py`, and
mutation manifest consumers as direct/high-risk dependents. Its index was stale
and result truncated, so repository search and full tests remain required.

## Work Packages and Verification

1. Add strict non-authoritative plan/result builders in
   `fettle/mutation_test.py`; verify focused unit tests.
2. Add deterministic six-group low/high selection with exact-once validation;
   verify reordered inputs produce byte-identical plans.
3. Add isolated unit execution using the existing executor and atomic external
   checkpoint serialization; verify partial writes, timeout censoring, and
   restoration evidence.
4. Add `prepare` and `execute` orchestration to
   `.github/workflows/mutation.yml`; verify parsed YAML and actual step scripts.
5. Add adversarial calibration/continuation rejection tests and prove ordinary
   modes are unchanged.
6. Run focused tests, full tests, Ruff, actionlint, compilation, whitespace,
   locked Fettle scan, and manual dispatch-condition inspection.
7. Obtain independent complete-diff review; only after `PASS`, create one signed
   commit, push normally, and observe literal-head CI without dispatching the
   experiment.

## Success Criteria

- Exactly 12 deterministic, distinct, nonempty range units across six mapped
  groups, low/high by canonical fingerprint count.
- Every selected fingerprint appears exactly once and belongs to its range.
- At most four concurrent workers; one workflow attempt; no automatic retries.
- Invalid inputs start zero workers and never broaden scope.
- Complete, partial, censored, missing, conflicting, and nonterminal states are
  retained and non-pass as applicable.
- Capacity evidence cannot parse as calibration checkpoint/report,
  representation inventory, continuation source, or qualification aggregate.
- Push/PR/schedule start zero capacity workers.
- Final review, quality gates, signed commit, push, and literal-head observation
  pass.

## Complete Provider Execution Request

This section is a request, not authority. `AH-CAPACITY-VALIDATION-20261015-A`
remains closed at zero spend and is neither reopened nor combined with this
request. No provider job may start until a new grant names the delivered commit
and approves every category below.

| Category | Requested ceiling | Basis |
|---|---:|---|
| Candidate-bound corpus preparation workers | 8,960 runner-minutes | 256 enumeration jobs × 35-minute hard limit |
| Corpus preparation support/publication | 25 runner-minutes | manifest preparation 10 + aggregation/sample freeze 15 |
| Twelve measurement workers | 240 runner-minutes | 12 × 20-minute end-to-end provider job limit |
| Measurement-run admission/publication support | 25 runner-minutes | execution admission 5 + two batch gates 5 each + in-run readback 10 |
| Terminal provider readback support | 10 runner-minutes | separate terminal readback dispatch; no transfer to measurement-run support |
| Cancellation controller exposure | 30 runner-minutes | separate non-transferable controller/readback reserve for bounded stop handling |
| **Total requested ceiling** | **9,290 runner-minutes** | No transfer, reset, or credit from historical or unused authority |

Because the terminal readback job cannot observe its own final provider timestamp,
its ledger conservatively charges the full independent 10-minute ceiling. It does
not infer or claim exact elapsed time for that job.

Requested authority: one `capacity-validation/prepare` dispatch followed, only
after its terminal artifact is independently read back and the exact plan-file
SHA-256 is approved, by one `capacity-validation/execute` dispatch and one
terminal `capacity-validation/readback` dispatch. Queue delay is recorded
separately. Each worker ledger starts at provider job `started_at`
and ends only at provider terminal time, including setup, execution, cleanup,
and cancellation wind-down. The 20-minute workflow timeout is a containment
request, not an exact termination guarantee; provider timestamps and cancellation
latency must be reconciled before any charge is considered determinate.

The requested sequence authorizes only corpus identity construction and the 12
frozen units. It excludes calibration, qualification, continuation, automatic
reruns, full-corpus mutation execution, host probes, acceptance, merge, tag, and
release. Any missing, partial, malformed, stale, conflicting, unavailable, or
indeterminate artifact or provider record is non-pass and cannot broaden scope.

## Superseding Bounded Authorization

`AH-CAPACITY-BOUNDED-20261016-A` supersedes the rejected request above for one
candidate-bound experiment after delivery gates pass. It does not reopen the
closed grant, provide historical spending credit, or authorize calibration.

Preparation uses sixteen fixed batches of sixteen shards. Before each batch,
complete provider pagination is accounted through the existing runner-time
owner. The gate charges completed elapsed work, reserves only the unelapsed
remainder for active or admitted-but-not-yet-observed workers, reserves the
entire next batch at 35 minutes per worker, and keeps support and uncertainty
categories fully reserved. The worker gate is:

`observed + active_remaining + not_yet_observed×35 + next_batch×35 <= 952`.

The non-transferable categories are 952 preparation workers, 168 preparation
support, 100 preparation cancellation/uncertainty, 240 measurement workers, 25
measurement support, 10 terminal readback, and 30 measurement cancellation
controllers: 1,525 runner-minutes total. Containment does not guarantee corpus
completion.

Under `AH-PREP-CONTAINMENT-20261019-C`, the preparation topology is narrowed to
14 fixed batches of 16 shards followed by four fixed batches of eight. Every
tail admission repeats stable provider collection and reserves the complete
35-minute limit for each of its eight workers; a passing earlier tail gate does
not imply a later gate will pass. The two added admission jobs do not expand
routine support authority: manifest preparation (10), 19 admission jobs (95),
and sample freeze (15) reserve 120 of the unchanged 168 minutes.

The sole preparation monitor and all its setup, provider polling, terminal-gate
artifact retrieval, evidence publication, applicable cancellation request, and
shutdown are owned by the unchanged 100-minute preparation
cancellation/uncertainty category. They do not consume routine support or the
30-minute measurement cancellation-controller category. Its internal observation
deadline is 70 minutes and job timeout is 90 minutes, leaving a 20-minute
configured envelope for an in-flight bounded provider call, terminal retrieval,
publication, applicable cancellation, and shutdown. These
configuration bounds do not establish a provider billing cap. Missing, delayed,
unreadable, stale, forged, or conflicting terminal decisions remain non-pass;
bounded retrieval exhaustion finalizes unavailable evidence and never authorizes
execution.

### Frozen Model Decision

Investment requires all 12 exact results, median absolute relative error to the
central prediction at most 0.35, at least 10 rates between the optimistic and
conservative assumptions, no stress-rate exceedance, at least five qualifying
concordant low/high pairs, zero material inversions, and all exact whole-worker
intervals at or below 960 seconds. A pair qualifies only when the high
fingerprint count is at least 1.5 times the low count and the central predicted
delta is at least 60 seconds. Concordance requires both a 1.2 duration ratio and
60-second delta. Two distinct qualifying inversions, each at most a 0.8 ratio
and at least a 60-second reverse delta, reject ranking.

Exact attributable whole-worker duration above 960 seconds rejects the proposed
range granularity. The 720-second execution deadline produces a timer-specific
right-censored observation; the 840-second step timeout is not an execution
duration; the 1,200-second worker timeout is containment, not success. Neither a
720-second nor an 840-second censor proves the 960-second target was exceeded.
Any case not meeting a frozen investment or rejection rule is inconclusive.

## Feature Manifest

The repository has no `FEATURES.md`; behavior ownership is recorded in
`docs/behavior-map.md` and the two route contracts above.
