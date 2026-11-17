# Documentation publication validation — 16 November 2026

Base: `461e73b89d33bfc2d80c945e959be74dafe5f3ab` on
`audit/hardening-acceptance`, remote `MilindGaharwar/fettle`.
The eleven purpose groups change documentation only. No runtime, test, rule,
workflow, dependency, executable mode or existing completion evidence is changed.
The state-consistency companion plan receives a narrow dependency/scope correction.

## Scope and preservation

The original dirty checkout remains untouched: 54 inventoried files, their modes,
the complete Git index and porcelain status are compared before and after work.
All 117 protected a private external project packet/answer files also match the retained hashes.
Preparation uses an isolated checkout of the verified remote, with explicit
file lists for each commit. Private histories and runtime files never enter the
staged lists. The original staged audit histories stay local and unchanged.

The old audit records would replace newer acceptance evidence and fail privacy
scrub on 25 lines. They are superseded, not imported or silently sanitized.
Old mutation/scanner/test snapshots are already upstream or superseded; importing
them would remove newer repairs. The unexplained executable-mode removals are
not adopted. The newer remote audit row, completion JSON and evidence stay intact.

## Completed checks

- `python -m fettle.quality_scan --root . --json`: 427 files, zero findings,
  warnings, errors or tool errors in the trusted execution environment.
- `python -m pytest tests/test_doc_claims.py tests/test_completion.py
  tests/test_work_items.py tests/test_plan_validator.py -q`: 99 passed.
- `python -m fettle.cli completion validate --json`: all records valid and
  complete under their recorded contracts. Audit acceptance remains bounded;
  mutation qualification is still `CLOSED_NON_PASS`.
- `python -m fettle.cli config --validate`: passed.
- `python -m fettle.cli check --changed`: no changed Python files to check;
  this is not a substitute for the full scanner above.
- Existing `fettle.plan_validator.validate_plan`: the eight changed plans using
  its WP table format pass. The formal plan initially reproduced 11 pre-existing
  missing-Method failures. Added explicit methods, named failure regressions,
  bounded commands and unknown-state observations; the validator was unchanged.
- Local Markdown target and heading-anchor checks pass (284 links across the
  reviewed group files at final preparation). External URLs and every
  historical research/run assertion were not revalidated; the affected proposals
  state those limits. Each commit also receives an index-only link check so
  unstaged future documents cannot conceal broken references.
- `bash fettle/scrub_audit.sh`: clean on the publication candidate. Additional
  selected-file checks found no private absolute user paths or raw conversation
  markers. This is a bounded privacy review, not a guarantee against every secret.
- `git diff --check`: clean. Per-group semantic matrices separate proposals,
  fixtures, live evidence, authority, non-goals and failure cases.

## Environment failures and regression comparison

The first sandboxed scanner failed because Semgrep could not access certificate
trust anchors. The unchanged command passed with system trust access. No rule,
ignore pattern, baseline or finding was suppressed.

An initial broad test attempt was interrupted after six failures, 463 passes and
11 skips. It used the host PATH/state: a test read malformed pre-existing trace
state, subprocesses could not find `python`, and local CI/monitor checks failed.
The suite was then run with the tool virtualenv on PATH and disposable XDG state,
cache and configuration directories. Private state was not edited. All runtime
and test files involved are byte-identical to the remote baseline.

That run was interrupted after 2,798 passes and one 60-second Semgrep subprocess
timeout with no output. The failing promise-rule integration test passed in an
isolated rerun (3.53 seconds). The untouched remote baseline passed all 172 tests
in `test_project_rules.py`, `test_assurance_baseline.py` and `test_ci.py` with the
same isolated setup. These results support an environment-sensitive timeout,
not a documentation-induced parser or rule defect; they do not prove a unique
network cause. The timeout remains part of the record.

The remaining collected tests are run without repeating completed cases.
`SEMGREP_SEND_METRICS=off` and `SEMGREP_ENABLE_VERSION_CHECK=0` disable optional
telemetry/version traffic only; rule selection, analysis, findings and test
assertions remain intact. All 2,208 remaining collected cases were run: 2,188
passed and 20 were skipped by existing explicit opt-in gates (one dedicated-VM
restart case and 19 prepared Docker qualification cases). No new skip was added.
Across the split collection and isolated timeout rerun, 4,987 distinct tests
passed; the 20 live qualification cases were not executed. This is not a claim
of one uninterrupted green full suite or completed VM/container qualification.
The initial failed/interrupted runs remain failures, not rewritten passes.

## Impact and publication procedure

`kgraph index --no-embed` refreshed the isolated checkout's static graph with
zero parser diagnostics. `kgraph impact docs/plan-index.md --json` returned a
fresh index and no parse failures at final preparation. Markdown impact is primarily direct file
scope; the graph does not prove semantic completeness, runtime behavior or
cross-document consistency. The per-group manual matrices supply that review.
No embedding or runtime change is needed for these Fettle planning records.

Each group is staged by explicit filename, compared with its reviewed manifest,
checked for whitespace and local links using the Git index (not future unstaged
files), and committed with DCO sign-off using the repository's existing signing
identity. Each normal fast-forward push is checked with `git ls-remote`; no force
push or remote history rewrite is permitted. Local push receipts retain the
individual commit IDs and observed remote tips without publishing private logs.

## Limits

This is documentation publication, not feature delivery. No live model study,
formal qualification, mutation campaign, active skill installation, D4 run,
main-branch merge or release is authorized or claimed. Per-program evidence and
execution gates remain. Generic home-relative installation examples are retained;
no private prompt/answer bodies or raw runtime logs are published.

## Subsequent live qualification

The [qualification follow-up](qualification-followup.md) records execution of all
20 previously skipped VM/Docker cases at candidate `4030de0`: all passed.
The historical skips above remain the actual results of the earlier suite.
Repeated Semgrep probes passed, but the earlier intermittent timeout remains
unexplained; no runtime fix or timeout relaxation was justified.
