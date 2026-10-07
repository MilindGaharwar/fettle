# Staged Preflight Recovery Contract

Date: 2026-10-06

## User story

As the repository owner, I want the staged preflight to continue from eight immutable,
compatible shard reports so that infrastructure metadata anomalies do not force valid
mutation work to repeat, while incomplete or ambiguous evidence can never qualify.

## Accounting contract

The GitHub workflow-jobs REST schema exposes `status`, `conclusion`, `run_attempt`,
runner identity, steps, `started_at`, and `completed_at`. GitHub documents that a job
prevented by a job-level condition is marked skipped. GitHub billing documentation
describes Actions minutes as runner processing time and notes that failed attempts
consume their elapsed processing time. Therefore the timestamp sum below is an
operational estimate, not an invoice or billing API result.

Sources:

- <https://docs.github.com/en/rest/actions/workflow-jobs>
- <https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions>
- <https://docs.github.com/en/billing/concepts/product-billing/github-actions>

Classification is fail-closed:

| Job evidence | Operational contribution | Treatment |
|---|---:|---|
| `completed` + `skipped`, no runner, no steps | 0 | Exclude timestamp fields; retain raw values and exclusion reason. Reversed skipped timestamps are recorded as anomalies. |
| `queued`, `requested`, `pending`, or `waiting`, no runner, no steps, no completion | 0 at observation | Record as not started. Its future allowance remains reserved by the launch ceiling. |
| Started and completed, including success, failure, timeout, neutral, action-required, or cancellation | Full observed interval | Require ordered timestamps and exact run attempt. |
| Started and in progress | Start through the accounting observation time | Require an aware observation time not before start. |
| Cancelled or completed without enough evidence to prove whether a runner executed | Unknown | Reject the budget gate. |
| Any potentially executed job with missing, partial, malformed, or reversed timing | Unknown | Reject the budget gate. |

Pages must be non-empty, job IDs unique, each page's `total_count` consistent with the
complete unique set, and every job must match the expected run attempt. Raw API pages
are retained beside the derived accounting report. The report lists included and
excluded jobs, fields, reasons, anomalies, source run, attempt, and raw SHA-256.

## Recovery compatibility contract

Run `37464324954` remains non-pass. A new recovery run may reference, but never modify
or relabel, its eight reports. Reuse requires all of the following before any remaining
shard executes:

1. Exact source run `37464324954`, attempt `1`, source orchestration
   `891562ba4909b16e6252a0eb7e8674393f43eba0`, and candidate
   `0fc41fdfee13e09f4bda3dc5eee177030882aa36`.
2. Source plan SHA-256
   `1e712595d7c6adccbd17aa284eaf4821afda82c9b61798022eeb6ea861190294`.
3. Exact expected SHA-256 for each of the eight report files.
4. Exact manifest topology and all 256 manifest digests.
5. Equal Python implementation/version, mutation dependency digest, policy digest,
   candidate, engine version, and fixed wave membership.
6. Manifest-bound validation of each source report and a unique origin assignment for
   all 256 shard indexes.

The recovery run executes only wave 2 and wave 3. Its gates charge the complete
source-run attempt plus the current recovery attempt against the original 740-minute
allocation. The final recovery record maps every shard to its source run, attempt,
artifact digest, and manifest digest. The unchanged authoritative Python aggregator
then consumes exactly 256 compatible reports. No single-run claim is made.

## Success criteria

- Accounting fixtures cover every status and malformed-evidence boundary.
- Transition fixtures prove the cumulative gates at 20, 95, 595, and 640 minutes.
- Recovery fixtures reject stale identities and every missing/duplicate/conflicting
  origin while accepting an exact mixed-origin 256-report corpus.
- Actionlint, focused tests, full tests, and Fettle scan pass; completion checkpoint
  validation is structurally valid while honestly retaining unrelated blocked criteria;
  and independent review finds no dispatch blocker before dispatch.
- Remote execution stops on the first failed shard, evidence gate, or budget gate.

## Separately authorized continuation

Run `37476889333` proved that conditional earlier matrices and supporting jobs still
consume the workflow run's matrix expansion capacity. The retained provider record
contains one unexpanded wave-3 placeholder with the literal matrix expression,
`completed/skipped`, null runner identity, and no steps. GitHub exposed no textual
rejection annotation; the documented applicable limit is 256 matrix jobs per workflow
run: <https://docs.github.com/en/actions/reference/limits>.

The continuation is therefore a separate workflow with only the 216 unattempted
shards at maximum parallelism 8 and seven support jobs (223 fully expanded jobs). Its
one-shot push trigger is restricted to the integration branch, the workflow file,
and the exact authorized commit message because GitHub does not expose a newly added
`workflow_dispatch` workflow until it exists on the default branch. Ordinary later
pushes cannot launch it.
Its
prepare gate imports explicit run `37464324954`, attempt 1 and run `37476889333`,
attempt 1, then revalidates exact candidate, orchestration and workflow provenance,
runtime, dependency and policy hashes, all manifest digests, source plan hashes,
report hashes, and retained validations. Budget gates sum all three attempts against
the original 740-minute operational allocation; aggregation launches at 595 minutes
or less and completion must remain at 640 minutes or less, preserving 100 minutes of
cancellation headroom. Both historical runs remain permanently non-pass.
