# Quality Gate Remediation Plan

Status: PROPOSED maintenance plan; no `fettle scan` alias is recommended

## 1. Objective

Restore a trustworthy repository quality gate by documenting and testing the
supported command, separating genuine defects from rule/fixture noise, and
ratcheting new findings without laundering existing findings into a permanent
unreviewed baseline.

The canonical public command is `fettle check --all`. The repository already
uses it in command prompts, examples, and CI templates. `fettle scan` is not a
documented CLI and should not be added solely to satisfy an outdated operator
instruction. Direct `scripts/quality_scan.py` remains an implementation/testing
entry point, not the preferred user contract.

## 2. Observed Baseline

On the inspected pre-merge worktree, `fettle check --all --json` scanned 406
Python files and returned 77 findings:

| Category | Count | Initial disposition |
|---|---:|---|
| `debug-print-statement` | 74 | Predominantly rule/scope false positives in CLI and output-rendering functions; inspect outliers individually |
| `sql-fstring` in `tests/test_rules.py` | 2 | Rule self-test fixture strings, not executed SQL; fixture-governance false positives |
| `F401` in `examples/assurance-loop/broken.py` | 1 | Intentional broken demonstration input; exclude only through explicit fixture/example policy |

The 74 print findings occur in 15 files, concentrated in `install.py`,
`ratchet.py`, and `suppressions_v3.py`. The rule currently recognizes only
`main`, `_print_human`, `_print_json`, and `_print_result`, while Fettle has many
legitimate command/render functions. Bulk replacing `print()` with logging would
damage CLI behavior and is not remediation.

## 3. Decisions And Tradeoffs

| Approach | Benefit | Risk | Decision |
|---|---|---|---|
| Add `fettle scan` alias | Makes one invalid instruction work | Expands public API and preserves ambiguity with `check` | Reject absent user demand |
| Baseline all 77 immediately | Fast green gate | Hides rule defects and intentional fixtures without provenance | Reject |
| Disable `debug-print-statement` globally | Removes 74 findings | Loses useful detection in library/runtime code | Reject |
| Narrow the rule to behavior, govern fixtures, fix real outliers, then baseline reviewed residuals | Trustworthy signal with limited change | Requires classification and rule tests | Adopt |

## 4. Work Packages

### QG-0: Freeze Command Contract (0.5 day)

Files:

- `docs/README.md`
- `commands/quality.md`
- `.opencode/commands/fettle-quality.md`
- `.github/prompts/fettle-quality.prompt.md`
- `tests/test_cli.py`
- `tests/test_workflows.py`

Tasks:

1. Search all maintained instructions for `fettle scan` and replace stale usage
   with `fettle check --all` only where it exists.
2. Add a CLI contract test that `check --all --json` is accepted and returns the
   documented schema.
3. Keep unknown `scan` behavior unchanged unless a compatibility consumer is
   identified.

Verification:

```bash
python3 -m pytest tests/test_cli.py tests/test_workflows.py -q
```

### QG-1: Classify Every Finding (0.5-1 day)

Files:

- `docs/quality-gate-findings.md` (temporary review register, new)

Tasks:

1. Capture canonical JSON from `fettle check --all --json` on current `main`.
2. Assign each finding one disposition: production defect, intentional output,
   rule defect, test fixture, demonstration fixture, or justified suppression.
3. Record owner, reason, remediation, and verification for each group.
4. Treat any security finding in executable production code as highest priority;
   do not baseline it pending review.

Gate: counts reconcile exactly to scan output and every suppression has a stable
reason and narrow scope.

### QG-2: Repair Rule Precision (1-2 days)

Files:

- `rules/llm-antipatterns.yml`
- `tests/test_rules.py`
- `tests/fixtures/` as needed

Tasks:

1. Add positive fixtures proving debug prints in library code remain findings.
2. Add negative fixtures for explicit CLI/output functions based on structural
   behavior, not a growing filename allowlist where Semgrep can express it.
