# Assurance Integrity Shadow Assessments

Status: collecting; 0 of 20 qualifying assessments accepted

This append-only register records real change assessments before production
enforcement. Test fixtures, repeated runs of an unchanged subject, and invented
evidence do not count.

Every row must follow the machine-reproducible
[prior-v1 baseline protocol](assurance-integrity-baseline-protocol.md).

## Acceptance Rules

- Assess a real, distinct change with `fettle assurance --policy production`.
- Use the reviewed collector/comparator required by the baseline protocol;
  manual reconstruction does not count.
- Retain the exact subject, policy, scope, capture digest, both normalized
  decisions, comparison, and raw-output digests.
- Record the prior v1 decision, hardened decision, and every changed dimension.
- Classify each difference as intentional hardening, defect, or unresolved with
  evidence; only rows with no differences or fully evidenced intentional
  hardening can be accepted.
- A blocked, malformed, stale, or unexplained result is non-pass and does not
  advance graduation until resolved.
- Enforcement requires 20 accepted rows and a separate explicit operator
  approval recorded after review of the completed register.

## Register

| # | Date | Change / PR | Capture digest | Prior decision | Hardened decision | Changed dimensions | Classification | Evidence bundle | Reviewer | Accepted |
|---|---|---|---|---|---|---|---|---|---|---|

## Operator Decision

Not requested. Fewer than 20 qualifying assessments have been accepted.
