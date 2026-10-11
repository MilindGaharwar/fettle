# Stage-2 successor repair contract

Status: **amended and authorized for bounded repair implementation and offline verification**  
Date: 2026-10-10  
Historical candidate: `8c31238d3a72af0ef1f85c5bee0aa49a3c565b88`  
Historical run attempt: `38041454291/1`

This document freezes the repair contract before executable edits. It does not authorize a
recovery, mutation execution, preflight, calibration, active-discipline change, commit, push,
stage 3, finalization, merge, release, or completion claim. The historical stage-2 result remains
non-pass. Historical evidence remains immutable and associated with its original chain.

## Governing amendment

Direction 1 was authorized on 2026-10-10 against the original contract digest
`6e1ead39248218d65b3f90c42c8a98b4992044b60bd02719919b32098f5fb042`.
The successful-run 35-minute wall-clock target is amended only for the calibration observer
lifecycle. Worker deadlines remain 35 minutes. Stage-2 topology remains 32 shards at maximum
parallelism 16. The full-chain ceiling remains 3,600 runner-minutes, with a 2,400-minute launch
cutoff and 1,200-minute cancellation reserve.

The amended stage-2 observer deadline is **91 minutes (5,460 seconds)**:

| Component | Allowance | Evidence and uncertainty |
|---|---:|---|
| Worker waves | 70 min | Exact structural bound: `ceil(32 / 16) × 35`. Worker job timeout is unchanged. |
| Scheduling/acquisition | 5 min | The incident's first wave acquired runners in seconds; later queue time was caused by the second wave and is already represented by the 70-minute term. Five minutes preserves the existing bounded cancellation-lag unit for residual provider scheduling uncertainty. It is an operational allowance, not a provider guarantee. |
| Polling | 1 min | Exact current polling interval is 60 seconds. |
| Checkpoint/report publication | 5 min | Bounded operational allowance for retained artifact publication after worker execution. Provider latency is not guaranteed. Publication expiry remains non-pass. |
| Cancellation | 5 min | Existing accounting contract charges five minutes per active job for cancellation lag. This remains an estimate, not a billing guarantee. |
| Terminal reconciliation | 5 min | Bounded allowance for one final provider read, accounting, and retention. Provider consistency is uncertain; expiry remains non-pass. |

The enclosing monitor job timeout is **100 minutes**, leaving nine minutes after observer expiry
for decisive evidence retention and a controlled cancellation request. Neither bound guarantees
completion. Budget failure, malformed evidence, publication failure, observer expiry, or shutdown
failure remains non-pass.

The historical run `38041454291/1` did not comply retroactively with this amendment. It remains a
non-pass under its original 2,100-second observer contract.

### Stage-3 observer and terminal-accounting amendment

The prospective successor also uses one stage-wide observer across the existing seven fixed
stage-3 batches. All seven admission gates, the `32,32,32,32,32,32,24` topology, maximum worker
parallelism 32, 35-minute worker deadlines, 3,600 runner-minute ceiling, 2,400-minute launch
cutoff, and 1,200-minute cancellation reserve remain unchanged. A longer lifecycle grants no
additional spending allowance and does not guarantee completion.

The full-stage observer deadline is **326 minutes** and its enclosing job bound is **335 minutes**:

| Component | Allowance | Evidence and uncertainty |
|---|---:|---|
| Seven occupied worker batches | 245 min | `7 × 35`; each fixed batch remains separately admission-gated. |
| Six required admission dependencies | 60 min | Each existing admission job retains its 10-minute enclosing bound. |
| Scheduling/acquisition | 5 min | Operational allowance, not a provider guarantee. |
| Polling | 1 min | The observer polls at 60-second intervals. |
| Checkpoint/report publication | 5 min | Publication failure remains non-pass and cannot inhibit cancellation attempts. |
| Cancellation | 5 min | Operational cancellation-lag estimate, not a provider guarantee. |
| Terminal reconciliation | 5 min | Bounded final accounting and retained-evidence reconciliation. |
| Controlled shutdown | 9 min | Enclosing-job margin after the 326-minute observer deadline. |

