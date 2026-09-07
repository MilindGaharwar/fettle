# Assurance Integrity Shadow Assessments

Status: collecting; 2 of 20 qualifying assessments accepted

This append-only register records real change assessments before production
enforcement. Test fixtures, repeated runs of an unchanged subject, and invented
evidence do not count.

Every row must follow the machine-reproducible
[prior-v1 baseline protocol](assurance-integrity-baseline-protocol.md).

## Acceptance Rules

- Assess a real, distinct change with `fettle assurance --policy production`.
- Use the reviewed collector/comparator required by the baseline protocol.
- Retain exact subject content, normalized decisions, comparison, and digests.
- Classify every difference with evidence; unresolved or defect rows do not count.
- Enforcement requires 20 accepted rows and explicit operator approval.

## Register

Generated from reviewed external bundles. Do not edit totals or rows manually.

| # | Date | Change / PR | Capture digest | Prior decision | Hardened decision | Changed dimensions | Classification | Evidence bundle | Reviewer | Accepted |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-07 | behavior-decision-table | `sha256:bbe8eb21a58ca998fed989bec9c37e9a1f8e76d8578e3d9867c4113192790f08` | FAIL | FAIL | none | none | `bbe8eb21a58ca998fed989bec9c37e9a1f8e76d8578e3d9867c4113192790f08` | Milind | yes |
| 2 | 2026-09-07 | docs-claims-gate | `sha256:e57f1022205dddc1e37fcb12651483a53fb32fae9261ebd8c91299e2b8f4128b` | FAIL | FAIL | dimensions.behavior, dimensions.security, policy.criteria.behavior, policy.criteria.security | intentional_hardening | `e57f1022205dddc1e37fcb12651483a53fb32fae9261ebd8c91299e2b8f4128b` | Milind | yes |

## Operator Decision

Not requested. Fewer than 20 qualifying assessments have been accepted.