3. If structural matching is insufficient, use the narrowest reviewed path or
   function-name exclusions and document the remaining blind spot.
4. Exclude rule self-test source from project self-scan narrowly, or encode SQL
   samples so they remain valid Semgrep fixtures without being findings in the
   host test file.
5. Verify SQL f-string positives still fire on executable vulnerable examples.

Gate: true-positive fixtures remain detected; known CLI renderers and rule
self-tests no longer pollute the project scan.

Verification:

```bash
python3 -m pytest tests/test_rules.py tests/test_quality_scan.py -q
fettle check --all --json
```

### QG-3: Govern Intentional Examples (0.5 day)

Files:

- `.fettle-ignore` or the narrow existing scanner configuration surface
- `examples/assurance-loop/README.md`
- `tests/test_assurance_loop_example.py`
- `tests/test_quality_scan.py`

Tasks:

1. Confirm `examples/assurance-loop/broken.py` is intentionally broken and is
   exercised as such.
2. Exclude only that fixture from repository self-quality evaluation, without
   teaching installed Fettle to ignore user files named `broken.py`.
3. Add regression coverage proving ordinary example/application files remain in
   scan scope.

Verification:

```bash
python3 -m pytest tests/test_assurance_loop_example.py tests/test_quality_scan.py -q
```

### QG-4: Fix Genuine Production Findings (variable, estimated 0.5-2 days)

Files: only files classified as production defects in QG-1.

For each finding, preserve the owning output/API contract and add focused tests.
Do not convert user-facing stdout to logging unless the command contract requires
stderr or structured return values. Run security-focused tests for any SQL,
subprocess, path, deserialization, or credential finding.

Gate: no unreviewed error-severity production finding remains.

### QG-5: Establish Ratchet Policy (0.5-1 day)

Preferred outcome is a zero-finding repository scan after QG-2 through QG-4. If
reviewed legacy findings remain, create a root-relative baseline only for those
specific findings and record owner, rationale, and removal target. CI runs:

```bash
fettle check --all --baseline
```

and separately validates baseline shape and drift. New findings fail according
to configured severity. Baseline updates require review and may not be automatic
on CI failure.

Because `scan_project()` currently uses compatibility wrappers that print scanner
failures and return empty findings, QG-5 must also verify the public CLI cannot
map a missing, timed-out, malformed, or failed required scanner to a clean pass.
Reuse `execute_required_scanners()` or propagate structured status rather than
inferring tool health from an empty finding list.

Files:

- `fettle/quality_scan.py`
- `fettle/cli.py`
- `.github/workflows/ci.yml`
- `tests/test_quality_scan.py`
- `tests/test_cli.py`
- `tests/test_ci.py`

Gate: required scanner failure exits 2/non-pass, findings exit 1 according to
severity policy, clean execution exits 0, and baseline suppresses only reviewed
identities.

## 5. Success Criteria

- `fettle check --all` is the single documented user command.
- Every original finding has a reviewed disposition; counts reconcile.
- Security and production defects are fixed, not suppressed.
- Rule self-tests and intentional broken examples are excluded narrowly with
  regression tests.
- The print rule still catches true debug output but no longer flags legitimate
  CLI rendering by default.
- Required scanner failure is fail-visible and cannot produce a clean result.
- The final full scan has zero unbaselined errors and no unexplained findings.

## 6. Verification And Rollback

```bash
python3 -m pytest tests/test_rules.py tests/test_quality_scan.py tests/test_cli.py tests/test_ci.py tests/test_workflows.py tests/test_assurance_loop_example.py -q
python3 -m pytest -q
fettle check --all
git diff --check
fettle completion validate
```

If a rule refinement causes false negatives, revert that rule change and retain
the reviewed findings while designing a narrower matcher. Do not recover by
global exclusion or by refreshing the baseline to current output.
