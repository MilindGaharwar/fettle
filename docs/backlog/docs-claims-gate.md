---
fettle-work-item: true
id: docs-claims-gate
status: open
scope:
  - tests/test_doc_claims.py
  - docs/engagement/TODO.md
spec: improvement-plan
---

# Docs-claims gate — executable predicates for documentation claims

First enforcement targets (known drift, double-confirmed by GLM review):
1. TODO.md marks Stage-5 S5.5 web surface `[x]` while
   `fettle.uat.session.DRIVABLE_SURFACES` excludes `web` — predicate must
   fail until either the code ships or the claim is amended honestly.
2. README claims a required mutation replay gate — predicate cross-checks
   `.github/workflows/mutation.yml` contains the replay preparation stage.

Pattern: tests encode doc claims as code-reality predicates; new high-value
claims get predicates incrementally. Advisory by nature (a red test, not a
hook block) until the predicate set matures.

## Done when

- Predicate for S5.5 exists and currently FAILS, forcing resolution.
- Resolution lands (code or honest amendment) and the suite is green.
- Replay-gate↔README consistency predicate passes.

## Resolution

Record how it was resolved.
