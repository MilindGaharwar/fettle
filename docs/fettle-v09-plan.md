# Fettle v0.9 Implementation Plan

**Authored by:** GPT-5.6 Sol (design) + Claude Opus (review + formatting)
**Status:** Pending Sol sign-off
**Total effort:** ~8-11 days across 4 work packages
**Prerequisite:** Fettle v0.8 shipped and activated

---

## Work Packages

### WP-K: Branch Coverage Gate (1-1.5 days)

Extend `coverage_gate.py` to evaluate branch/decision coverage from `coverage.json`.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Parse `missing_branches` and `executed_branches` from coverage.json per file | CODE | Unit test: parse sample coverage.json with branch data, assert correct arc extraction |
| 2 | Intersect missing branches with edited lines (only arcs originating from edited lines) | CODE | Unit test: edited line 10 has missing branch [10,15]; unedited line 20 has missing branch [20,25]; only first flagged |
| 3 | Compute branch coverage percentage: covered_arcs / (covered + missing) × 100 | CODE | Unit test: 3 executed + 1 missing from edited lines = 75% |
| 4 | Add `minimum_branch_percent` config key, skip silently when branch data absent | CODE | Unit test: coverage.json without missing_branches field → check passes silently |
| 5 | Write failing test: edited line has missing branch, threshold 80% | TDD | Test fails before implementation, passes after |
| 6 | Integration test: full hook invocation with mock coverage.json containing branch data | INTEGRATION | `echo '{"hook_event_name":"Stop"...}' \| python3 coverage_gate.py` returns advisory with branch % |
| 7 | Regression test: coverage.json with branch data missing for some files but present for others — mixed scenario | REGRESSION | Files without branch data skip silently; files with branch data are evaluated; no crash on partial data |
| 8 | Live verification: run pytest --cov --branch on Fettle itself, generate coverage.json, trigger Stop hook | LIVE | `pytest --cov=scripts --cov-branch --cov-report=json && echo '{"hook_event_name":"Stop"...}' \| python3 scripts/dispatcher.py` shows branch coverage findings |

**Config:**
```toml
[gates.coverage]
minimum_branch_percent = 80   # 0 = disabled; independent of line threshold
```

**Acceptance:**
- Existing line coverage behavior unchanged
- Branch check skipped when data absent (no crash, no warning)
- Percentage computed only from edited-line-origin arcs
- Advisory by default

---

### WP-H: Function Complexity Limits (1-1.5 days)

Add cyclomatic and cognitive complexity checks for new/modified Python functions.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement `complexity_check.py` with `CyclomaticVisitor`: count if/for/while/except/boolop/comprehension per function | CODE | Unit test: known function with 3 ifs + 1 for = cyclomatic 5 |
| 2 | Implement `CognitiveVisitor`: nesting-penalized count (1 + depth for control flow, break/continue +1) | CODE | Unit test: nested-3-deep if chain = cognitive score 6 (1+0 + 1+1 + 1+2) |
| 3 | Filter to only functions intersecting `changed_lines` | CODE | Unit test: file with 2 functions, only one touched → only that one scored |
| 4 | Integrate into dispatcher registry as PostToolUse(.py) check, budget_ms=100 | CODE | Dispatcher selects check for .py edits |
| 5 | Write failing test: function with cyclomatic 12 (exceeds default 10) | TDD | Test fails before implementation, passes after |
| 6 | Integration test: full dispatcher invocation on a complex .py file in advisory mode | INTEGRATION | Advisory returned with function name, score, and limit |
| 7 | Regression test: existing over-limit function untouched while nearby function is edited — only the edited one flagged | REGRESSION | Untouched complex function at line 1-50 produces no finding when edit is at line 100; changed function at line 100 exceeding limit does produce finding |
| 8 | Inversion test: file with syntax error or empty content produces degraded/unknown result, not a crash or false score < 0.5 | REGRESSION | Malformed Python file (syntax error) → complexity check returns allow with no score emitted (degraded gracefully); empty file → no findings, no crash |
| 9 | Live verification: edit a deliberately complex function and observe the advisory | LIVE | `echo '{"hook_event_name":"PostToolUse","tool_name":"Edit","tool_input":{"file_path":"scripts/stop_quality_gate.py"}...}' \| python3 scripts/dispatcher.py` shows complexity findings for modified functions |

