---
fettle-work-item: v2
id: p55-consistency-runner
status: done
scope:
  - fettle/consistency_runner.py
  - fettle/state_consistency.py
  - fettle/cli.py
  - tests/test_consistency_runner.py
  - tests/fixtures/state_consistency/apps/
spec: state-consistency-implementation-plan
---

# P55/SC3 - bounded API/CLI execution kernel

## Resolution

`fettle consistency run [ID...]` executes repository-owned argv adapters in
setup, mutation, canonical-read, observer, and cleanup order. It validates all
paths and required environment names before mutation, uses isolated process
groups with per-adapter deadlines, drains output with a 64 KiB retention cap,
accepts only versioned JSON envelopes, redacts observed values to typed
fingerprints, and records source, dirty-tree, policy, contract, adapter, command,
and output identities. Cleanup runs after success, failure, timeout, malformed
output, or cancellation; cleanup failure remains separate and makes the run a
non-pass.

The committed `seeded-stale-read` fixture proves that canonical and stale
observer fingerprints remain distinct. P56a/SC4 now owns convergence and
stale/divergence decisions over this execution evidence.
