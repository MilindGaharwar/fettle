---
fettle-work-item: true
id: p81-assurance-vector
status: done
scope:
  - fettle/assurance.py
  - tests/
spec: assurance-record-plan
---

# P81 — assurance vector + sufficiency policies

## Resolution
evaluate_vector() evaluates the record against release policies; render_assurance() produces the 'Why should I trust this change?' CLI output. DEFAULT_RELEASE_POLICY pins authorization, policy_integrity, behavior, and provenance.
