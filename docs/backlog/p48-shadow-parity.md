---
fettle-work-item: true
id: p48-shadow-parity
status: done
scope:
  - fettle/
  - tests/
spec: change-integrity-implementation-plan
---

# P48 slice 1 — shadow parity engine (semantic consumer)

## Resolution
Delivered fettle/graph_shadow.py comparing the ephemeral graph against the legacy semantic layer: matched link pairs, unexplained-narrower detection (acceptance requires zero), declared difference categories (traces/scopes/observes). CLI: fettle graph shadow --root. Digest-bound and advisory.
