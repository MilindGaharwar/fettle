---
fettle-work-item: v2
id: p81-assurance-vector
status: done
scope:
  - fettle/assurance.py
  - fettle/cli.py
  - fettle/config.py
  - fettle/config_schema.py
  - tests/test_assurance_record.py
  - tests/test_cli.py
  - tests/test_config_schema.py
  - docs/assurance-policy.ux-spec.md
  - docs/uat/assurance-policy.md
  - docs/assurance-record-plan.md
  - docs/fettle.schema.json
spec: assurance-record-plan
---

# P81 — Assurance vector + sufficiency policy

Formal vector over the record's dimensions; release policies as
machine-checkable rules (e.g., production requires authorization=PASS,
policy_integrity=PASS, behavior=PASS, provenance=COMPLETE). Render the
"Why should I trust this change?" explanation. Security dimension joins
here.

## Resolution

Implemented on `p81-assurance-policy`: named release policies evaluate exact
assurance-vector statuses, malformed policy fails closed, retained security
review results join the vector, and human/JSON CLI output exposes the same
evidence-linked decision. Repository-wide completion validation passes after
refreshing P54/P55 evidence against the same final-tree full-suite run.
