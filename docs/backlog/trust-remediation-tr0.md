---
fettle-work-item: v2
id: trust-remediation-tr0
status: claimed
scope:
  - .github/workflows/mutation-pr.yml
  - tests/test_ci.py
  - tests/test_doc_claims.py
  - tests/test_installed_hooks_e2e.py
  - tests/fixtures/agent_payloads/
  - fettle/host-capabilities.json
  - docs/trust-remediation-implementation-plan.md
  - docs/trust-remediation.ux-spec.md
  - docs/plan-index.md
  - docs/backlog/trust-remediation-tr0.md
  - docs/completion/trust-remediation-tr0.json
  - docs/completion/evidence/trust-remediation-tr0/
  - docs/engagement/TODO.md
spec: trust-remediation-implementation-plan
---

# TR-0 baseline harness and required-check containment

Execute the registered installed-hook commands in both launch modes, record
host failure-mode capabilities, and contain M5 by separating an ordinary label
no-op from the exact required `mutation evidence` check name.

## Resolution

In progress. The executable harness covers all four hosts in plugin and
installed-bridge launch modes. Official-source host findings and the probe that
confirmed M5 are retained under
`docs/completion/evidence/trust-remediation-tr0/`. Contract tests confirm the
workflow gives ordinary label no-ops a distinct aggregate name while preserving
`mutation evidence` for normal and authorizing-label runs. Resolution remains
pending until the one-time live pull-request containment probe passes.
