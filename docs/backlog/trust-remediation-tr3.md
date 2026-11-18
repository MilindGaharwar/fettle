---
fettle-work-item: v2
id: trust-remediation-tr3
status: claimed
scope:
  - fettle/
  - tests/test_trust_remediation_tr3.py
  - tests/test_installed_hooks_e2e.py
  - tests/test_verify_gate.py
  - tests/test_ci_gate.py
  - tests/test_assurance_record.py
  - tests/test_assurance_integrity.py
  - tests/test_brief.py
  - tests/test_baseline.py
  - docs/behavior-map.md
  - docs/evidence-artifact-contract.md
  - docs/fettle.schema.json
  - docs/uat/trust-remediation-tr3.md
  - docs/backlog/trust-remediation-tr3.md
  - docs/completion/trust-remediation-tr3.json
  - docs/completion/evidence/trust-remediation-tr3/
spec: trust-remediation-implementation-plan
---

# TR-3 truthful verification

Implement design D-6 and package TR-3. A passing verification must come from
validated evidence for the current source and must prove that tests executed.
CI and status surfaces must apply the same identity and result rules.

## Acceptance criteria

- Findings V2, V3a, V4, V7, V10, V11, V13, E8, and P13 have retained red and
  green regression evidence.
- Every TR-3 UX scenario has an unskipped test.
- Stamp tampering is covered through both installed hook launch modes.
- Pytest counts are captured in hashed evidence; zero executed tests are red.
- Custom commands without counts are advisory UNKNOWN for the compatibility
  window.
- Verification defaults to full scope; explicit impacted scope stays partial.
- CI and brief reject stale or contradictory evidence.
- No mutation-tooling file changes.