**Config:**
```toml
[gates.complexity]
enabled = true
enforce = false
max_cyclomatic = 10
max_cognitive = 15
```

**Acceptance:**
- stdlib `ast` only, no external deps
- Single AST parse shared with lean_sniffers (or receives pre-parsed tree)
- Only changed/new functions evaluated
- Advisory by default; `enforce = true` required for blocking
- p95 < 100ms on representative files

---

### WP-J: Enhanced Plan Thresholds (2-3 days)

Extend the plan gate with risk-path detection, module count, and line estimation.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add risk-path detection: match edited file paths against configurable glob patterns (auth/, security/, migration/) | CODE | Unit test: `src/auth/login.py` matches `**/auth/**`; `src/authorization.py` does not |
| 2 | Add module counting: derive top-level package from edited paths using configurable `module_roots` | CODE | Unit test: `src/payments/api.py` + `src/billing/invoice.py` = 2 modules |
| 3 | Add line estimation via cached `git diff --numstat` with timeout and graceful failure | CODE | Unit test: mock git output with 200 added lines → threshold met |
| 4 | Integrate all thresholds into `scan_planning()` — any one independently triggers plan requirement | REFACTOR | Existing file-count tests still pass; new thresholds fire independently |
| 5 | Write failing test: first edit to an auth/ path blocks without a plan | TDD | Test fails before risk-path check is implemented |
| 6 | Integration test: full hook with 3 modules edited, module_threshold=3, plan exists → passes | INTEGRATION | `echo '{"hook_event_name":"PreToolUse"...}' \| python3 scripts/dispatcher.py` allows when plan found |
| 7 | Regression test: existing projects using only `threshold=3` continue working unchanged after upgrade — no new blocks from unset thresholds | REGRESSION | Project with no risk_paths or module/line config in .fettle.toml behaves identically to v0.8; only file-count threshold fires |
| 8 | Live verification: edit files across 3 modules without a plan, observe the block message | LIVE | Edit `src/auth/x.py` then `src/billing/y.py` then `src/payments/z.py`; third edit blocked with `"3 modules affected (threshold: 3)"` in hookSpecificOutput |

**Config:**
```toml
[gates.plan]
threshold = 3                           # Existing (file count), null disables
risk_paths = ["**/auth/**", "**/security/**", "**/migration/**", "**/migrations/**"]
module_threshold = 3                    # Distinct top-level packages, null disables
module_roots = ["src", "packages"]
line_threshold = 150                    # Total added lines across session, null disables
diff_timeout_ms = 500
```