Sparse stage-3 recovery derives its worker term from the number of occupied fixed batches. The
actual workflow still traverses all six sequential admission dependencies, including gates around
non-executing placeholder batches, so the admission term remains 60 minutes. It does not use
`ceil(selected shards / 32)` when selected shards span non-adjacent batches. Existing admission
gates remain authoritative; missing workers in a future, not-yet-admitted batch are not terminal
failures, while workers instantiated before admission are rejected. Sparse observer completion
requires all six admission handoffs and a terminal seventh batch node, including a legitimate
skipped placeholder, even when all selected workers terminated in an early batch.

Stage 3 must establish a digest-bound readiness record before batch 1. Every later admission
handoff requires the observer job to remain active before the next batch can start. A concurrent
watchdog treats observer loss, malformed terminal evidence, or premature completion as non-pass
and attempts cancellation. Hard provider interruption can prevent both evidence retention and a
cancellation request; this contract does not claim otherwise. Failed readiness, liveness,
retention, cancellation, or reconciliation remains explicit non-pass.
Monitor evidence retention has its own five-minute step bound; a failed or expired upload therefore
does not suppress the following best-effort cancellation step during normal job execution.

The observer accounts all jobs returned for the current run, including observer, admission,
support, worker, and reconciliation exposure under the existing accounting rules. It validates
the run, attempt, calibration, stage, and admission sequence before incorporating prior
observations. Every poll retains the maximum compatible current-run floor. Final accounting
requires exact terminal shard coverage, a successful observer lifecycle, all six stage-3
admission records for a full run, compatible predecessor accounting, and a bounded 15-minute
reconciliation job. The aggregate has a 30-minute enclosing bound, embeds the downloaded
accounting digest, and cannot publish successful evidence unless an independent consumer
downloads and verifies both the evidence checksum and accounting digest within a 10-minute
enclosing bound. Because reconciliation cannot observe its own terminal duration or later jobs,
it conservatively reserves the unobserved portions of the 15-minute reconciliation, 30-minute
aggregate, and 10-minute readback bounds before applying the unchanged 2,400-minute cutoff.

Partial checkpoint recovery eligibility remains distinct from qualification acceptance. This
amendment does not authorize stage-3 execution and does not change any historical verdict.

### Original decision context

The initiating failure was the calibration monitor's fixed 2,100-second observer deadline, not a
budget breach. Stage 2 admits 32 shards with maximum parallelism 16. Every worker job retains a
35-minute job deadline and a 29-minute mutation-engine deadline. A safe observer must cover:

1. monitor setup and the first authoritative observation;
2. every admitted shard while queued, acquiring a runner, or executing;
3. at most 16 concurrent workers, hence up to two worker waves for 32 admitted shards;
4. provider scheduling and runner-acquisition delay;
5. the final authoritative observation after all workers become terminal;
6. retention of the decisive accounting record; and
7. bounded cancellation and terminal reconciliation when a budget or lifecycle boundary fails.

Even before scheduling and reconciliation allowances, the structural worker bound is
`ceil(32 / 16) × 35 = 70 minutes`. The repository's approved performance contract states that
successful full evidence completes within 35 minutes (`docs/hypothesis-tree.md`). The current
40-minute monitor job timeout and 2,100-second internal observer deadline cannot cover the
admitted topology. Selecting a truthful observer deadline would therefore change an approved
wall-clock constraint or require a different approved topology/admission policy.

The original contract stopped because no larger allowance was authorized. Removing the timeout
remains rejected. Direction 1 now supersedes only that blocker; the alternative remains recorded:

- revise the 35-minute end-to-end wall-clock contract and approve a measured scheduling and
  reconciliation allowance on top of the 70-minute structural bound; or
- revise stage-2 topology/admission so all admitted work can finish and reconcile within the
  existing 35-minute contract without weakening worker deadlines, budget controls, cancellation
  reserve, or fail-closed behavior.

Increasing stage-2 parallelism from 16 to 32 is not assumed safe: it changes approved concurrency
and unresolved spending exposure. Splitting observation into multiple jobs does not remove the
end-to-end lifecycle requirement and must not create an unobserved gap between waves.

## Frozen failure-to-remedy matrix

