# Mutation Quality Playbook

Fettle's mutation surface measures Python test strength with pinned mutmut
evidence. It is advisory by default. A full run is held-out verification, not a
debugging loop.

## Validation Funnel

1. Add a focused regression fixture for the behavior under test.
2. Run the relevant unit tests.
3. Check local readiness and canonicalize the engine vocabulary.
4. Replay the smallest changed scope.
5. Use a full run only after preflight and narrow replay succeed.

```bash
uv sync --extra dev
python -m pip install -r requirements-mutation.txt
uv run fettle doctor
uv run fettle mutation preflight
uv run fettle mutation run --changed
```

Set `enabled = true` under `[mutation]` in `.fettle.toml` before preflight.
Python with mutmut 2.5.1 is the only supported mutation engine. Fettle's
polyglot adapters do not imply polyglot mutation support.

## Evidence Invariants

- Generated details must equal canonicalized details; rejected details and
  fingerprint collisions must be zero.
- Stable fingerprints are authoritative across runs. Native mutmut numeric IDs
  are run-local locators only.
- Missing, malformed, stale, partial, overlapping, or incompatible evidence
  cannot establish a score or pass enforcement.
- Native cache reuse requires an exact compatibility identity. Delete stale
  `.mutmut-cache` and `.fettle/mutation-cache` state rather than weakening
  validation.
- Independent calibrations may share one immutable preflight corpus, but never
  terminal outcomes. Run authoritative calibrations sequentially.
- Keep retained JSON bounded and secret-free. Do not add absolute paths,
  credentials, environment values, or raw unbounded process output.

## Exit Semantics

| Exit | Meaning | Next action |
|---|---|---|
| `0` | Complete successful evidence, or an explicit non-applicable result | Continue to narrow replay or review |
| `1` | Valid evidence failed configured mutation policy | Inspect survivors and strengthen tests or record reviewed classification |
| `2` | Configuration, tool, or evidence-integrity failure | Repair readiness/evidence; do not treat it as a test-quality verdict |

Use JSON when retaining or automating a result:

```bash
uv run fettle mutation preflight --json --output .fettle/mutation-preflight.json
uv run fettle mutation run --changed --json --output .fettle/mutation-report.json
uv run fettle mutation status --report .fettle/mutation-report.json
```

## Recovery

| Symptom | Recovery |
|---|---|
| Mutation disabled | Set `[mutation] enabled = true`, then rerun `fettle doctor` |
| mutmut missing or wrong version | Run `python -m pip install -r requirements-mutation.txt` |
| Source has no mapped tests | Add an exact `[mutation.test_mappings]` entry and verify the test path exists |
| Stale or incompatible cache | Remove `.mutmut-cache` and `.fettle/mutation-cache`, then rerun preflight |
| Parser drift or rejected detail | Retain the bounded JSON diagnostic and add an adversarial fixture before changing canonicalization |
| Fingerprint collision | Stop; retain both bounded records and fix identity logic before any full run |
| Timeout | Narrow source/test mapping first; do not reinterpret timeout as killed or survived |

Historical shard numbers and native IDs are provenance, never runtime policy.
See the [mutation UX contract](mutation-quality.ux-spec.md) for user states and
the [implementation plan](mutation-quality-implementation-plan.md) for evidence
and graduation criteria.
