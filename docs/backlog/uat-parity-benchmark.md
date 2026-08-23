---
fettle-work-item: true
id: uat-p77-parity-benchmark
status: open
scope:
  - docs/uat/
  - tests/
spec: plan-uat-strength
---

# P77 — Seeded-defect parity benchmark (held-out verification)

Plan: `docs/hypothesis-tree-uat.md`

Build mutation-testing-for-UX: inject known defects into demo apps across
surfaces, run agent sessions and recorded human sessions over identical
seeds, and measure discovery rate, false-verdict rate, and coverage
accounting. This is the held-out instrument that decides "at par or
stronger" — no capability ships past advisory on vibes.

## Done when

- Benchmark harness reproduces discovery metrics from retained session
  evidence with canonical identities (same doctrine as mutation evidence).
- A published baseline table compares agent vs human sessions on ≥10 seeds;
  Phase gates unblock only when the false-verdict rate is zero and
  discovery rate meets the agreed threshold.

## Resolution

Record how it was resolved.
