# Stage 8 — Remote CI verification gate (`[gates.ci]`)

## Why this stage exists (incident)

Remote CI was red for **eight consecutive runs** (Stages 3–7) while every
local pre-push hook stayed green. Root cause: subprocess-style CLI tests
spawn `python -m fettle.cli` with `cwd=tmp_path`; the local venv had an
editable install, the CI checkout did not → `ModuleNotFoundError`. The
fix was one line in `ci.yml` (`pip install -e .`), but the process
failure was structural: *"local pre-push green" was treated as done, and
nobody looked at the remote verdict.* Stage 8 makes that impossible to
repeat — Fettle itself now refuses to consider a session finished while
a pushed commit's remote CI verdict is unverified or red.

## Design — two worlds (same pattern as verify/coverage gates)

- **Minutes-world**: `fettle ci status|wait` queries GitHub Actions for
  HEAD's runs (gh CLI first, REST fallback via urllib with optional
  `GITHUB_TOKEN`) and writes a stamp to `.fettle/ci-status.json`
  (`{ok, sha, overall, runs, reproduce, error, ts}`). `wait` polls up to
  `timeout_s` (900) every `poll_s` (15). Query failures and no-runs are
  distinct, explicit states — never silently green.
- **Milliseconds-world**: a PostToolUse hook (`ci_push_record`, order 45)
  records every `git push` in the session (`pushes.jsonl` in state dir).
  The Stop gate (`ci_gate`, order 53, 100 ms budget) fires only if the
  session pushed, then checks stamp existence, sha match, freshness
  (stamp newer than push), and verdict. Any gap → advisory/block with
  the exact problem and `Run: fettle ci wait`.

## Failure ingest finally has a caller

On a red run, `_ingest_failure` pulls `gh run view --log-failed`,
classifies via `ci_ingest.classify_failure`, stores history via
`store_failure`, and surfaces `ci_diagnose.diagnose_failure(...)`'s
reproduction command in the stamp and gate message. `ci_ingest` /
`ci_diagnose` existed since v0.5.0 with no production caller — closed.

## Decisions

- **OFF by default, advisory-first** — consistent with every other gate.
  Fettle's own repo enables `enforce` (dogfood; see `.fettle.toml`).
- `cancelled` is **not** green; `skipped`/`neutral` are.
- Push detection regex tolerates option tokens (`git -C x push`,
  `git --no-verify push`) but not arbitrary words (`git status && echo
  push` does not match — caught by test, regex tightened).
- Stamp is repo-local (`.fettle/`), push log is session-scoped (state
  dir) — a push in session A never haunts session B.

## Evidence

- 31 tests in `tests/test_ci_gate.py` (summarize, remote parsing, stamp
  lifecycle, push recording, all five Stop-gate failure modes, registry
  wiring, CLI exit codes 0/1/2).
- Live smoke: `fettle ci status` on this repo → `✓ CI success — 8195fe3`.
- Config schema regenerated; consistency pins green.

## Standing rule (also in operator memory)

After **every** push: `gh run watch --exit-status $(gh run list --branch
main --limit 1 --json databaseId --jq '.[0].databaseId')` — now enforced
in-product by this gate.
