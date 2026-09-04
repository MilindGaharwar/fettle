# Assurance Integrity Shadow Assessments

Status: collecting; 0 of 20 qualifying assessments accepted

This append-only register records real change assessments before production
enforcement. Test fixtures, repeated runs of an unchanged subject, and invented
evidence do not count.

## Acceptance Rules

- Assess a real, distinct change with `fettle assurance --policy production`.
- Retain the exact subject, policy, scope, and Assurance Record digest.
- Record the prior v1 decision, hardened decision, and every changed dimension.
- Classify each difference as intentional hardening or defect with evidence.
- A blocked, malformed, stale, or unexplained result is non-pass and does not
  advance graduation until resolved.
- Enforcement requires 20 accepted rows and a separate explicit operator
  approval recorded after review of the completed register.

## Register

| # | Date | Change / PR | Subject | Record digest | Prior decision | Hardened decision | Difference classification | Evidence | Accepted |
|---|---|---|---|---|---|---|---|---|---|

## Operator Decision

Not requested. Fewer than 20 qualifying assessments have been accepted.
