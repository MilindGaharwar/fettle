---
fettle-work-item: true
id: behavior-decision-table
status: open
scope:
  - docs/behavior-map.md
  - tests/test_doc_claims.py
  - AGENTS.md
spec: improvement-plan
---

# "Where new behavior goes" decision table

Adopted from dsh's extension cookbook table: one row per goal → exact
mechanism (which dispatch entry, gate category, provider seam, or program),
removing the biggest onboarding unknown.

## Done when

- `docs/behavior-map.md` covers: add a gate, add a check, add an agent host
  transport, add a workspace adapter, add a mutation provider target, add a
  UAT surface driver, add an evidence consumer, add a consistency contract
  type.
- Drift predicate: every command in the CLI dispatch registry appears in
  the table (doc-claims pattern).
- Linked from docs/README.md and AGENTS.md.

## Resolution

Record how it was resolved.
