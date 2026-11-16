# Scanner repair: six-check follow-up

16 November 2026. Scoped follow-up to the scanner repair on scanner compatibility repair `0555a8b`. The original checkout, its staged work and private histories are preserved. No rule suppression, sandbox permission change or production evidence refresh is included.

## Root causes and fixes

1. `test_module_cli_validates_reports` generated synthetic evidence with August timestamps, then invoked a subprocess using the real clock. The fixture expired; this was not a finding that installed host integrations had failed. Generate current UTC timestamps for this synthetic CLI fixture and add an explicit one-year-old case that must still fail with the stale-evidence message. Fixed-clock validator tests retain their deterministic historical dates. Production freshness checks and release records are unchanged.
2. Five native UAT cases used the test runner's uv-managed Python under the home directory. The unchanged sandbox allows the executable but denies its home-directory standard library. A direct probe returned `Failed to import encodings module` before any intended operation ran. A system-installed Python passed the same probe under the same policy. The new fixture qualifies the current interpreter, then a system interpreter, by executing a harmless positive control inside the actual sandbox. If neither starts, the test fails with an actionable diagnostic; it does not skip or widen permissions. Only the five affected cases use this qualified runtime. Their write/fork/network denial and timeout/output-limit assertions remain intact.

These are test-environment corrections. There is no reason to weaken the sandbox or misclassify interpreter startup failure as successful denial coverage. The earlier delivery record's shorthand “stale live evidence” describes the failed assertion; investigation identifies an expired synthetic fixture, not independently assessed live-host evidence.

## Validation and boundaries

- Before modification, the six failures were reproduced on both the repair branch and its unchanged upstream parent.
- Targeted suite: `pytest tests/test_installed_artifact_contract.py tests/test_uat_session.py tests/test_distribution.py tests/test_semgrep_compatibility.py tests/test_assurance_baseline.py -q -p no:cacheprovider`: **380 passed, 20 skipped**. Existing dedicated-VM/Docker opt-in qualifications were not enabled; their skips are retained, not counted as passes. All five affected native cases ran successfully on macOS.
- Full Fettle quality scan of the repair worktree: **pass, zero findings, zero tool errors**. Diff whitespace check passed. kgraph impact was inspected before the two test files were edited.
- Tests use a separate `XDG_STATE_HOME` because the existing private runtime trace is malformed. The original trace is preserved. This environment boundary does not skip tests or change scanner rules.
- The push requires the existing full-suite pre-push hook; no bypass is used. Successful local tests do not assert fresh installed-host certification, dedicated-VM restart qualification or Docker qualification.

Review scope: two test files and this record. The preceding scanner commit retains its bounded timeout, parser dependency floor and regression tests. Any unrelated work in the original Fettle checkout remains outside this branch.
