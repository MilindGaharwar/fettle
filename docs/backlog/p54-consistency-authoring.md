---
fettle-work-item: v2
id: p54-consistency-authoring
status: done
scope:
  - fettle/state_consistency.py
  - fettle/cli.py
  - tests/test_state_consistency.py
  - tests/test_cli.py
spec: state-consistency-implementation-plan
---

# P54/SC2 - state-consistency discovery and authoring

## Resolution

Contracts now retain explicit command adapter manifests and phase references.
Discovery is deterministic, skips tool-owned directories, and rejects duplicate
IDs. `consistency lint --executable` checks run readiness without executing
repository code, while `consistency list --json` provides stable selection data.
Adapter manifests accept only argv arrays, repository-relative working
directories, environment variable names, bounded timeouts, and `json-v1`
output.
