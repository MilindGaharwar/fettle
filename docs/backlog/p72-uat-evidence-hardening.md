---
fettle-work-item: true
id: p72-uat-evidence-hardening
status: done
scope:
  - fettle/uat/artifacts.py
  - fettle/uat/session.py
  - fettle/uat/reconcile.py
  - tests/test_uat_artifacts.py
spec: uat-strength-plan
---

# P72 — UAT evidence hardening (trust floor)

## Resolution

Sessions now retain a per-scenario observation artifact bundle
(`.fettle/uat-artifacts/<scenario>.json`: verbatim transcript block,
content hash, surface, capture time) via `fettle.uat.artifacts`. Session
reconciliation (`reconcile_session`) requires these artifacts: a CONFIRMED
verdict without a retained artifact degrades to INDETERMINATE ("claimed
match but no observation artifact"), and a transcript that drifts from its
captured artifact hash is INDETERMINATE even when the text still claims a
match. Non-confirming verdicts are unaffected; direct `reconcile()` calls
remain backward compatible. Contract coverage in
tests/test_uat_artifacts.py (6 tests incl. tampered-transcript drift).

Scope note: web-surface capture (screenshots/a11y trees) arrives with P74;
CLI/API/library surfaces capture verbatim-block + hash artifacts today.