| Failure | Owning seam | Proposed behavior | Required regression fixture | Acceptance check |
|---|---|---|---|---|
| Observer expires while admitted work is valid and budget still passes | `.github/workflows/mutation.yml` monitor orchestration plus a deterministic lifecycle helper in `fettle/staged_preflight.py` | Derive observer state from admitted batch count, maximum parallelism, unchanged worker deadline, controlled scheduling allowance, terminal-observation interval, retention, and cancellation/reconciliation allowance. Never treat observer expiry as a budget breach. Expiry remains fail-closed and records its distinct cause. | Controlled clock with 32 workers, parallelism 16, two waves, queue/acquisition transitions, worker timeouts, final polling, retention failure, and cancellation lag | The observer remains active through all admitted waves and terminal reconciliation, or cancels with a precise lifecycle/budget cause. No unbounded wait and no 2,100-second assumption. |
| Completed/cancelled provider record has reversed timestamps and no runner or steps | `fettle/staged_preflight.py::account_runner_minutes` | Preserve raw timestamps and anomaly. Exclude as never executed only with affirmative provider evidence that no runner was acquired and no execution occurred. Runner/step absence alone is insufficient. Confirmed execution is charged; ambiguous execution retains conservative exposure if a defensible bound exists, otherwise accounting is non-pass. Never normalize timestamps or omit the record. | Original-shaped anomalous record, affirmative never-executed record, confirmed executed record, partial runner identity, missing steps, conflicting provider evidence, and reversed timestamps | Every record remains in included, excluded, or unresolved evidence with its raw values and reason. Ambiguous/unbounded records reject accounting. The incident-shaped record is not silently zero-rated. |
| Cancelled producers have valid checkpoints but absent or zero-byte reports | `fettle/staged_preflight.py::plan_calibration_continuation`, checkpoint validators in `fettle/mutation_test.py`, and workflow artifact inventory | Admit a checkpoint-only representation only for a cancelled partial producer after full identity, manifest digest, corpus, provenance, outcome, attempt, execution-error, artifact inventory, and cancellation validation. Treat zero-byte reports as quarantined malformed historical artifacts, not as checkpoint representations. | Immutable incident copies for all 32 checkpoints and 13 zero-byte reports; negative variants for missing, malformed, stale, conflicting, extra, and cross-calibration evidence | Without bypassing validators, select exactly shards `[11,15,18,19,22,23,24,25,26,29,30,31,32,33,34]`, preserve exactly 1,917 terminal outcomes, retain two unscored `execution_error` attempts, and identify exactly 472 pending fingerprints. Every insufficient or contradictory variant is non-pass. |
| Shell redirection publishes a zero-byte report before producer success | `.github/workflows/mutation-calibration-shard.yml` and `fettle/mutation_test.py::_write_json_atomic` | Write the report to a temporary sibling, validate and fsync/close it, then atomically replace the publish path. Upload checkpoints independently. If report publication is interrupted, retain an explicit publication-state record and any malformed historical object under quarantine identity; do not present it as a report. | Fake worker interrupted before serialization, during temporary write, before rename, and after rename | Consumers see either a complete validated report or no report plus explicit non-pass publication evidence. They never see a newly published zero-byte canonical report. |
| Consolidation can rediscover quarantined reports or ignore checkpoint recovery | `fettle/mutation_test.py` aggregation/selection and `.github/workflows/mutation.yml` consolidation inputs | Produce an explicit validated-representation inventory with immutable digests and one selected representation per shard. Consolidation consumes only that inventory. Quarantined files remain retained but are outside selectable report paths. | Mixed directory containing valid reports, validated checkpoint-only representations, zero-byte quarantined reports, duplicate reports, and conflicting digests | Consolidation consumes the declared 32-shard representation exactly once, cannot glob quarantined content, preserves 1,917 historical terminal outcomes, and combines synthetic results only for 472 pending fingerprints. Consumer readback reproduces the same digests and counts. |
| A later 854.38 observation can replace the 919.51 historical floor | `retain_historical_accounting_floor`, planning/dispatch schemas, monitor inputs, continuation, reconciliation, publication, and consumer validation | Carry a typed, origin-bound monotonic floor through every handoff. Each producer emits terminal reconciliation and effective maximum; each consumer verifies origin chain and applies `max(current reconciliation, all compatible prior floors)`. Missing, stale, conflicting, malformed, or foreign floors are non-pass. | Same-origin snapshots at 854.38 and 919.51 plus lower terminal reconciliation; foreign-chain and malformed variants | Every downstream effective amount is at least 919.51. The 854.38 snapshot remains retained but can never lower the floor. No amount or outcome is imported into successor qualification. |
| Recovery can be planned but not atomically published and read back | Workflow publication jobs, explicit evidence inventory, and the canonical evidence consumer | Publish representation inventory, accounting chain, aggregate, and consumer record as one digest-bound set. Eligibility derives from every required criterion, not overall job status. | Synthetic end-to-end fixture with fake workers and controlled clock, including interrupted publication and stale consumer input | Atomic publication either validates completely or remains non-pass. Consumer readback matches the published set. Next-stage eligibility is true only for synthetic repaired-contract evidence; historical stage 2 remains false. |

