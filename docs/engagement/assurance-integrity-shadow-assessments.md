# Assurance Integrity Shadow Assessments

Status: graduated; 20 of 20 qualifying assessments accepted

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
| 1 | 2026-09-07 | uat-p72-evidence-hardening | `sha256:03d09dc4fcee32595bc4f4eb53a27596f592255fdbcb7d0f7659c00bc7881ea9` | FAIL | FAIL | none | none | `03d09dc4fcee32595bc4f4eb53a27596f592255fdbcb7d0f7659c00bc7881ea9` | Milind | yes |
| 2 | 2026-09-07 | readme-anchor-repair | `sha256:36c12078a306d2be68b2ab0da2743b5d63cddd876e20015049570788cb640f40` | FAIL | FAIL | none | none | `36c12078a306d2be68b2ab0da2743b5d63cddd876e20015049570788cb640f40` | Milind | yes |
| 3 | 2026-09-07 | verdict-evidenced-invariant | `sha256:4b4260aa657360ded3dfde161e8c525e2b89dc87f7c9ebbb8d6ec159d13e44ee` | FAIL | FAIL | none | none | `4b4260aa657360ded3dfde161e8c525e2b89dc87f7c9ebbb8d6ec159d13e44ee` | Milind | yes |
| 4 | 2026-09-07 | canonical-plan-lifecycle | `sha256:55984b564815e837dac406e2ae7a5db7c06ff58d2aa15a6e25c8ef733905541b` | FAIL | FAIL | none | none | `55984b564815e837dac406e2ae7a5db7c06ff58d2aa15a6e25c8ef733905541b` | Milind | yes |
| 5 | 2026-09-08 | threat-model-probe-failure | `sha256:5da5f6a1e9f1b11d3f791be27bb4bfcbc7735f1f5966c7871ce2dd816816bb8f` | FAIL | FAIL | none | none | `5da5f6a1e9f1b11d3f791be27bb4bfcbc7735f1f5966c7871ce2dd816816bb8f` | Milind | yes |
| 6 | 2026-09-07 | baseline-version-provenance | `sha256:6d64fb36e7aa16bc4a8ef2dd7b85cbd1ce2a0aedcf17f527220ca52d4961c6aa` | FAIL | FAIL | none | none | `6d64fb36e7aa16bc4a8ef2dd7b85cbd1ce2a0aedcf17f527220ca52d4961c6aa` | Milind | yes |
| 7 | 2026-09-08 | autofix-content-classification | `sha256:803cfbe57fb263c45f86a0f502a2da6500cefec8f0991fcbd60e2e764410c589` | FAIL | FAIL | none | none | `803cfbe57fb263c45f86a0f502a2da6500cefec8f0991fcbd60e2e764410c589` | Milind | yes |
| 8 | 2026-09-07 | quality-workflow-review-command | `sha256:88bea57de3f6c78983c7af537953659512f8e734e9ef1cc50bc413d4526a261f` | FAIL | FAIL | none | none | `88bea57de3f6c78983c7af537953659512f8e734e9ef1cc50bc413d4526a261f` | Milind | yes |
| 9 | 2026-09-07 | corpus-spec-gwt | `sha256:9bafcc3ac6c53c4f08017071224f046c092359d5a013d5fb24b2050256421f09` | FAIL | FAIL | none | none | `9bafcc3ac6c53c4f08017071224f046c092359d5a013d5fb24b2050256421f09` | Milind | yes |
| 10 | 2026-09-07 | orientation-archive-link | `sha256:9c8ff773a4b52006e190f4f651c1d92c107015b0bf363900bf2cfc2b7099cb9d` | FAIL | FAIL | none | none | `9c8ff773a4b52006e190f4f651c1d92c107015b0bf363900bf2cfc2b7099cb9d` | Milind | yes |
| 11 | 2026-09-07 | pipeline-dump-command | `sha256:acfe726946604a78ec547b8d74c63b1e3b60864a3078d328e272703e7b4d086f` | FAIL | FAIL | none | none | `acfe726946604a78ec547b8d74c63b1e3b60864a3078d328e272703e7b4d086f` | Milind | yes |
| 12 | 2026-09-07 | event-map-doc | `sha256:b3f35b24f6a77b40fb689b03228fdc195222912d56ae424e1326e3b6af261ea2` | FAIL | FAIL | none | none | `b3f35b24f6a77b40fb689b03228fdc195222912d56ae424e1326e3b6af261ea2` | Milind | yes |
| 13 | 2026-09-07 | behavior-decision-table | `sha256:bbe8eb21a58ca998fed989bec9c37e9a1f8e76d8578e3d9867c4113192790f08` | FAIL | FAIL | none | none | `bbe8eb21a58ca998fed989bec9c37e9a1f8e76d8578e3d9867c4113192790f08` | Milind | yes |
| 14 | 2026-09-08 | cross-review-exit-status | `sha256:bcf9faa7467ea68339466a116dfaae2b5487d544b67e4c81ffc7ea750bfe1045` | FAIL | FAIL | none | none | `bcf9faa7467ea68339466a116dfaae2b5487d544b67e4c81ffc7ea750bfe1045` | Milind | yes |
| 15 | 2026-09-07 | mcp-explicit-human-approval | `sha256:d228949cbe9e605c07ebf94d9c37204579318150eee6adcaba393b764dcf0b4c` | FAIL | FAIL | dimensions.security, policy.criteria.security | intentional_hardening | `d228949cbe9e605c07ebf94d9c37204579318150eee6adcaba393b764dcf0b4c` | Milind | yes |
| 16 | 2026-09-07 | corpus-spec-scope | `sha256:e46083044f7eacc39aaaf246829938fb75191d850f9467ee170078bb9cacd57a` | FAIL | FAIL | none | none | `e46083044f7eacc39aaaf246829938fb75191d850f9467ee170078bb9cacd57a` | Milind | yes |
| 17 | 2026-09-07 | docs-claims-gate | `sha256:e57f1022205dddc1e37fcb12651483a53fb32fae9261ebd8c91299e2b8f4128b` | FAIL | FAIL | dimensions.behavior, dimensions.security, policy.criteria.behavior, policy.criteria.security | intentional_hardening | `e57f1022205dddc1e37fcb12651483a53fb32fae9261ebd8c91299e2b8f4128b` | Milind | yes |
| 18 | 2026-09-07 | assurance-record-uat-consent | `sha256:f0e4226f48bd2a50094acffc56965d58a619458c28b44cf0095b8d7959728388` | FAIL | FAIL | none | none | `f0e4226f48bd2a50094acffc56965d58a619458c28b44cf0095b8d7959728388` | Milind | yes |
| 19 | 2026-09-07 | orientation-archive-link-2 | `sha256:f13a1f67fec900b593d1be670a2f7351f57a3bb297626127fcb17d73a05a09d9` | FAIL | FAIL | none | none | `f13a1f67fec900b593d1be670a2f7351f57a3bb297626127fcb17d73a05a09d9` | Milind | yes |
| 20 | 2026-09-07 | pr-review-working-scope | `sha256:f3c2d653142dbf976463c998afaf04abfb3a7b093f0e144be30a430665d3656b` | FAIL | FAIL | dimensions.security, policy.criteria.security | intentional_hardening | `f3c2d653142dbf976463c998afaf04abfb3a7b093f0e144be30a430665d3656b` | Milind | yes |

## Operator Decision

Approved by Milind on 2026-09-08. Production release enforcement is authorized.
