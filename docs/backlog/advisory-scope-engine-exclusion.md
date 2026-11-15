---
fettle-work-item: v2
id: advisory-scope-engine-exclusion
status: open
scope:
  - docs/backlog/advisory-scope-engine-exclusion.md
  - .fettle.toml
  - .github/workflows/mutation-pr.yml
  - fettle/config.py
  - fettle/mutation_test.py
  - tests/test_ci.py
  - tests/test_config_schema.py
  - tests/test_mutation_test.py
  - README.md
  - docs/CONFIG.md
  - docs/behavior-map.md
  - docs/engagement/TODO.md
  - docs/mutation-quality-playbook.md
  - docs/trust-remediation-implementation-plan.md
  - docs/trust-remediation.ux-spec.md
spec: trust-remediation
---

# Per-pull-request mutation engine exclusion

Implement owner decision D2 from 2026-11-15. Pull-request advisory preparation
omits `fettle/mutation_test.py` and `fettle/staged_preflight.py`; deliberate
full-corpus preparation remains unchanged. Retained evidence must name the
omitted prefixes, and the historical observed ledger remains untouched with
its known shard-index limitation assigned to finding M7 in TR-8.

## Acceptance

- Engine-only changes produce the existing zero-scope advisory outcome.
- Mixed changes produce full advisory partitions without either engine file.
- Empty configuration preserves prior pull-request behavior.
- Full-corpus manifest bytes and digests do not depend on the new key.
- Reduced-scope prepare, reuse, projection, selection, aggregation, retained
  identity, and job-summary contracts are exercised end to end.
