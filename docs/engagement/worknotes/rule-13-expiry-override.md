# Work note — Rule 13 expired-candidate override

## Contract

Rule 13 remains fail-closed when successful advisory candidates exist but no
identity-bound artifacts download. The guard records the candidate run IDs and
exits 2 unless an operator starts an attributable authorization run by applying
the `mutation-full-matrix-authorized` label.

Authorization exists only on the resulting `pull_request` `labeled` event when
the event label has that exact name. The workflow records
`github.event.sender.login` as `authorized_by`. GitHub requires triage or higher
repository permission to apply labels, so permission to apply the label is the
authorization boundary; no separate permission API lookup is needed.

The label is not removed automatically. Reapplying it creates a fresh,
attributable run. A stale label has no effect on later `synchronize` events.

## Precedence and concurrency

Downloaded identity artifacts always take precedence and continue through
digest-bound selection. An empty candidate list uses the existing full-matrix
fallback without an override record. Only candidates with zero downloaded
identities can use the explicit override, which records the reason, candidate
run IDs, actor, and label in `advisory-reuse.json`.

The workflow listens for `opened`, `synchronize`, `reopened`, and `labeled`.
Non-authorizing label events use a separate `-label-noop` concurrency group and
skip every job, so applying an unrelated label cannot cancel a live advisory
matrix. Normal PR events and the authorizing label event retain the established
per-PR concurrency group.

## Boundaries

This change does not alter mutation scope, pass semantics, survivor handling,
qualification eligibility, candidate age selection, cron behavior, or D4.
Reuse remains advisory-only. The override authorizes fresh changed-scope
execution; it does not convert reused evidence into qualification evidence.

## Verification

Completed before delivery:

- `bash .github/scripts/mutation_reuse_download_guard.sh --self-test` — passed
  all six precedence and authorization cases.
- `shellcheck .github/scripts/mutation_reuse_download_guard.sh` — passed.
- `actionlint .github/workflows/mutation-pr.yml` — passed.
- Focused workflow contract — 3 passed.
- `uv run --no-sync pytest -q tests/test_ci.py` — 159 passed.
- `uv run --no-sync python .github/scripts/run_full_suite_parallel.py --workers 4`
  — all 219 test files passed.
- `uv run --no-sync fettle check --changed` — no issues found.
- `uv run --no-sync python -m fettle.cli completion validate` — all registered
  completion manifests validated.

The final path audit confirmed that `fettle/mutation_test.py` and every test file
other than `tests/test_ci.py` were untouched.
