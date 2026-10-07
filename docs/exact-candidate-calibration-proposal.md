# Exact-Candidate Calibration Proposal

Date: 2026-10-07

Status: **proposal only — calibration is not authorized**

## Candidate and accepted preflight

- Executable candidate: `0fc41fdfee13e09f4bda3dc5eee177030882aa36`
- Accepted aggregation recovery: run `37560100974`, attempt 1
- Aggregate: 256 reports, 45,432 generated and canonicalized details, zero
  collisions
- Corpus digest: `155a02b863d6b440211e09eef8daf189098554ca5871c5a484e7b65a3b005be2`
- Aggregate SHA-256: `dded4dfe0ba8fcb9a1eccd995d7e2e31b68215c3468884dc418dd8709699f173`

The failed verdicts of source runs `37464324954`, `37476889333`, and
`37550308775` remain unchanged. Run `37560100974` is the accepted linked preflight
record; it does not itself qualify the candidate.

## Proposed calibration flow

1. Authorize one exact-candidate calibration separately.
2. Bind the calibration input to candidate `0fc41fd…`, aggregation recovery run
   `37560100974`, attempt 1, aggregate SHA-256, corpus digest, manifests, dependency
   hash, policy hash, and Python 3.12.14.
3. Run one authoritative calibration with the existing timeouts, thresholds, and
   mutation acceptance policy. No preflight shard is regenerated.
4. Stop on identity mismatch, missing/stale evidence, indeterminate outcome, or
   budget breach. No retry is implied.
5. Retain full calibration reports, job metadata, logs, source-restoration evidence,
   cache identity, checksums, and independent artifact readback.

## Resource budget proposal

The original preflight allocation consumed 351.11 of 740 operational runner-minutes,
leaving 388.89 minutes. That remainder is preflight reserve, not automatic calibration
authorization. Before dispatch, derive a separate calibration estimate from the
accepted 45,432-detail corpus and existing bounded runtime evidence. Reserve explicit
setup, monitoring, cancellation, aggregation, and readback headroom. Do not launch if
the conservative estimate exceeds the separately approved calibration allocation.

## Check-binding plan

- The authoritative `mutation evidence` check must execute on and bind to the exact
  candidate commit, not the orchestration commit.
- The accepted preflight artifact is an input, not a substitute check conclusion.
- Verify repository, workflow ref, run ID and attempt, candidate SHA, aggregate hash,
  corpus digest, manifest topology, runtime, dependencies, policy, and calibration ID.
- Diagnostic, preflight, aggregation-recovery, and orchestration checks must remain
  unable to satisfy the authoritative required check.
- Branch-protection changes, merge, release, and milestone completion remain outside
  this proposal.
