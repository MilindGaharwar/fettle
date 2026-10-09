# Accounting-only staged-preflight continuation proposal

Status: **prepared for review; not wired for dispatch or source admission**.

This proposal does not change the verdict of source run `37795579761/1`. The
source remains `completed/cancelled`, non-pass, and incomplete. It proposes a
separately identified recovery that may reuse its 40 immutable successful
reports and execute only the 216 wave-3 shards after every condition below is
proved.

## Exact admission contract

Admission must require all conditions, with no fallback or inference:

1. Bind the source to run `37795579761`, attempt `1`, candidate
   `abed35141a0734b46f753e914d9450265e5a34ee`, its workflow path/ref, its
   orchestration SHA, and frozen plan SHA-256
   `187f7fb1466621fd2727b4197ef2ab79bc4fe4efe78c8440b7f4582f3b9edbad`.
2. Require terminal `completed/cancelled`, and require the retained monitor
   outcome and cancellation request to identify only
   `persistent-accounting-uncertainty`.
3. Verify all 8 wave-1 and 32 wave-2 shard jobs terminal-successful. Reject any
   duplicate, absent, failed, retried, or origin-mismatched prerequisite job.
4. Verify all 40 report artifacts are unexpired, source-bound, digest-bound,
   assigned exactly once, and compatible with the frozen plan, runtime,
   dependency, policy, and manifest identities.
5. Independently rerun both committed wave validators over downloaded bytes;
   require success and exact outputs matching retained hashes
   `20dc3ab51a093a8d9a15c6939d4c9777f69aa112bfbe5c0692ef50c92e7fcadd`
   and `511b391fa1e693d536cc4ef1cbb1c99f92b126042f318bafe47d49a318881b7f`.
6. Verify the three immutable monitor snapshots and monitor log. Require the
   sole accounting rejection to be the reviewed `queued + started_at + no
   runner identity + no steps` transition. Reject API, execution, restoration,
   identity, artifact, validator, or other integrity failures.
7. Reconcile terminal accounting from a fresh terminal response and the
   retained snapshots. Preserve both the historical exposure bounds and the
   corrected terminal intervals. Require cumulative usage plus the unchanged
   wave-3 allowance and orchestration allowance to remain within the unchanged
   overall budget before launch.
8. Prove non-execution of every planned wave-3 shard (the exact 216-index set)
   from all of:
   - the source terminal job inventory contains no wave-3 shard job;
   - the source artifact inventory contains no wave-3 shard report;
   - the parent dispatch job failed at its prerequisite guard and its dispatch
     step was skipped;
   - the continuation workflow run inventory contains no run titled
     `Staged preflight continuation for source 37795579761/1`.
9. Reject missing, malformed, stale, expired, contradictory, or incomplete
   evidence. A later GitHub timestamp correction cannot validate the original
   monitor decision and cannot turn the source into a pass.
10. Issue a new recovery run identity. Link the source evidence hashes and
    assign the 40 reused origins to `37795579761/1`; assign all new origins to
    the recovery run. Existing duplicate-dispatch protection must remain.

## Sender, monitor, cancellation, admission, and continuation review

- **Sender:** no dispatch is permitted until the admission record exists and
  the duplicate-dispatch query proves no prior recovery identity.
- **Monitor:** use explicit observation timestamps and the unchanged 35-minute
  job timeout as retained context. Charge all dispatch-to-observation exposure;
  the timeout cannot safely tighten that bound because the reported start is
  the field known to be revision-prone. Retain every raw and computed sample.
- **Cancellation:** malformed or unbounded accounting still requests bounded
  cancellation. Budget-gate exit 2 with `passed:false` remains an immediate
  operational cutoff.
- **Admission:** add a new explicit accounting-cancellation mode; do not add
  `cancelled` to the existing generally accepted source conclusions.
- **Continuation:** the matrix must equal the proven 216 never-started shards.
  It must not retry or replace any of the 40 successful source shards.

## Required authorization

Integration requires separate authorization to implement and commit the above
admission contract and workflow wiring. Execution then requires a second,
explicit authorization naming the reviewed commit, source run/attempt, frozen
candidate, plan hash, exact 216-shard matrix, unchanged budget, and one new
recovery dispatch. Neither authorization permits calibration, threshold or
budget changes, merge, release, or a completion claim.
