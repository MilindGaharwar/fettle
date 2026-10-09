# Staged-preflight accounting verification

This record applies to the accounting repair based on candidate
`abed35141a0734b46f753e914d9450265e5a34ee` and retained run
`37795579761/1`. It does not admit that cancelled run or authorize reuse of its
40 reports.

## Accounting interpretation

The figures produced from a live observation are conservative exposure bounds
through that observation time. They are not predictions of final job duration.
Later execution can legitimately increase cumulative usage.

Each monitor retains the raw jobs response, observation timestamp, and computed
accounting result. Every later sample consumes all earlier valid samples as an
identity-bound floor. Sender, aggregate-launch, and terminal reconciliation
consume the retained monitor envelope. Terminal metadata is retained separately
as `terminal_reconciled_runner_minutes`; it cannot lower the effective
`estimated_runner_minutes` or erase the historical observations.

## Acceptance environment

- Interpreter: CPython 3.12.13
- Interpreter invocation: `uv run --no-sync python` from the locked repository environment
- Fettle: repository package `finefettle 1.13.1`
- Semgrep: 1.179.0
- Ruff: 0.16.10
- pytest: 9.1.1
- `uv.lock` SHA-256: `ac5a08e9e9da15de0a1742909affbbe927d72514b46dabc2564753fb366bcfdc`
- `requirements-mutation.txt` SHA-256:
  `c00bd24f7b87c160202ad3b3b2f14f7521ea4e88582d032a7805a584f69e9d46`

Repository ruleset SHA-256 values:

- `rules/go-antipatterns.yml`: `10d467e7fba955ed85adad05e8891c660172f91bbb90539bd594aafaedca96b5`
- `rules/llm-antipatterns.yml`: `e5745933820b92a849fa8bc8a56cd6d67125f981f83c64adb5c097cdfd87bb0f`
- `rules/security.yml`: `7cf0458335c92ece045079153eb49d3b3dc6d06b1b1a6e83b7d0bff40c15117e`
- `rules/ts-antipatterns.yml`: `0a92540e31561607e010da766e159e8981378f4ec87da2c8f24146dae3ff672e`

## Global scan discrepancy

The separately installed global `fettle 1.12.3`, running under CPython 3.14.6
with Semgrep 1.168.0, reports three `sql-fstring` errors at
`fettle/init_cmd.py:343`, `tests/test_rules.py:247`, and
`tests/test_rules.py:263`. Its bundled `llm-antipatterns.yml` SHA-256 is
`66d8e7cbd24dfa55ff34269f51862ef9ebaf3f44cdc3953c0018c1016921e6a0`
and contains a broader regex than the repository's current security rule.

The two affected files are byte-identical to candidate `abed351…`. Both
Semgrep 1.168.0 and 1.179.0 produce zero findings when given the repository's
current narrow `rules/security.yml`. The discrepancy is therefore bundled
ruleset/package drift, not source drift or a demonstrated engine-version
difference. No finding is suppressed or changed by this repair.

## Captured fixture privacy

The four byte-identical GitHub jobs responses were checked for authorization
headers, bearer/token/secret/password fields, private keys, GitHub token forms,
and email addresses. None were found. The retained data contains public
repository, workflow, job, timing, and hosted-runner metadata only. No fixture
transformation was required; original SHA-256 values remain the fixture
provenance boundary.