## Required offline verification after the blocker is resolved

Implementation may start only after the governing decision above supplies an explicit lifecycle
bound or compatible topology. Verification must then use immutable incident copies, deterministic
fixtures, fake workers, and a controlled clock. It must not execute the mutation engine or contact
the provider.

The focused suite must prove:

- multiple worker waves and observer expiry are deterministic;
- cancellation cause remains distinct from cancellation-era provider anomalies;
- anomalous records are preserved and ambiguous accounting remains non-pass;
- interrupted report publication cannot create a selectable canonical report;
- checkpoint-only recovery is narrow, identity-complete, and fail-closed;
- exactly 15 unfinished shards and 472 unfinished fingerprints are selected;
- all 1,917 terminal outcomes and unscored execution-error history remain unchanged;
- the 919.51 floor survives planning, dispatch, monitoring, continuation, reconciliation,
  publication, and readback;
- consolidation consumes only the explicit validated representation; and
- synthetic completion demonstrates the repaired contract without qualifying historical or live
  evidence.

Negative cases must include missing and malformed JSON, zero-byte canonical and quarantined
objects, stale and foreign identities, incomplete manifests, conflicting checkpoints and reports,
duplicate representations, changed terminal outcomes, scored execution errors, reversed and
missing timestamps, partial runner identity, ambiguous execution, floor regression, interrupted
publication, stale readback, and observer/reconciliation expiry.

## Anticipated blast radius and changed identities

No executable identity has changed yet. After approval, the expected minimum blast radius is:

- `fettle/staged_preflight.py` — lifecycle derivation, conservative provider accounting,
  checkpoint-only representation validation, monotonic accounting handoffs;
- `fettle/mutation_test.py` — atomic publication and explicit representation aggregation;
- `.github/workflows/mutation.yml` — observer lifecycle, floor propagation, explicit recovery
  inventory, consolidation, publication, and readback;
- `.github/workflows/mutation-calibration-shard.yml` — atomic producer publication and separate
  checkpoint/publication-state retention;
- focused fixtures and tests under `tests/`; and
- `docs/behavior-map.md` and governing mutation documentation for the approved contract change.

Any additional file is out of scope unless impact analysis demonstrates it owns a required
handoff. Historical evidence directories are read-only fixture sources and must not be modified.

## Success and qualification sequence

After owner approval of the governing wall-clock/topology amendment:

1. record the amendment and exact lifecycle formula;
2. add immutable synthetic fixtures derived without modifying historical evidence;
3. implement the narrow executable and workflow changes;
4. run focused contract, error-path, boundary, and regression tests offline;
5. run the complete synthetic path with fake workers and a controlled clock;
6. obtain an independent diff and fixture review;
7. run repository quality gates, including `fettle check --all` and completion validation only for
   the repair milestone if its criteria are fully evidenced;
8. return the exact diff, changed identities, test evidence, negative cases, approved observer
   bound, remaining risks, and proposed successor qualification sequence; and
9. stop before commit, push, preflight, mutation execution, calibration, or dispatch.

Success does not change the historical verdict. Any successor qualification requires separate
authorization and fresh compatibility evidence under the changed executable and consumer
identities.
