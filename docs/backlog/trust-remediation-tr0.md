---
fettle-work-item: v2
id: trust-remediation-tr0
status: done
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

Completed. The executable harness covers all four hosts in plugin and
installed-bridge launch modes. Official-source host findings and the probes that
confirmed and contained M5 are retained under
`docs/completion/evidence/trust-remediation-tr0/`. Contract tests keep the exact
`mutation evidence` name conditional and forbid a static protected name. The
one-time pull request #76 probe confirmed that a non-authorising label event
created no check named exactly `mutation evidence`; GitHub displayed the skipped
aggregate under the unevaluated expression text.
