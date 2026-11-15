---
fettle-work-item: v2
id: trust-remediation-tr2
status: claimed
scope:
  - fettle/
  - tests/test_trust_remediation_tr2.py
  - tests/test_installed_hooks_e2e.py
  - tests/test_installed_artifact_contract.py
  - tests/test_mutation_test.py
  - tests/test_config_protect.py
  - tests/test_config_schema.py
  - tests/test_policy_layers.py
  - tests/test_policy_remote.py
  - tests/test_trace.py
  - docs/CONFIG.md
  - docs/MULTI-AGENT.md
  - docs/behavior-map.md
  - docs/fettle.schema.json
  - docs/uat/trust-remediation-tr2.md
  - docs/backlog/trust-remediation-tr2.md
  - docs/completion/trust-remediation-tr2.json
  - docs/completion/evidence/trust-remediation-tr2/
spec: trust-remediation-implementation-plan
---

# TR-2 control plane and policy floors

Protect policy, evidence, state, and host hook configuration from in-session
changes. Apply monotonic enforcement floors, retain ignored weakening attempts,
fail closed for unavailable declared remote policy, and derive policy-integrity
assurance from session-start evidence.

## Resolution

Implementation and non-mutation verification are complete. Completion remains
blocked because the configured mutation preflight reached its 7,200-second
deadline, so no narrow replay was authorized.
