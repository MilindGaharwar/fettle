# Hypothesis Tree: Recover the Frozen-Candidate Staged Preflight

**Objective:** Complete compatible preflight evidence for candidate
`0fc41fdfee13e09f4bda3dc5eee177030882aa36` without rerunning the eight accepted
wave-1 shards or resetting the 740 runner-minute operational budget.

## Root constraints

- Run `37464324954` remains immutable and permanently non-pass.
- Its eight successful shard reports are reusable only if every execution input,
  manifest, artifact, and origin identity remains compatible.
- Missing, conflicting, duplicated, or unknown executed-job evidence is non-pass.
- The existing `aggregate_preflight_shards()` remains the final corpus authority.
- Each remaining shard may execute once; no failed-shard retry is allowed.

## H1 — Status-aware operational accounting (selected)

**Hypothesis:** Classifying a job as zero-execution only when GitHub reports it as
completed/skipped with no assigned runner and no steps will remove irrelevant skipped
timestamp anomalies while retaining conservative accounting for every job that could
have consumed a runner.

**Falsification:** Any executed or potentially executed job can enter the zero-usage
class, or any missing/reversed timestamp for such a job can pass.

**Evidence required:** Official status/conclusion and billing documentation; retained
run response; fixtures for skipped, successful, failed, cancelled, in-progress,
missing-timestamp, pagination, duplicate, and run-attempt cases.

## H2 — Ignore all negative durations (rejected)

**Hypothesis:** Clamping every negative duration to zero would let the gate proceed.

**Falsification:** An executed job with contradictory timestamps would be accepted.

**Decision:** Rejected before implementation because it weakens fail-closed handling
and discards relevant contradictions.

## H3 — Reuse wave 1 through a linked recovery record (selected conditionally)

**Hypothesis:** The eight reports can be combined with 248 newly executed reports
without changing aggregate acceptance when a separate recovery validator proves the
source plan/report hashes, candidate, runtime, dependencies, policy, complete manifest
topology, exact origin assignment, and current execution identities.

**Falsification:** The existing aggregate cannot consume the exact 256-report union,
or compatibility cannot be proven before fan-out.

**Evidence required:** Independent read-back of the eight reports; source/current plan
comparison; fixtures proving duplicate, missing, substituted, stale, and conflicting
origins fail; an outcome-equivalence fixture through the existing aggregate.

## H4 — Standalone 216-shard continuation (selected, pending execution)

**Hypothesis:** A separate workflow containing only the 216 never-started wave-3
shards and seven support jobs can complete the frozen corpus without crossing GitHub's
256-job matrix ceiling or replaying accepted work.

**Falsifiers:** The expanded topology exceeds 256 jobs; either prior run cannot be
revalidated by exact run/attempt, manifest, identity, and artifact hash; cumulative
operational usage exceeds a launch or completion ceiling; any shard fails; or the
authoritative aggregate cannot reconcile exactly 256 unique reports.

**Evidence before dispatch:** GitHub documented a maximum of 256 matrix-generated
jobs per workflow run. Recovery run `37476889333` exposed wave 3 only as one literal
`${{ matrix.shard }}` placeholder marked completed/skipped, with no runner and no
steps; GitHub exposed no more specific annotation. The old readiness tests checked
each wave's membership and parallelism but never counted the fully expanded workflow
topology. The proposed topology is 216 matrix jobs plus seven support jobs, 223 total.
Earlier-wave matrices are absent rather than conditionally instantiated.
