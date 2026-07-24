# Fettle Expansion Plan: From Code Quality to Engineering Discipline

## User Story

As a developer using Claude Code with Fettle hooks, I want Fettle to enforce
per-check time budgets, measure diff-coverage, prevent over-engineering, and
require verification evidence — so that quality enforcement is comprehensive,
fair (no starvation), and covers the full engineering lifecycle, not just linting.

## Assumptions

1. Fettle runs as Claude Code hooks (PreToolUse, PostToolUse, Stop) — no daemon.
2. All changes land in `~/.claude/plugins/fettle/scripts/`.
3. Python >= 3.11 runtime guaranteed (run.sh enforces this).
4. `pytest-cov` / `coverage.py` available or installable via uv.
5. No external API calls in hot-path hooks (budget constraints).
6. Ponytail and Superpowers are MIT-licensed — cherry-pick, don't vendor wholesale.
7. Each work package must pass Fettle's own test suite (`pytest tests/ -q`).

## Tradeoffs Considered

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| **A: Monolithic rewrite** | Clean architecture | Breaks all tests, high risk | Reject |
| **B: Incremental WPs** | Each shippable, testable, rollback-safe | Slower total delivery | **Accept** |
| **C: Fork to Fettle v2** | Clean break | Maintains two codebases | Reject |

Recommendation: **B — Incremental work packages**, each self-contained and testable.

## Blast Radius

| Component | Risk | Mitigation |
|---|---|---|
| `dispatcher.py` | Core loop change — all checks affected | WP-1 adds timeout; existing tests validate no regression |
| `quality_gate.py` | Coverage gate adds new blocking behavior | Off by default; opt-in via `.fettle.toml` |
| `lean_sniffers.py` | Enhanced rules may trigger on existing code | Advisory mode only; never blocks without opt-in |
| `stop_quality_gate.py` | Stronger evidence requirement | Progressive: warn first session, block next |
| New files | No blast radius | Self-contained modules |

## Success Criteria

- [ ] Per-check budgets enforced: a check exceeding its budget_ms is killed and logged
- [ ] Diff-coverage: edited Python lines measured, threshold configurable, blocks below threshold
- [ ] Lean enforcement: Ponytail decision ladder integrated into lean_sniffers
- [ ] Verification gate: Stop hook requires evidence artifact (test output, screenshot marker, curl log)
- [ ] All existing Fettle tests pass (no regressions)
- [ ] Each WP has its own test file with >= 3 test cases

---

## Work Packages

### WP-1: Per-Check Budget Enforcement (P0)

**Problem:** `budget_ms` on CheckSpec is dead metadata. A slow check starves later checks.

**Files modified:**
- `scripts/dispatcher.py` — add per-check timeout via `concurrent.futures.ThreadPoolExecutor`

**Design:**
```python
# In the check execution loop (dispatcher.py line 113-125):
# Before: spec.run(ctx) runs unconstrained
# After:
import concurrent.futures

per_check_budget = spec.budget_ms / 1000.0 if spec.budget_ms else (deadline - time.monotonic())
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    future = pool.submit(spec.run, ctx)
    try:
        result = future.result(timeout=per_check_budget)
    except concurrent.futures.TimeoutError:
        aggregator.record_check_timeout(spec.name, spec.budget_ms)
        continue
```

**Changes to `dispatcher_aggregate.py`:**
- Add `record_check_timeout(name, budget_ms)` method
- Log timeout in timings as `decision="timeout"`

