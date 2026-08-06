# TLA+ Formal Verification Specs

Formal models of Fettle's critical concurrent/protocol subsystems, verified
through exhaustive state-space exploration via the TLC model checker.

## Specs

| Spec | Source | What it verifies |
|------|--------|-----------------|
| `PolicyCapsule` | `fettle/policy_capsule.py`, `fettle/capsule_guard.py` | Monotonic delegation, tamper detection, depth bounds |
| `WorkItemClaims` | `fettle/work_items.py`, `fettle/topology.py` | Claim mutual exclusion, footprint disjointness, stale reclamation |

## Prerequisites

- **Java 11+** — `brew install openjdk` on macOS
- **tla2tools.jar** — auto-downloaded by the runner script, or manually from
  https://github.com/tlaplus/tlaplus/releases

Optional for interactive exploration:
- [TLA+ Toolbox](https://github.com/tlaplus/tlaplus/releases) (standalone IDE)
- [VS Code TLA+ extension](https://marketplace.visualstudio.com/items?itemName=alygin.vscode-tlaplus)

## Running

```bash
# All specs
./specs/tla/run-all.sh

# Single spec
./specs/tla/run-all.sh PolicyCapsule

# Direct TLC invocation
java -cp specs/tla/tla2tools.jar tlc2.TLC \
  -config specs/tla/PolicyCapsule.cfg \
  -workers auto \
  specs/tla/PolicyCapsule.tla
```

## Interpreting Results

TLC explores every reachable state and checks invariants at each one.

- **No violation found** — the property holds for all reachable states
  under the model parameters.
- **Invariant violated** — TLC prints the shortest trace (sequence of
  states) that reaches the violation. This is a concrete bug reproduction.
- **Deadlock detected** — the spec reached a state with no enabled actions
  and no termination condition. May indicate a missing fairness condition
  or a real protocol deadlock.

## Keeping Specs in Sync

These specs model the *protocol logic* of their source files. When changing:

- `fettle/policy_capsule.py` — check `PolicyCapsule.tla` invariants still hold
- `fettle/work_items.py` or `fettle/topology.py` — check `WorkItemClaims.tla`

The runner script is designed to be CI-friendly (exit 1 on any failure).
Add it to your CI pipeline to catch protocol regressions:

```yaml
- name: TLA+ verification
  run: ./specs/tla/run-all.sh
```

## Model Parameters

The specs use small model values for tractable exhaustive checking:

| Spec | Parameters | Approx. states |
|------|-----------|----------------|
| PolicyCapsule | 4 agents, 3 keys, depth=3 | ~50K |
| WorkItemClaims | 3 items, 3 sessions, 3 worktrees, 3 files | ~200K |

These are sufficient to find protocol bugs because the properties are
symmetric — a bug reachable with 16 agents is reachable with 4.

## Mutation Testing

To verify the specs *can* find bugs, try these mutations:

**PolicyCapsule — remove depth check:**
Change `Len(capsules[parent].lineage) < MaxDepth` to `TRUE` in `WriteCapsule`.
Expected: TLC finds `DepthBound` violation.

**PolicyCapsule — weaken merge:**
Change `StricterMode(parent_policy[key], local_policy[key])` to `local_policy[key]`.
Expected: TLC finds `MonotonicStrictness` violation.

**WorkItemClaims — remove lock:**
Change `AcquireLock` to always succeed regardless of `locked` state.
Expected: TLC finds `NoDuplicateClaim` or `LockMutualExclusion` violation.

**WorkItemClaims — allow unknown-scope parallelism:**
Change `Init` so `footprints` starts as `{}` instead of `Files`.
Expected: TLC finds `DisjointParallelism` violation (or `UnknownScopeConservative`).
