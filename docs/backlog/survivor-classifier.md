---
fettle-work-item: true
id: survivor-classifier
status: done
scope:
  - fettle/survivor_classify.py
  - tests/test_survivor_classify.py
spec: mutation-ratchet-decision
---

# Survivor classifier — enforcement bar for the mutation ratchet

Implements the revised re-entry path from docs/mutation-ratchet-decision.md:
raw survivor count is not a valid bar (equivalent/implementation-detail
mutants are unkillable without brittleness). `fettle/survivor_classify.py`
provides a versioned waiver registry (`schema_version: v1`, fingerprint-keyed,
classification ∈ {equivalent, implementation_detail}, mandatory reason +
decided_by, unknown-key tolerant YAML with precise findings) and
`classify_survivors(report, waivers)` splitting survivors into behavioral
(blocks enforcement) vs waived, with `enforce_ready` semantics.

## Done when

- Behavioral-only bar: `enforce_ready` true iff zero unwaived survivors.
- Malformed registries produce findings, never crashes or silent passes.
- Contract coverage in tests/test_survivor_classify.py (6 tests).

## Resolution

Shipped as above; seeded registry pending operator triage of the 64 ledger
survivors + cli.py cluster inventory.