**Tests:** `tests/test_dispatcher_budget.py`
- Test: check exceeding budget is killed, returns timeout finding
- Test: check within budget completes normally
- Test: global deadline still respected (check doesn't start if event budget exhausted)
- Test: timeout finding is advisory, never blocks

**Effort:** 1-2 hours
**Risk:** Low — only affects execution timing, fail-open on timeout

---

### WP-2: Diff-Coverage Measurement (P1)

**Problem:** Fettle knows tests ran but not what they covered. Zero coverage data.

**New file:** `scripts/coverage_gate.py`

**Design:**
1. After test stamp detected (in `quality_gate.py:stamp_tests`), also trigger coverage:
   - Run `coverage json --include=<edited_files>` (reads `.coverage` if pytest-cov was used)
   - Parse `coverage.json` for line-level coverage of edited files only
   - Store result in session state: `state_dir / "coverage.json"`

2. At Stop hook, `coverage_gate.py` reads the stored coverage:
   - Calculate: lines_covered / lines_edited for each file
   - Compare against threshold (default 80%, configurable via `.fettle.toml`)
   - Below threshold: block (if mode=enforce) or warn (if mode=advisory)

**Config addition to `.fettle.toml`:**
```toml
[gates.coverage]
enabled = false          # opt-in
mode = "advisory"        # or "enforce"
threshold = 80           # percent of edited lines that must be covered
require_pytest_cov = false  # if true, block if no .coverage file exists
```

**Integration with dispatcher:**
- New `CheckSpec` in `dispatcher_registry.py`: event=Stop, order=45, budget_ms=200

**Tests:** `tests/test_coverage_gate.py`
- Test: coverage above threshold passes
- Test: coverage below threshold warns/blocks per mode
- Test: missing .coverage file handled gracefully (skip, don't crash)
- Test: only edited files measured (not whole project)

**Effort:** 3-4 hours
**Risk:** Medium — depends on pytest-cov being available; fail-open if not
**Dependency:** None (WP-1 is independent)

---

### WP-3: Lean Enforcement — Ponytail Decision Ladder (P2)

**Problem:** `lean_sniffers.py` uses heuristics (line count, single-method class). Ponytail's structured decision ladder is sharper.

**Files modified:**
- `scripts/lean_sniffers.py` — add new sniffers

**New sniffers (from Ponytail's philosophy):**

| ID | Name | Trigger |
|---|---|---|
| LR013 | YAGNI_UNUSED_PARAM | Function parameter added but never referenced in body |
| LR014 | STDLIB_AVAILABLE | Import of external lib for something stdlib does (e.g., `requests` for simple GET when `urllib` suffices, `arrow` when `datetime` works) |
| LR015 | WRAPPER_NO_VALUE | Function that only calls one other function with same args |
| LR016 | PREMATURE_GENERIC | TypeVar/Generic introduced with only one concrete usage |

**Design principle:** Each sniffer is AST-based (no LLM call), runs in < 50ms, produces a `CheckFinding` with severity=WARNING.

**Config:**
```toml
[gates.lean_review.tier1.sniffers]
LR013_YAGNI_UNUSED_PARAM = true
LR014_STDLIB_AVAILABLE = true
LR015_WRAPPER_NO_VALUE = true
LR016_PREMATURE_GENERIC = true
```

**Tests:** `tests/test_lean_sniffers_ponytail.py`
- Test each sniffer with positive and negative cases
- Test: sniffers are advisory only (never block)
- Test: disabled sniffers don't run

**Effort:** 3-4 hours
**Risk:** Low — advisory only, existing lean_sniffers pattern is proven
**Dependency:** None

---

### WP-4: Verification Evidence Gate (P3)

**Problem:** Stop hook only checks "tests ran." Doesn't verify the agent proved the change works.

**New file:** `scripts/verification_gate.py`

**Design — Evidence types recognized:**
1. **Test output** — already tracked (stamp_tests in quality_gate.py)
2. **Screenshot/browser** — already tracked (BROWSER_TEST_MARKER)
3. **CLI output verification** — NEW: detect patterns like `curl`, `http`, API responses in bash history
4. **Build success** — NEW: detect `npm run build`, `cargo build`, `go build` completion

**Evidence scoring:**
- Implementation files edited → require at least 1 evidence type
- Frontend files edited → require browser evidence OR screenshot
- API files edited → require curl/http evidence OR test

**Integration:**
- Registered as CheckSpec: event=Stop, order=48, budget_ms=100
- Mode: advisory (default) or enforce
- First session with a project: warn only. After `.fettle.toml` opt-in: block.

**Config:**
```toml
[gates.verification]
enabled = false
mode = "advisory"
require_browser_for_frontend = true
require_build_for_compiled = true
```

**Tests:** `tests/test_verification_gate.py`
- Test: all evidence types detected correctly from bash command history
- Test: missing evidence produces advisory/block per mode
- Test: non-implementation edits (docs, config) don't require evidence

**Effort:** 2-3 hours
**Risk:** Low — advisory default, fail-open
**Dependency:** WP-1 (needs budget enforcement so this doesn't starve other Stop checks)

---

### WP-5: Systematic Debugging Upgrade for loop_detect (P3)

**Problem:** `loop_detect.py` counts repetitions. It doesn't distinguish "retrying blindly" from "investigating with new information."

**Files modified:**
- `scripts/loop_detect.py` — enhance detection logic

**Current behavior:** Fires when same file is edited 3+ times in a window of 7 tool calls.

**Enhanced behavior:**
1. Track not just "same file edited" but "same region edited" (within 5 lines)
2. Check if intervening tool calls show investigation (Read of related files, grep, test run)
3. If 3+ edits to same region with NO investigation between them → "blind retry" finding
4. If 3+ edits but with Reads/greps between → "iterating with feedback" → no finding

**Scoring:**
```
blind_retry_score = same_region_edits - investigation_actions_between
if blind_retry_score >= 3: fire advisory
```

**Advisory message change:**
```
Before: "Loop detected: {file} edited 3 times in 7 actions"
After:  "Blind retry detected: {file}:{region} edited 3 times without investigation. 
         Try: read error output, check related files, or ask for direction."
```

**Tests:** `tests/test_loop_detect_v2.py`
- Test: blind retries detected (edit-edit-edit with no reads)
- Test: informed iteration not flagged (edit-read-edit-grep-edit)
- Test: different regions of same file don't trigger
- Test: threshold configurable

**Effort:** 2-3 hours
**Risk:** Low — strictly advisory, existing loop_detect tests still pass
**Dependency:** None

---

### WP-6: Code Review Subagent at Stop (P4)

**Problem:** No automated review before response delivery for multi-file changes.

**New file:** `scripts/review_dispatch.py`

**Design:**
- Only fires when: 5+ implementation files edited in session AND no review command detected in bash history
- Does NOT run an LLM call in the hook (too slow, budget violation)
- Instead: emits an advisory message recommending the agent run `/code-review` before completing
- If `.fettle.toml` sets `[gates.review] mode = "enforce"`: blocks until review evidence exists

**Evidence of review:**
- Bash command containing `code-review`, `review`, or `cr`
- A file matching `*.review.md` created in session
- The string "LGTM" or "review complete" in recent bash output

**Config:**
```toml
[gates.review]
enabled = false
mode = "advisory"
threshold_files = 5
```

**Tests:** `tests/test_review_dispatch.py`
- Test: < 5 files edited → no finding
- Test: >= 5 files, no review evidence → advisory
- Test: >= 5 files, review evidence exists → pass
- Test: enforce mode blocks

**Effort:** 2 hours
**Risk:** Low — advisory default, simple file-count heuristic
**Dependency:** None (but pairs well with WP-4's evidence tracking)

---

## Execution Order

```
WP-1 (budget enforcement) ─── independent, unblocks WP-4
WP-2 (diff-coverage)      ─── independent
WP-3 (lean/ponytail)      ─── independent
WP-4 (verification gate)  ─── after WP-1
WP-5 (loop_detect v2)     ─── independent
WP-6 (review dispatch)    ─── independent
```

Parallelizable: WP-1, WP-2, WP-3, WP-5, WP-6 can all proceed in parallel.
Sequential: WP-4 depends on WP-1 (budget enforcement needed for Stop-hook fairness).

## Total Effort Estimate

| WP | Hours | Risk |
|---|---|---|
| WP-1 | 1-2 | Low |
| WP-2 | 3-4 | Medium |
| WP-3 | 3-4 | Low |
| WP-4 | 2-3 | Low |
| WP-5 | 2-3 | Low |
| WP-6 | 2 | Low |
| **Total** | **13-18 hours** | **Low-Medium** |

## Rollback Strategy

Each WP is:
1. A new CheckSpec in the registry (can be disabled via config)
2. Off by default (opt-in via `.fettle.toml`)
3. Advisory mode before enforce mode
4. Fail-open on any error

To disable any WP's output without reverting code:
```toml
[dispatcher.checks.coverage_gate]
enabled = false
```

---

## Appendix: Independent Architecture Review

**Verdict: APPROVE WITH CONDITIONS**

Reviewer found 13 issues. The 5 blocking conditions (must address before implementation):

### Condition 1: WP-1 Cannot Use ThreadPoolExecutor (CRITICAL)

**Problem:** `concurrent.futures.ThreadPoolExecutor` does NOT kill running threads.
`future.result(timeout=X)` raises `TimeoutError` in the caller, but the thread
continues executing. Worse, the `with` context manager calls `shutdown(wait=True)`
which blocks until the thread finishes — defeating the entire purpose.

**Fix:** Two options:
- (a) Use `multiprocessing.Process` + `.terminate()` for true kill. Higher overhead (~50ms process spawn) but reliable.
- (b) Acknowledge this is **cooperative budgeting only** — checks self-enforce via `time.monotonic()` checks in their own loops. Rename success criterion from "killed" to "logged and skipped next iteration."

**Decision:** Option (b) for Phase 1 (immediate). Option (a) as WP-1b later if needed.
The dispatcher already stops calling *future* checks when deadline passes; the per-check
budget becomes a cooperative protocol: checks receive their budget via context and should
self-abort when exceeded. The dispatcher logs overruns for observability.

### Condition 2: WP-2 Must Not Spawn `coverage json` in Hot Path

**Problem:** `coverage json` spawns a Python subprocess (200-300ms startup),
reads a SQLite `.coverage` database, and serializes — easily 1-3 seconds.
This blows the 600ms Stop budget and violates Assumption 5.

**Fix:** WP-2 coverage_gate reads a **pre-existing** `coverage.json` file only.
The generation happens at test-stamp time (PostToolUse after pytest runs) where
the 15s Claude Code timeout is generous. Specifically:
1. `stamp_tests()` in `quality_gate.py` detects pytest-cov ran
2. NEW: fire `coverage json -o <state_dir>/coverage.json --include=<tracked_files>` asynchronously (subprocess, fire-and-forget)
3. At Stop, `coverage_gate` only reads the pre-computed JSON. If it doesn't exist: skip.

### Condition 3: Stop Check Ordering — Blocking Before Advisory

**Problem:** New advisory checks (coverage_gate order=45, verification_gate order=48)
run BEFORE the existing blocking `stop_quality_gate` (order=50). If they consume
budget, the blocking check gets starved — a correctness regression.

**Fix:** Reorder new advisory checks to order > 50:
- coverage_gate: order=55 (was 45)
- verification_gate: order=60 (was 48)
- review_dispatch: order=65

Blocking checks always run first. Advisory checks get remaining budget.

### Condition 4: WP-4 + WP-6 Need Shared Bash History Tracking

**Problem:** Both work packages need to access "what bash commands ran this session"
but neither specifies how. Claude Code hook input only contains the current tool call,
not session history.

**Fix:** Add a shared infrastructure piece first:
- `quality_gate.py` already tracks edits in `edits.jsonl`
- Extend: on PostToolUse for Bash tool, also log command + exit code to `bash_history.jsonl`
- Both WP-4 and WP-6 read this shared log at Stop time.
- This becomes "WP-0.5" — a 30-minute prerequisite before WP-4/WP-6.

### Condition 5: WP-1 Risk Rating = Medium, Not Low

**Rationale:** Touches the core dispatch loop (all checks affected), introduces a
new execution model (cooperative timeout protocol), requires all existing checks to
be timeout-aware. Pre-existing issue: `stop_quality_gate` already runs `cargo check`
with a 60-second subprocess timeout — WP-1's cooperative model can't fix this.

---

### Non-Blocking Findings (address during implementation):

6. **WP-2 stale `.coverage` detection** — check file mtime; ignore if > 5 minutes old.
7. **WP-5 "same region" is harder than stated** — use "same first 50 chars of old_string" heuristic, not line numbers (line shifts make exact tracking a multi-day problem).
8. **WP-3 LR014 false positives** — restrict to explicit 1:1 replacement allowlist, not open-ended "stdlib could do this."
9. **`.fettle.toml` schema evolution** — unknown keys must be silently ignored (already handled by `_deep_merge` in config.py, confirmed).
10. **Pre-existing `cargo check` 60s timeout** — WP-1 cannot fix subprocess-based checks. Tracked as separate future work: subprocess checks need `process.kill()` on budget overrun.

---

## Revised Execution Order (post-review)

```
WP-0.5 (bash history tracking)  ─── prerequisite for WP-4, WP-6
WP-1   (cooperative budget)     ─── independent, risk=Medium
WP-2   (diff-coverage, read-only) ─── independent (generation moved to PostToolUse)
WP-3   (lean/ponytail)          ─── independent
WP-4   (verification gate)      ─── after WP-0.5, after WP-1
WP-5   (loop_detect v2)         ─── independent
WP-6   (review dispatch)        ─── after WP-0.5
```

## Revised Effort Estimate

| WP | Hours | Risk |
|---|---|---|
| WP-0.5 | 0.5 | Low |
| WP-1 | 2-3 | **Medium** |
| WP-2 | 3-4 | Medium |
| WP-3 | 3-4 | Low |
| WP-4 | 2-3 | Low |
| WP-5 | 2-3 | Low |
| WP-6 | 2 | Low |
| **Total** | **15-20 hours** | |

---

## What This Does NOT Include (Explicit Scope Boundary)

- No LLM calls in hooks (too slow, non-deterministic)
- No Mermaid visualization (utility, not enforcement — separate effort)
- No wholesale Superpowers/ECC/Ponytail vendoring (cherry-pick only)
- No UI-UX Pro Max integration (requires frontend project context)
- No OpenUI integration (irrelevant to quality enforcement)
- No changes to `settings.json` hook wiring (already correct)
- No new discipline skills (existing ones cover the process layer)
