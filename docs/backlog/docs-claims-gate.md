---
fettle-work-item: true
id: docs-claims-gate
status: done
scope:
  - tests/test_doc_claims.py
  - docs/engagement/TODO.md
spec: improvement-plan
---

# Docs-claims gate — executable predicates for documentation claims

First enforcement targets (known drift, double-confirmed by GLM review):
1. TODO.md marks Stage-5 S5.5 web surface `[x]`; the predicate checks that the
   installed capability probe exposes `web` exactly when Playwright is present.
2. README claims mutation replay and survivor enforcement; the predicate checks
   that `.github/workflows/mutation.yml` requires replay preparation and replay
   jobs before the authoritative `mutation evidence` aggregate.

Pattern: tests encode doc claims as code-reality predicates; new high-value
claims get predicates incrementally. Advisory by nature (a red test, not a
hook block) until the predicate set matures.

## Done when

- Predicate for S5.5 exists and validates the shipped capability probe.
- Resolution lands (code or honest amendment) and the suite is green.
- Replay-gate↔README consistency predicate passes.

## Resolution

The tests now require both documentation claims to remain present instead of
silently skipping when wording drifts. They bind the S5.5 claim to the runtime
Playwright capability probe and the mutation claim to the required replay jobs,
preparation command, and authoritative aggregate.