**Acceptance:**
- Backward compatible: existing `threshold` key works unchanged
- Each threshold independently enables/disables
- Block message names which threshold triggered and observed value
- Git failures skip line check (don't block)
- Component-based path matching (not substring)

---

### WP-I: TDD Phase Enforcement (3-5 days)

Detect whether test files are edited before corresponding implementation files.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement path classification: test vs implementation vs exempt, with configurable patterns | CODE | Unit test: `tests/test_parser.py` → test; `src/fettle/parser.py` → impl; `docs/README.md` → exempt |
| 2 | Implement module-key derivation: map test paths and impl paths to the same key | CODE | Unit test: `tests/test_parser.py` and `src/fettle/parser.py` both resolve to `fettle/parser` |
| 3 | Implement ordering state: `tdd_events.jsonl` with sequence numbers, recording test-first evidence | CODE | Unit test: record test edit seq=1, check impl at seq=2 → has evidence |
| 4 | PreToolUse gate: advisory/block when impl edit has no prior test evidence for its module | CODE | Unit test: impl edit without prior test → advisory; with prior test → allow |
| 5 | PostToolUse recorder: log successful edits with classification and sequence | CODE | Unit test: after Write(test_parser.py) → event recorded with module key |
| 6 | Write failing test: implementation edit attempted before any test file edit in strict mode | TDD | Test fails before gate logic is implemented |
| 7 | Integration test: create test file → edit impl file → full hook flow in advisory mode | INTEGRATION | Advisory mode: first impl edit shows reminder; after test edit, subsequent impl edit is clean |
| 8 | Regression test: project with existing tests and `accept_preexisting_tests=true` — implementation edits allowed without re-editing the test file | REGRESSION | User with existing test suite (`accept_preexisting_tests=true`) can edit implementation freely without being forced to touch test files; only NEW modules (no test file exists) trigger the advisory |
| 9 | Live verification: start a session, edit a source file, observe advisory, then edit corresponding test, edit source again, observe clean pass | LIVE | `python3 scripts/dispatcher.py` with PreToolUse for `src/new_module.py` → advisory; then PostToolUse for `tests/test_new_module.py`; then PreToolUse for `src/new_module.py` again → allowed |

**Config:**
```toml
[gates.tdd]
enabled = true
mode = "advisory"                    # advisory only in v0.9; strict deferred to v1.0
test_patterns = ["tests/test_{module}.py", "tests/**/test_*.py"]
implementation_roots = ["src/"]
exempt_paths = ["docs/**", "tests/fixtures/**", "*.toml", "*.yaml", "*.md"]
accept_preexisting_tests = true      # Default true: existing tests count as evidence
```

**Acceptance:**
- Advisory mode only in v0.9 (strict mode deferred — same pilot-then-scale pattern)
- Ordering persists across hook invocations (file-based state)
- Exempt paths never trigger
- `accept_preexisting_tests=true` means existing test file satisfies the requirement
- Module mapping errors produce advisory (not crash)
- Clear message identifies expected test path
- Path mappings escape hatch via `[gates.tdd.path_mappings]`

---

## Execution Order

```
WP-K (branch coverage)  ─── smallest, extends existing code
WP-H (complexity)        ─── independent, new check module
WP-J (plan thresholds)   ─── extends existing plan gate
WP-I (TDD enforcement)   ─── most complex, benefits from patterns established by H/J
```

## Summary

| WP | Days | Risk | What it adds |
|---|---|---|---|
| K | 1-1.5 | Low | Branch coverage from existing coverage.json |
| H | 1-1.5 | Low | Cyclomatic + cognitive complexity per function |
| J | 2-3 | Low | Risk paths, module count, line estimation triggers for plan gate |
| I | 3-5 | Medium-High | Test-before-impl ordering enforcement |
| **Total** | **7.5-11** | | |

## Conditions from Review

1. **WP-I defaults to `accept_preexisting_tests = true`** — forcing re-edits on existing tests is hostile
2. **WP-I ships advisory-only in v0.9** — strict mode is v1.0 after advisory proves itself
3. **WP-I includes `[gates.tdd.path_mappings]` from day 1** — non-standard layouts need an escape hatch
4. **WP-H uses a separate `complexity_check.py`** (not inline in lean_sniffers) to prevent unbounded growth

---

## Sol Sign-Off Clarifications (Required)

#### Clarification K: Branch Coverage — Precise Semantics

**Denominator:** For each edited executable line L, count arcs where `from_line == L`:
- `covered_arcs` = arcs in `executed_branches` originating from L
- `missing_arcs` = arcs in `missing_branches` originating from L
- `branch_percent = covered_arcs / (covered_arcs + missing_arcs) * 100`

**Aggregation:** Aggregate across ALL edited files before applying threshold (not per-file).

**Edge cases:**
- Negative/synthetic arc destinations (e.g., exit arcs `[10, -1]`): include in count normally
- Deleted/renamed files: skip (file must exist and be in coverage.json)
- Path normalization: resolve both coverage.json paths and edited paths to absolute before comparison
- Missing `missing_branches` field: skip branch check for that file (not the whole gate)
- Debug visibility: when branch check is skipped, log `"branch_data_unavailable"` to trace (not user-facing)

**Threshold scope:** Aggregate (sum all edited-line arcs across all files, compute single percentage).

#### Clarification H: Complexity — Exact AST Rules

**Cyclomatic complexity (per function, starting at 1):**
| AST Node | Contribution |
|---|---|
| `If` (including elif) | +1 per branch |
| `For`, `AsyncFor`, `While` | +1 |
| `ExceptHandler` | +1 |
| `IfExp` (ternary) | +1 |
| `BoolOp` (and/or) | `len(values) - 1` |
| `comprehension` generator | +1 per generator |
| `comprehension` if-clause | +1 per if |
| `match_case` | +1 per case |
| `with`, `try`, `else`, `finally` | +0 |

**Cognitive complexity (per function, starting at 0):**
| Construct | Cost |
|---|---|
| `if`, `elif`, `for`, `while`, `except`, `match_case`, `IfExp` | 1 + current_nesting_depth |
| Entering body of above | nesting_depth += 1 |
| `BoolOp` (and/or chains) | `len(values) - 1` (no nesting penalty) |
| `break`, `continue` | +1 (no nesting penalty) |
| Nested function/lambda | scored independently, skipped in parent |

**Modified function definition:** A function is "modified" when `changed_lines` intersects the range `[min(decorator_line, func.lineno), func.end_lineno]`. Nested functions are evaluated independently.

#### Clarification J: Plan Thresholds — Semantic Decisions

**Line estimation:** Additions only (not deletions). Binary files ignored (lines = `-` in numstat).

**Module definition:** First path component after the configured `module_roots` prefix. E.g., with `module_roots = ["src"]`: `src/payments/api.py` → `payments`. Files not under any module_root are grouped as `_root`.

**Glob semantics:** Risk-path globs are matched against the repo-relative path using `fnmatch` with `**` support (pathlib.PurePath.match behavior). Root is the project cwd.

**Trigger semantics:** OR — any single enabled threshold can independently require a plan.

**Existing threshold mapping:** `gates.plan.threshold` remains the file-count trigger. New keys are additive and independent.

**Git-diff cache key:** `(repo_root_abspath, session_id, hook_invocation_count)`. Invalidated each invocation. Cache lifetime = single process run only (hooks are short-lived).

**Git failure handling:** Skip line threshold, log `"git_diff_unavailable"` to trace. Do not block, do not warn user.

#### Clarification I: TDD — Event Model Specification

**Evidence definition:** A test edit (PostToolUse for Write/Edit of a test-classified file) constitutes evidence. Test execution (bash pytest) does NOT count — it proves tests pass, not test-first ordering.

**Evidence scope:** Evidence must precede the FIRST implementation edit for a module key in this session. Subsequent edits to the same module don't require re-evidence.

**Mapping cardinality:** One test file can satisfy multiple impl files with the same module key. One impl file needs evidence from any one matching test file.

**Sequence allocation:** Monotonic counter in `tdd_events.jsonl`, incremented per write. File-level append with `os.O_APPEND` (atomic on POSIX for < PIPE_BUF). No concurrent-write lock needed for append.

**Scoping:** Per-session only. Branch/worktree changes reset on new session.

**Malformed JSONL:** Skip unparseable lines. Never crash. Log to trace.

**Exemptions:** Files matching `exempt_paths` globs never trigger TDD checks (neither as test nor impl). Generated files (paths containing `__pycache__`, `node_modules`, `.venv`, `dist/`) are always exempt.

**Path mappings precedence:** Explicit `[gates.tdd.path_mappings]` entries override auto-derivation. Format: `"src/special/module.py" = "tests/custom/test_special.py"`.

**Preexisting test discovery:** If `accept_preexisting_tests=true` and a file matching the test pattern for a module key EXISTS on disk (regardless of session edits), that satisfies evidence.

---

## Revised Effort Estimates (per Sol feedback)

| WP | Original | Revised | Reason |
|---|---|---|---|
| K | 1-1.5 days | 1.5-2 days | Path normalization + edge cases |
| H | 1-1.5 days | 2-3 days | Full AST rule specification + fixture tests |
| J | 2-3 days | 2.5-4 days | Cache semantics + glob testing |
| I | 3-5 days | 4-7 days | Event model + mapping + exemptions |
| **Total** | **7.5-11** | **10-16 days** | |
