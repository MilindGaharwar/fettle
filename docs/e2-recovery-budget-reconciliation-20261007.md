# E2 Recovery Budget Reconciliation — 2026-10-07

## Fixed limits

- Overall operational ceiling: **800 runner-minutes**.
- Cancellation headroom: **100 runner-minutes**.
- Execution and completion cutoff: **700 runner-minutes**.
- Shard timeout, concurrency, candidate, scope, policy, and acceptance criteria are unchanged.

## Prior allocation and observed recovery overhead

The original allocation was 20 minutes for wave 1, 75 for wave 2, 500 for wave 3,
105 for orchestration and aggregation, and 100 for cancellation headroom. Its
pre-wave-3 boundary of 95 minutes assumed only the first two wave allocations had
been consumed. It did not accommodate the two preserved failed recovery attempts.

The retained terminal accounting totals **146.93 minutes**:

| Attempt | Runner-minutes |
|---|---:|
| Source run `37573662156/1` | 64.50 |
| Setup failure `37580393007/1` | 0.35 |
| Layout failure `37589782905/1` | 82.08 |
| **Total** | **146.93** |

The 82.08-minute layout failure includes GitHub runner intervals for all 216 matrix
jobs, including cancelled jobs that acquired no runner and ran no steps. Charging
them is intentionally conservative; no prior usage is removed or relabelled.

## Conservative completion projection

The 40 retained successful shards total 48.27 minutes, average 1.21, maximum 1.92,
and p95 **1.80 runner-minutes per shard**. The recovery gate reserves the p95 for
all 216 new shards, including the canary:

- Shards: `216 × 1.80 = 388.80` minutes.
- Preparation, launch accounting, canary readback, monitoring, validation,
  aggregation, durable readback, and terminal accounting: **30.00** minutes.
- Conservative remaining reserve: **418.80** minutes.
- Projected cutoff usage from 146.93: **565.73** minutes.
- Uncertainty margin before the 700-minute cutoff: **134.27** minutes.
- Separate cancellation headroom above the cutoff: **100.00** minutes.

The support reserve exceeds the retained 16.23 minutes used by source freeze,
two validation jobs, dispatch, and monitoring, while allowing for the extra canary
readback and final aggregation/readback jobs.

The revised pre-canary boundary is therefore derived as `700 − 418.80 = 281.20`
runner-minutes. It is not an increase to the 800-minute ceiling.

After successful canary readback, the workflow recalculates cumulative usage and
projects the remaining 215 shards at the greater of the observed canary duration or
the retained 1.80-minute p95, plus the unchanged 30-minute support reserve. Missing,
malformed, ambiguous, or insufficient evidence stops matrix expansion.

Run `37600554367/1` stopped during preparation on a transient GitHub API HTTP 502.
Its only executed job consumed 0.63 minutes; the canary and every downstream job
had no runner and no steps. The attempt remains permanently failed and is charged
by subsequent cumulative accounting. Immutable evidence collection uses three
bounded attempts (immediate, 5 seconds, then 15 seconds) and publishes only a
complete final file; this does not retry a shard or mutation command.
