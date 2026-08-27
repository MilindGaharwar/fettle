---
fettle-work-item: true
id: p82-independence-computation
status: done
scope:
  - fettle/assurance.py
  - fettle/authorship_gate.py
spec: assurance-record-plan
---

# P82 — Independence computation

Join authorship of code vs tests vs verifying identity from P52 roles +
spawn lineage chains + work-item claims. independence ∈ {LOW, MEDIUM, HIGH,
UNKNOWN} with defined criteria. Feeds the assurance vector's independence
dimension (v1 is presence-based).

## Resolution

`fettle.assurance` now derives independence from retained `authorship_gate`
trace decisions, the verification stamp's session identity, common spawn
lineage, and a matching live work-item claim. `HIGH` requires distinct tester,
implementer, and verifier identities under one claimed lineage; `MEDIUM`
requires distinct implementation and test authors; same-session authorship is
`LOW`; missing, malformed, or incomplete evidence remains `UNKNOWN`. The
authorship gate records its validated effective role in the bounded trace.
