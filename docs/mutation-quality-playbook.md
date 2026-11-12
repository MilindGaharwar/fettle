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

## D4 dispatch preconditions

The standalone `.github/workflows/mutation-d4.yml` execute graph admits a run only when these checks pass:

- `candidate_sha` equals the workflow revision and `git status --porcelain` is empty (`d4-admit`).
- `d4_id`, `d4_preflight_run_id`, and `d4_runner_minute_ceiling` are supplied; calibration, stage, and resume inputs are empty (`d4-admit` and `tests/test_ci.py`).
- The retained preflight contains exactly 256 ordered manifests, reconciled generated and canonical counts, zero collisions, and a byte-identical current `corpus-identity.json` (`build_d4_corpus_identity` and `d4-admit`).
- The supplied ceiling is at least the ledger's nearest-rank per-shard P95 total plus the 1,200-minute cancellation reserve (`evaluate_d4_admission` and `tests/test_mutation_test.py`).
- The `gate` phase runs only the real-path synthetic `d4-gate`; execute also requires that gate before the 256-shard matrix starts. Its report is retained as `d4-gate-report-<run_id>-<attempt>` (`d4-gate`, `d4-shards`, and `tests/test_ci.py`).
- Aggregation accepts exactly 256 fresh same-run reports from attempt 1 or exactly one bounded failed-job rerun (attempt 2); any later attempt or a duplicate completed shard whose container digest matches sealed `corpus-identity.json` is rejected with missing, malformed, checkpoint-only, reused, stale, or unrelated lineage (`aggregate_d4_shards` and `tests/test_mutation_test.py`).
- Retention installs the pinned mutation environment and invokes Fettle through `uv run --no-sync`; the CLI builds the evidence index from retained files, appends provider artifact IDs, re-digests it, and the job mirrors the index plus retained-file digests to `evidence/d4`. Any mirror or policy failure remains a non-pass (`d4-retain` and `tests/test_ci.py`).

On every pull request, `.github/workflows/mutation-pr.yml` binds preparation to
the exact head, base, and merge base. A mutation-relevant scope automatically
dispatches the changed-scope shard matrix. Each shard consumes its digest-bound
manifest and publishes an attempt-scoped artifact; a failed job may receive one
bounded failed-job rerun, but the aggregate must select exactly one compatible
completed attempt for every shard. A retry timeout, missing attempt, or
conflicting completed attempt remains exit 2 and cannot establish a score or
pass.

`fettle/mutation_test.py` aggregates this pull-request evidence with
`aggregation_mode: "advisory"` and `qualification_eligible: false`. Advisory
success therefore confirms complete, compatible changed-scope execution only.
It does not establish a full-corpus baseline, waive survivors, or qualify a
ratchet. If preparation proves there is no mutation-relevant Python scope, the
workflow dispatches no shards and publishes identity-bound `not_applicable`
evidence with `passed: true`. Missing or malformed zero-scope identity remains
non-pass.

Advisory cost follows the configured partition contract: changes to engine files
such as `fettle/mutation_test.py` or `fettle/staged_preflight.py` always cost the
full matrix; non-engine source changes cost the shards that contain that source;
documentation-only changes cost zero shards.

Protected `main` requires both `CI required` and `mutation evidence`. It also
requires linear history, so approved changes land through a linear merge method;
passing source checks do not authorize a direct protected-branch push. Full-scope
qualification remains a separate, fresh, held-out path and never reuses advisory
terminal outcomes.

```bash
pipx install finefettle
fettle doctor
fettle mutation preflight
fettle mutation run --changed
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
- Pull-request shard and aggregate artifacts are scoped by workflow run attempt.
  Never select a report by shard number alone or combine incompatible attempts.
- Native cache reuse requires an exact compatibility identity. Delete stale
  `.mutmut-cache` and `.fettle/mutation-cache` state rather than weakening
  validation.
- Independent calibrations may share one immutable preflight corpus, but never
  terminal outcomes. Run authoritative calibrations sequentially.
- Advisory pull-request aggregates are always qualification-ineligible, even
  when all changed-scope shards pass.
- A failed staged-preflight run remains non-pass. Its successful shard reports may
  contribute to a separately identified recovery corpus only when immutable artifact
  hashes, candidate/runtime/dependency/policy identity, complete manifest topology,
  exact-once shard origins, and cumulative original-budget accounting all validate.
  Never rewrite the source run as successful or describe recovery as one uninterrupted
  run.
- A failed or timed-out calibration shard remains non-pass. Each calibration stage may
  seed at most one sparse continuation, and only when every selected checkpoint has
  positive unfinished work and explicitly records `incomplete_reason:
  deadline_exhausted`. The source provenance must prove it is the initial same-stage
  run, the terminal producer job must have the exact reviewed
  producer/checkpoint-upload/report-upload outcomes, and provider run, attempt,
  artifact, candidate, manifest, calibration, preflight, corpus, environment, and
  cumulative accounting provenance must all validate. This applies independently to
  stages 1, 2, and 3; a continuation may not itself be continued. A locally calculated
  extracted-file hash does not establish artifact origin, and the exception never
  replaces a successfully published canonical report. See
  `docs/calibration-budget-contract-amendment.md` for the retained historical
  budget and run limits; it is not the current pull-request evidence path.
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

The PR advisory retries manifest downloads and shard-report uploads twice with
short backoff. Exhausted retries still fail without synthesizing evidence;
long provider outages require the bounded failed-job recovery path.

| Symptom | Recovery |
|---|---|
| Mutation disabled | Set `[mutation] enabled = true`, then rerun `fettle doctor` |
| mutmut missing or wrong version | Upgrade or reinstall the complete package with `pipx upgrade finefettle` |
| Source has no mapped tests | Add an exact `[mutation.test_mappings]` entry and verify the test path exists |
| Stale or incompatible cache | Remove `.mutmut-cache` and `.fettle/mutation-cache`, then rerun preflight |
| Parser drift or rejected detail | Retain the bounded JSON diagnostic and add an adversarial fixture before changing canonicalization |
| Fingerprint collision | Stop; retain both bounded records and fix identity logic before any full run |
| Timeout | Narrow source/test mapping first; do not reinterpret timeout as killed or survived |

Historical shard numbers and native IDs are provenance, never runtime policy.
See the [mutation UX contract](mutation-quality.ux-spec.md) for user states and
the [implementation plan](mutation-quality-implementation-plan.md) for evidence
and graduation criteria.
