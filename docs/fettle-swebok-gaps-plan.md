# Fettle SWEBOK v4 Gap Coverage Plan

**Authored by:** Claude Opus
**Status:** Pending Sol review
**Total effort:** 20-27 hours across 5 work packages
**SWEBOK KAs addressed:** KA 7 (Maintenance), KA 6 (Operations), KA 8 (SCM), KA 5 (Testing), KA 1 (Requirements)

---

## Work Packages

### WP-X1: Technical Debt Dashboard (4-6 hrs)

Extend `/fettle:report` with debt quantification using data already captured in trace JSONL, ratchet.json, and lean markers.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Count TODO/FIXME/HACK markers across project source, trend vs. previous report | CODE | Unit test: fixture project with 5 TODOs → debt report shows count=5 |
| 2 | Count active suppressions (fettle:ignore, # noqa) and compute suppression debt | CODE | Unit test: file with 3 noqa markers → suppression_debt=3 |
| 3 | Compute complexity trend from ratchet.json history (rising/stable/falling) | CODE | Unit test: ratchet with 3 entries showing increasing avg complexity → trend="rising" |
| 4 | Report lean markers where upgrade trigger is now met (stale intentional debt) | CODE | Unit test: lean marker "upgrade when: > 100 users" with metric showing 150 → flagged as actionable |
| 5 | Aggregate into debt section of report output with A-E rating (per SQALE model) | CODE | Unit test: 0-2% debt ratio = A, 3-5% = B, 6-10% = C, 11-20% = D, >20% = E |
| 6 | Write failing test: project with known debt produces correct rating | TDD | Test fails before rating logic, passes after |
| 7 | Integration test: run full report on Fettle's own codebase, verify debt section present | INTEGRATION | `python scripts/report.py --debt` produces output with TODO count, suppression count, complexity trend, rating |
| 8 | Regression test: project with zero debt produces rating A and no false findings; project with only lean markers (intentional debt) reports them without inflating the rating | REGRESSION | Zero-debt fixture → rating=A with empty findings; lean-only fixture → markers listed but rating not penalized for intentional simplifications |
| 9 | Live verification: run debt report on Fettle itself | LIVE | `bash scripts/run.sh report.py --debt --root .` outputs debt section with TODO=0, suppressions counted, complexity trend from ratchet data |

---

### WP-X2: Deployment Safety Gate (4-6 hrs)

New PreToolUse(Bash) check detecting deploy/release commands and verifying safety preconditions.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Detect deploy commands: `kubectl apply`, `terraform apply`, `cdk deploy`, `docker compose up -d`, `fly deploy`, `git push heroku` | CODE | Unit test: each command pattern correctly identified |
| 2 | Pre-deploy verification: check session has recent test pass (from quality_gate test stamp) | CODE | Unit test: deploy after test stamp → allow; deploy without → advisory |
| 3 | Pre-deploy verification: check CHANGELOG.md modified in session (from edits.jsonl) | CODE | Unit test: deploy with CHANGELOG edit → allow; without → advisory |
| 4 | Pre-deploy verification: grep for health endpoint in source (must exist somewhere in project) | CODE | Unit test: project with `/health` route → passes; without → advisory |
| 5 | Pre-deploy verification: grep for debug flags in tracked files (DEBUG=True, console.log in non-test) | CODE | Unit test: production file with `DEBUG=True` → advisory |
| 6 | Write failing test: `kubectl apply` without any test run in session | TDD | Test fails before gate logic, passes after |
| 7 | Integration test: full dispatcher flow with deploy command after test stamp + CHANGELOG edit | INTEGRATION | `echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"kubectl apply -f deploy.yaml"}...}' \| python3 scripts/dispatcher.py` returns allow when all preconditions met |
| 8 | Regression/inversion test: non-deploy commands don't trigger; project with no source files produces degraded/unknown status for endpoint check (not crash); deploy with all preconditions met produces no advisory | REGRESSION | `ls -la` and `npm install` do not trigger; empty project with no routes → endpoint check returns unknown/degraded gracefully; deploy after all verifications pass produces clean allow |
| 9 | Live verification: attempt a deploy command in session and observe advisory | LIVE | `echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"fly deploy"},"cwd":"/tmp","session_id":"test"}' \| python3 scripts/dispatcher.py` returns advisory about missing preconditions |

**Config:**
```toml
[gates.deploy_safety]
enabled = false
mode = "advisory"
deploy_patterns = ["kubectl apply", "terraform apply", "cdk deploy", "fly deploy", "docker compose up"]
require_tests = true
require_changelog = false
require_health_endpoint = true
check_debug_flags = true
```

---

### WP-X3: CHANGELOG and Semver Enforcement (2-3 hrs)

Extend commit/tag handling to verify CHANGELOG has matching entry and version is valid semver.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Detect `git tag` commands in PreToolUse(Bash), extract version string | CODE | Unit test: `git tag v1.2.3` → extracts "1.2.3"; `git tag -a v2.0.0 -m "msg"` → extracts "2.0.0" |
| 2 | Validate semver format (MAJOR.MINOR.PATCH, optional pre-release) | CODE | Unit test: "1.2.3" valid, "1.2" invalid, "1.2.3-beta.1" valid, "v1.2.3" valid (strip v prefix) |
| 3 | Check CHANGELOG.md contains entry matching the tag version | CODE | Unit test: CHANGELOG with "## v1.2.3" and tag v1.2.3 → passes; tag v1.2.4 without entry → advisory |
| 4 | Check for BREAKING CHANGE in commits since last tag (via git log) | CODE | Unit test: commit with "BREAKING CHANGE:" footer → advisory if MAJOR not bumped |
| 5 | Write failing test: `git tag v2.0.0` without CHANGELOG entry | TDD | Test fails before CHANGELOG check logic, passes after |
| 6 | Integration test: dispatcher with git tag command, CHANGELOG exists with matching version | INTEGRATION | Full dispatcher flow → allow when CHANGELOG has entry |
| 7 | Regression test: non-tag git commands never trigger; existing projects without CHANGELOG.md get advisory not crash | REGRESSION | `git commit` does not trigger changelog check; missing CHANGELOG.md → advisory "no CHANGELOG found" not a crash |
| 8 | Live verification: attempt git tag in the Fettle repo | LIVE | `echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git tag v0.9.1"}...}' \| python3 scripts/dispatcher.py` shows advisory about CHANGELOG |

**Config:**
```toml
[gates.release]
enabled = false
mode = "advisory"
changelog_path = "CHANGELOG.md"
require_semver = true
check_breaking_changes = true
```

---

### WP-X4: Mutation Testing Command (3-4 hrs)

New `/fettle:mutation-test` command wrapping mutmut for Python mutation testing on changed files.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement mutation_test.py: detect changed .py files from git diff, invoke `mutmut run --paths-to-mutate=<files>` | CODE | Unit test: mock subprocess returns mutmut results, parsed correctly |
| 2 | Parse mutmut results: extract survived/killed/timeout counts and surviving mutant details | CODE | Unit test: sample mutmut JSON output → structured report with file, line, mutation type |
| 3 | Compute mutation score: killed / (killed + survived) * 100 | CODE | Unit test: 7 killed + 3 survived = 70% score |
| 4 | Timeout enforcement: cap mutation run at configurable limit (default 300s) | CODE | Unit test: mock slow process → timeout, partial results reported |
| 5 | Graceful absence: if mutmut not installed, report clearly with install instructions | CODE | Unit test: FileNotFoundError → "mutmut not found. Install: pip install mutmut" |
| 6 | Write failing test: mutmut returns 3 surviving mutants, score below threshold | TDD | Test fails before threshold comparison, passes after |
| 7 | Integration test: run on a fixture module with known killable/surviving mutants | INTEGRATION | Fixture with `def is_adult(age): return age >= 18` → mutant `age > 18` should be killed by test; report shows expected results |
| 8 | Regression/inversion test: empty project → "nothing to mutate" not crash; mutmut returns malformed output → degraded/unknown result with partial data; test-only changes → skip | REGRESSION | No changed source files produces "nothing to mutate"; corrupted mutmut output produces degraded result (not crash) with status=unknown; test-only changes produce "no implementation files to mutate" |
| 9 | Live verification: run mutation test on a small module | LIVE | `bash scripts/run.sh mutation_test.py --paths scripts/advisory.py --timeout 60` produces mutation report (or "mutmut not found" gracefully) |

**Config:**
```toml
[gates.mutation]
threshold = 70
timeout_s = 300
paths = ["src/"]
exclude = ["tests/", "migrations/"]
```

---

### WP-X5: Requirements Traceability Command (6-8 hrs)

New `/fettle:trace-requirements` command linking spec files to tests to code.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Scan for spec files matching configurable patterns (docs/*spec*.md, docs/*requirements*.md) | CODE | Unit test: docs/ with 3 spec files → all 3 discovered |
| 2 | For each spec, find corresponding test files (naming convention: spec "auth" → test_auth.py) | CODE | Unit test: spec "auth-spec.md" matches "tests/test_auth.py" |
| 3 | Support explicit tracing markers: `# traces: docs/auth-spec.md` in test files | CODE | Unit test: test file with marker → linked to spec regardless of naming |
| 4 | Report: specs without tests (uncovered requirements), tests without specs (orphan tests) | CODE | Unit test: 3 specs, 2 with matching tests → report shows 1 uncovered |
| 5 | Report: coverage summary (N/M specs have tests = X% traced) | CODE | Unit test: 2/3 specs traced = 67% |
| 6 | Write failing test: project with spec and no matching test → uncovered finding | TDD | Test fails before tracing logic, passes after |
| 7 | Integration test: fixture project with mixed coverage → full trace report | INTEGRATION | Fixture with 2 specs (1 with test, 1 without) + 1 orphan test → report lists all 3 categories correctly |
| 8 | Regression test: project with no docs/ directory → "no specs found" not crash; project with no tests/ → "no test root" not crash | REGRESSION | Missing docs/ produces "no specification files found at configured patterns"; missing tests/ produces "no test directory found"; neither crashes |
| 9 | Live verification: run traceability on Fettle itself | LIVE | `bash scripts/run.sh trace_requirements.py --root . --spec-patterns "docs/**/*plan*.md" --test-root tests/` produces report showing which plans have corresponding test files |

**Config:**
```toml
[gates.traceability]
spec_patterns = ["docs/**/*spec*.md", "docs/**/*requirements*.md"]
test_roots = ["tests/"]
trace_marker = "# traces:"
naming_convention = true
```

---

## Execution Order

```
WP-X3 (changelog/semver)      ─── smallest, extends existing commit_message
WP-X1 (debt dashboard)        ─── extends existing report with existing data
WP-X2 (deploy safety)         ─── new hook, follows artifact_gate pattern
WP-X4 (mutation testing)      ─── new command, independent
WP-X5 (requirements trace)    ─── most complex, independent
```

## Summary

| WP | Hours | Risk | SWEBOK KA |
|---|---|---|---|
| X1 | 4-6 | Low | KA 7 (Maintenance) |
| X2 | 4-6 | Low | KA 6 (Operations) |
| X3 | 2-3 | Low | KA 8 (SCM) |
| X4 | 3-4 | Medium | KA 5 (Testing) |
| X5 | 6-8 | Medium | KA 1 (Requirements) |
| **Total** | **19-27** | | |
