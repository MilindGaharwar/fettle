---
fettle-work-item: v2
id: assurance-integrity-ai1
status: claimed
scope:
  - docs/assurance-integrity-implementation-plan.md
  - docs/assurance-integrity.ux-spec.md
  - docs/plan-index.md
  - docs/backlog/assurance-integrity-ai1.md
  - docs/uat/assurance-integrity-ai1.md
  - fettle/assurance.py
  - fettle/cli.py
  - fettle/verify_gate.py
  - fettle/ci_gate.py
  - tests/test_assurance_record.py
  - tests/test_assurance_integrity.py
  - tests/test_cli.py
spec: assurance-integrity
---

# Assurance Integrity AI-0/AI-1

AI-2 and AI-3 were authorized after the AI-1 red baseline was accepted. The
claimed item now covers shared assessment context and canonical verify/CI
consumption; mutation, UAT, provenance, authorization, and security hardening
remain out of scope.

## Acceptance Criteria

- The authority, compatibility, applicability, and validity mappings are frozen
  before production behavior changes.
- Final-boundary regression tests expose raw verify, CI, mutation, provenance,
  security, caller-supplied scope, and portability false-pass paths.
- Each regression fails against the current implementation for the intended
  reason.
- No production Python file changes in this milestone.

## AI-2 Acceptance Criteria

- One working source snapshot and one effective layered-policy digest are
  resolved per record.
- Scope is derived from Git state; `changed_files` cannot establish authority.
- Subject, policy, scope, and stage identities are portable across equivalent
  checkout locations.
- Producer acceptance behavior remains unchanged until AI-3 and later.

## AI-3 Acceptance Criteria

- Raw verify and CI reports remain diagnostic and cannot establish `PASS` or
  `FAIL` without valid canonical sidecars.
- Verify and CI canonical evidence is validated by producer-owned logic against
  its exact source, policy, scope, producer, completeness, and stamp reference.
- Valid canonical passes establish `PASS`; valid canonical violations remain
  `FAIL`; invalid or indeterminate evidence becomes `UNKNOWN` with a recovery
  command.
- Existing schema-v1 record and CLI shapes remain additive and compatible.

## Verification

AI-1 retained the expected failure list. For AI-3, run
`uv run pytest tests/test_assurance_integrity.py -q`; the shared-context and
verify/CI tests pass while the mutation, provenance, and security gaps remain
strict `xfail`. Run the assurance, verify-gate, CI-gate, and CLI suites
separately to prove v1 compatibility.
