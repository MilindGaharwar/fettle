# Calibration terminal-accounting retention

## Guarantee

The calibration accounting job publishes `calibration-accounting.json` as its
primary, 90-day GitHub Actions artifact. If that upload action fails after a
bounded accounting payload was generated, the same job also emits a
digest-bound copy of the exact payload bytes into its job log. The downstream
aggregate may retrieve and validate that copy from the exact run attempt.

Fallback retention does **not** turn the accounting job or calibration run into
a success. The primary publication failure remains visible, the aggregate
remains non-pass, and recovered log bytes cannot become an authoritative
predecessor or satisfy continuation eligibility. A retained typed decision with
`passed: false` or `terminal_accounting_status: indeterminate` remains non-pass
and indeterminate.

The fallback survives a failure confined to the primary `upload-artifact`
action when all of the following remain available:

- the accounting job generated one payload no larger than 256 KiB;
- the fallback-emission step completed and GitHub captured its stdout;
- the exact attempt's authenticated job metadata and completed log, bounded to
  4 MiB for deterministic readback, are readable;
- the downstream aggregate runs within its existing 30-minute bound.

## Exclusions and failure states

The guarantee does not cover a shared GitHub Actions outage, missing or
transformed job logs, workflow-run deletion, retention expiry, repository-access
loss, runner loss before fallback emission, or simultaneous artifact and log
publication failure. Missing, truncated, altered, foreign, oversized, malformed,
or conflicting fallback records produce an explicit unavailable/non-pass
readback result. A job log larger than 4 MiB is outside the fallback guarantee
and is rejected as unavailable. Accounting-generation failure remains typed indeterminate only
when the existing local containment generator can create that decision; it is
otherwise unavailable.

## Retention and access

Both channels use the repository's existing GitHub Actions retention and access
policy. The workflow requests no new credential, permission, destination, or
retention change. This public repository permits repository readers to retrieve
completed job logs through the GitHub Actions API. Payloads are bounded,
machine-readable accounting JSON and must remain secret-free. The envelope is
split into at most 32 ordered 12-KiB chunks; each log record binds its index,
total, and the whole-envelope digest. Log fallback is not an external archive
and expires with the provider's Actions retention.

The envelope binds the exact bytes and their SHA-256 to repository, candidate,
workflow path and ref, run, attempt, calibration chain, stage, schema, kind, and
accounting lineage. Those self-described fields are accepted only when they
match independently authenticated exact-attempt job metadata and expected
workflow inputs.

## Readback and retry

Readback prefers the primary artifact. A malformed, foreign, or conflicting
primary result is rejected rather than silently replaced. Log fallback is used
only after primary download failure and only for the unique completed accounting
job in the exact run attempt. Retrieval has three bounded attempts. Identical
duplicate log records are deduplicated; conflicting duplicates are rejected.
The retrieved bytes receive strict digest, provenance, lineage-shape, and
applicability validation. They are deliberately not treated as a successful
semantic accounting decision or authoritative predecessor through this channel.

An orphaned fallback record has no authority. Later-stage launch and sparse
continuation continue to require their existing artifact, lineage, producer,
checkpoint, and terminal-success contracts.

## Containment and accounting boundaries

Execution containment, accounting validity, and evidence availability are
separate claims:

- one stage-3 worker batch is bounded at 32 workers × the conservative
  35-minute charge = 1,120 worker-minutes;
- support work is separately reserved by the frozen accounting contract:
  accounting 15 minutes, aggregate 30 minutes, and evidence readback 10 minutes;
- the fallback adds no job and runs inside the accounting and aggregate bounds;
- the 1,120 worker bound alone does not cover support exposure or establish
  reconciled spend.

Cancellation does not remove the job timeouts. Missing terminal accounting is
not zero consumption and does not reset current or historical floors.
