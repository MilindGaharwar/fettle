---
fettle-work-item: true
id: p53-consistency-contracts
status: done
scope:
  - fettle/
  - tests/
spec: change-integrity-implementation-plan
---

# P53/SC1 — frozen state-consistency contract schema

## Resolution
fettle/state_consistency.py: ConsistencyContract identity via canonical digest excluding runtime/redaction keys; header/scope/consistency/comparator/observer validators with unknown-key rejection; TEMPLATE_V1; lint_contract_text. No execution code (runners are SC3+).
