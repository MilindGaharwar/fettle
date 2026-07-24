# Fettle v0.8 Implementation Plan (Sol-Reviewed) — v2

**Authored by:** GPT-5.6 Sol + Claude Opus (collaborative), revised after code-grounded review
**Status:** Ready for implementation
**Total effort:** ~14.5 hours across 7 work packages
**Supersedes:** `fettle-v08-plan-sol.md`

**Changes from v1:**
1. Config unified on the existing `gates.*` namespace — v1's parallel `[quality.*]` / `[process.*]` / `[audit.*]` schema is dropped; aspirational sections with no implementing WP are moved to a "Deferred to v0.9" appendix so no dead config keys ship.
2. One dedup mechanism: WP-B's persistent `AdvisoryDeduplicator` is the single source of truth; WP-A and WP-C explicitly migrate onto it (new WP-B2 step).
3. `AdvisoryDeduplicator` state is persisted to `state_dir` (hooks are short-lived processes — in-memory cooldowns reset every invocation).
4. WP-D acceptance now requires at least one expensive check to actually consume the deadline.
5. WP-F adds a coverage-staleness check (mtime vs. newest edit) to avoid false verdicts.
6. Cross-check advisory cap (`max_per_turn`) is enforced in the dispatcher `Aggregator`, wired in WP-B.
7. WP-G's gate on WP-C is now a defined metric with baseline and pilot duration, not "measurable improvement".
8. WP-E implements `retention_days` cleanup and documents redaction as best-effort.
9. WP-A takes the hook event name from context, not a hardcoded literal.
10. Effort re-estimated to include migration, aggregator wiring, and pilot instrumentation.

---

## Part 1: New User-Configurable Inputs (.fettle.toml)

All new config lives under the existing `gates.*` namespace (matching `gates.lean_review` et al. in `config.py` DEFAULTS). **Every key below is implemented by a WP in Part 2 — no orphaned config ships.**

```toml
[gates.lean_review]
# existing section — one new key:
mode = "silent"                  # "silent" (JSONL only) or "advisory" (surface findings)  → WP-A

[gates.advisory]                                                                           # → WP-B
cooldown_seconds = 300           # Min time before repeating same advisory (persisted)
dedup_window_seconds = 900       # Same rule+file suppression window
max_per_turn = 3                 # Cross-check cap, enforced in the dispatcher Aggregator
max_total_bytes = 2048           # Size cap for formatted advisory output
allow_escalation = true          # A changed finding (new dedupe_key) can bypass cooldown

[gates.discipline_link]                                                                    # → WP-C, WP-G
enabled = true
skills_path = "~/.claude/plugins/disciplines/skills"
cooldown_seconds = 300
reminder_style = "compact"       # "silent", "compact" (2 sentences max)
# Per-trigger mappings added by WP-G only after the WP-C pilot passes its gate:
# [gates.discipline_link.mappings]
# loop_detect = "systematic-debugging"

[gates.bash_audit]                                                                         # → WP-E
enabled = false                  # Opt-in only
capture_command = false          # If true, logs redacted command text (best-effort — see WP-E)
capture_exit_code = true
capture_duration = true
retention_days = 14              # Auto-delete events older than N days (0 = keep forever)

[gates.bash_audit.redaction]                                                               # → WP-E
enabled = true
replacement = "[REDACTED]"
environment_variables = [        # Case-insensitive env var name matching
  "API_KEY", "SECRET", "TOKEN", "PASSWORD",
  "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN",
]
patterns = [                     # Regex patterns applied before logging
  '(?i)authorization:\\s*bearer\\s+\\S+',
  '(?i)(api[_-]?key|password|secret|token)\\s*[=:]\\s*[^\\s]+',
  '-----BEGIN [A-Z ]+ PRIVATE KEY-----[\\s\\S]*?-----END [A-Z ]+ PRIVATE KEY-----',
]
sensitive_paths = [".env", ".env.*", "**/*.key", "**/*.pem", "**/secrets/**"]
fail_closed = true               # If redaction fails, don't write unredacted data

[gates.coverage]                                                                           # → WP-F
enabled = false                  # Off by default
threshold = 80                   # Required coverage percent for edited lines
mode = "advisory"                # "advisory" or "enforce"
scope = "changed_lines"          # "changed_lines" or "changed_files"
max_staleness_seconds = 0        # 0 = coverage.json must be newer than newest edit;
                                 # N > 0 = tolerate coverage data up to N seconds older
```

---

## Part 2: Work Packages (Sequenced)

### WP-A: Surface Lean Findings (1 hr)

**Problem:** `lean_sniffers.py` writes candidates to JSONL but always returns `CheckResult.allow()`. Findings are invisible.

**File:** `scripts/lean_sniffers.py` — modify `run_check()`

**Change:** After existing candidate collection and JSONL write, add:

```python
    mode = lean_cfg.get("mode", "silent")
    if mode == "silent" or not candidates:
        return CheckResult.allow()

    # Interim inline dedup — replaced by AdvisoryDeduplicator in WP-B2
    seen: set[str] = set()
    unique: list[dict] = []
    for c in candidates:
        key = c.get("dedupe_key", "")
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # Size cap: max 3 findings, max 200 chars each
    capped = unique[:3]
    lines = []
    for c in capped:
        msg = c.get("message", "")[:200]
        loc = f"{c.get('relative_path', '?')}:{c.get('line_start', '?')}"
        lines.append(f"  [{c.get('sniffer_id', 'lean')}] {loc}: {msg}")
    if len(unique) > 3:
        lines.append(f"  ... and {len(unique) - 3} more (run /fettle:lean-debt)")

    text = "Lean review findings:\n" + "\n".join(lines)
    return CheckResult.advisory(text, hook_specific_output={
        # Event name from context — lean_sniffers has two run_check entry points
        # (PostToolUse and Stop paths); never hardcode the literal.
        "hookEventName": ctx.hook_input.hook_event_name,
        "additionalContext": text,
    })
```

**Note:** `lean_sniffers.py` has two `run_check`-style entry points (~line 425 and ~line 520). Apply the surfacing to both, driven by the same `mode` key.

**Tests:** (1) silent mode with findings → allow; (2) advisory mode, 5 findings with 2 dupes → 3 unique surfaced; (3) advisory mode, 0 findings → allow; (4) event name in `hook_specific_output` matches the invoking event

**Acceptance:** Silent unchanged. Non-silent surfaces max 3 deduped. JSONL always written. No regressions. Inline dedup carries a `# replaced in WP-B2` marker.

---

### WP-B: Normalized Advisory Contract (1.5 hrs)

**New file:** `scripts/advisory.py`

```python
@dataclass(frozen=True)
class Advisory:
    rule_id: str
    category: str
    severity: Severity  # error/warning/info
    confidence: float   # 0.0-1.0
    summary: str        # max 120 chars
    recommended_action: str  # max 200 chars
    discipline_id: str | None = None
    discipline_version: str | None = None
    dedupe_key: str = ""
    provenance: str = ""

class AdvisoryDeduplicator:
    """Cooldown state is PERSISTED — hooks are short-lived processes, so an
    in-memory cooldown would reset on every invocation.

    Storage: state_dir/session/advisory_state.json
      { "<dedupe_key>": { "last_emitted": <epoch>, "count": N } }
    Atomic write (tempfile + rename), permissions 0o600.
    Corrupt/missing state file → treat as empty (fail-open for advisories).
    """
    def __init__(self, state_dir: Path, session_id: str,
                 cooldown_s: float = 300.0, window_s: float = 900.0): ...
    def should_emit(self, advisory: Advisory) -> bool: ...
    def record(self, advisory: Advisory) -> None: ...

def format_advisories(advisories: list[Advisory], max_total_bytes: int = 2048) -> str: ...
```

**Aggregator wiring (same WP):** per-check caps alone still allow N checks × 3
advisories per event. The cross-check cap belongs in the dispatcher:

- `dispatcher_aggregate.py` — `Aggregator` gains `max_advisories_per_turn`
  (from `gates.advisory.max_per_turn`, default 3). Advisories beyond the cap
  are dropped highest-`order` first and summarized as
  `"... and N more advisories suppressed this turn"`.
- `format_advisories` respects `gates.advisory.max_total_bytes`.

**Migration:** Additive for existing checks. New checks and WP-C/WP-G use `Advisory`. WP-B2 (below) migrates WP-A.

**Tests:** (1) dedup within cooldown → suppressed **across two separate process invocations** (proves persistence); (2) after cooldown → emitted; (3) format respects size cap; (4) auto-generated dedupe_key deterministic; (5) corrupt state file → advisories still emitted; (6) aggregator caps 3 checks × 3 advisories → max_per_turn surfaced + suppression summary

---

### WP-B2: Migrate WP-A onto the Advisory Contract (0.5 hr)

**Prerequisite:** WP-A and WP-B merged.

Replace WP-A's inline dedupe in `lean_sniffers.py` with `AdvisoryDeduplicator` + `format_advisories`. Delete the `# replaced in WP-B2` block. After this, **exactly one dedup mechanism exists** (WP-C reuses the same class — see below).

**Tests:** WP-A's tests still pass unchanged; add (1) repeated finding within cooldown across invocations → suppressed.

**Acceptance:** No inline dedup remains in `lean_sniffers.py`.

---

### WP-C: Discipline Link Pilot — loop_detect (2.5 hrs)

**Problem:** loop_detect gives generic advice. Should inject discipline-debugging reminder.

**Changes to `scripts/loop_detect.py`:**

```python
_FALLBACK_REMINDER = (
    "Pause and inspect the evidence before repeating the same action. "
    "Form a new hypothesis, then choose a tool call that tests it."
)

def _load_discipline_snippet(config): ...  # Load 2 sentences from SKILL.md
```

Reminder cooldown uses **WP-B's `AdvisoryDeduplicator`** (dedupe_key =
`discipline:loop_detect:<session_id>`) — no bespoke `_reminder_due`
timestamp mechanism.

After existing advisory message construction:
```python
    disc_cfg = ctx.config.get("gates", {}).get("discipline_link", {})
    dedup = AdvisoryDeduplicator(state_dir, session_id,
                                 cooldown_s=disc_cfg.get("cooldown_seconds", 300))
    if dedup.should_emit(reminder_advisory):
        snippet = _load_discipline_snippet(ctx.config)
        msg += f"\n\nDiscipline reminder: {snippet or _FALLBACK_REMINDER}"
        dedup.record(reminder_advisory)
```

**Pilot instrumentation (required — feeds the WP-G gate):** log one JSONL event
per loop_detect firing to `state_dir/session/discipline_pilot.jsonl`:
`{ts, session_id, reminder_shown: bool, next_tool_calls: [first 2 tool names after firing]}`.
The "next tool calls" are captured by the existing PostToolUse path reading the
pilot file for an open marker (cheap, budget ≤ 10ms).

**Config:** `[gates.discipline_link]` as defined in Part 1.

**Tests:** (1) disciplines present → 2-sentence reminder appended; (2) absent → fallback; (3) within cooldown (across process invocations) → no reminder; (4) pilot event written with `reminder_shown` flag

**Acceptance:** Graceful absence. Max 2 sentences. p95 < 50ms. Cooldown enforced via shared deduplicator. Pilot telemetry captured.

---

### WP-D: Cooperative Budget Enforcement (2.5 hrs)

**Problem:** `budget_ms` per CheckSpec is dead metadata.

**Changes:**

1. `dispatcher_types.py` — add `check_deadline_monotonic: float = 0.0` to HookContext
2. `dispatcher.py` — compute per-check deadline as `min(global_deadline, start + budget_ms/1000)`, pass via context, log overruns

```python
    per_check_deadline = deadline
    if spec.budget_ms:
        per_check_deadline = min(deadline, check_start + spec.budget_ms / 1000.0)
    # ... run check with deadline in context ...
    elapsed_ms = int((time.monotonic() - check_start) * 1000)
    if time.monotonic() > per_check_deadline:
        _log_overrun(spec.name, spec.budget_ms, elapsed_ms)
```

3. **At least one consumer, or the metadata is still dead:** the most expensive
   check (lean sniffers Tier-1 scan) checks `ctx.check_deadline_monotonic`
   between sniffer passes and bails early with partial results + a
   `"budget exhausted after N sniffers"` note in its JSONL record.

**Note:** Cooperative only — checks self-budget. No thread killing. Overruns logged for observability, not enforced by process kill.

**Tests:** (1) check within budget → no log; (2) check over budget → overrun logged; (3) global deadline clamp works; (4) lean sniffers with an artificially tiny budget → early bail, partial results recorded

**Acceptance:** Overrun logging live **and** lean sniffers demonstrably honor the deadline.

---

### WP-E: Bash Structured Audit (2 hrs)

**New file:** `scripts/bash_audit.py`

- PostToolUse(Bash) check, order=99, budget_ms=30
- Logs: timestamp, command_hash, exit_code, duration_ms
- NOT raw commands by default (privacy-first)
- Opt-in `capture_command` applies redaction before write
- Redaction: regex patterns from config, fail-closed on invalid regex.
  **Redaction is best-effort (denylist):** novel secret formats can slip past
  the patterns. The real protection is `capture_command = false` by default;
  the docstring and README note must say so explicitly.
- **Retention:** on each invocation, if `retention_days > 0` and the events file's
  oldest entry exceeds it, rewrite the file dropping expired lines (amortized:
  only when file mtime is > 24h old, to stay within budget)
- Storage: state_dir/session/bash_events.jsonl, permissions 0o600
- Always returns `CheckResult.allow()`

**Config:** `[gates.bash_audit]` + `[gates.bash_audit.redaction]` as defined in Part 1

**Tests:** (1) disabled → no file; (2) enabled no capture → hash only; (3) capture with secrets → redacted; (4) invalid regex in config → fail-closed, event written without command text; (5) events older than retention_days → purged on next eligible invocation

---

### WP-F: Diff Coverage Gate (2.5 hrs)

**New file:** `scripts/coverage_gate.py`

- Stop hook check, order=55, budget_ms=100
- Reads pre-existing `coverage.json` (coverage.py format) — NOT generated in hook
- **Staleness guard:** if `coverage.json` mtime is older than the newest edit
  timestamp in edits.jsonl (beyond `max_staleness_seconds` tolerance), do NOT
  compute a percentage — emit a single advisory
  `"coverage data is stale — re-run tests to enable the coverage gate"` and allow.
  Rationale: stale data gives false verdicts twice over (missing new lines,
  line-number drift between the coverage run and current file state).
- Measures covered/total edited lines per .py file from edits.jsonl
- Advisory or block per mode when below threshold
- Silent skip when no coverage.json exists

**Config:** `[gates.coverage]` as defined in Part 1

**Tests:** (1) no coverage.json → allow, no advisory; (2) above threshold → allow; (3) below + advisory → advisory; (4) below + enforce → block; (5) coverage.json older than newest edit → staleness advisory, no percentage computed; (6) staleness within `max_staleness_seconds` tolerance → gate runs normally

---

### WP-G: Expand Discipline Link (1.5 hrs) — GATED on WP-C pilot metric

**Gate (defined, not vibes):** run the WP-C pilot for **2 weeks or 30 loop_detect
firings, whichever comes first**, using the `discipline_pilot.jsonl` telemetry.

- **Metric:** fraction of loop_detect firings followed by a *different* tool/target
  within the next 2 tool calls ("loop broken").
- **Pass:** loop-broken rate with reminder ≥ baseline (reminder suppressed by
  cooldown) + 10 percentage points, with ≥ 10 samples per arm.
- **Fail or insufficient data:** WP-G does not proceed; revisit reminder content
  instead of scaling it.

**Mappings:**
| Trigger | Skill | Theme |
|---|---|---|
| loop_detect | discipline-debugging | Observe, hypothesize, test |
| scope_creep | discipline-planning | Define blast radius |
| quality_gate (tests) | discipline-testing | Test error paths |
| lean_sniffers | discipline-coding | YAGNI ladder |

**Implementation:** Extract helpers from WP-C into `scripts/discipline_link.py`. Each check calls shared `get_reminder()`. Cooldowns via the shared `AdvisoryDeduplicator` (per-trigger dedupe keys).

**Config:** Per-trigger mappings in `[gates.discipline_link.mappings]`

---

## Execution Order & Parallelism

```
Phase 1 (validate feedback mechanism):
  WP-A ─── proves model responds to advisories (interim inline dedup)

Phase 2 (foundation):
  WP-B ─── advisory contract + aggregator cap (parallel with Phase 1 results)
  WP-D ─── budget fix + first consumer (independent)

Phase 2.5 (consolidation):
  WP-B2 ── migrate WP-A onto the contract (after A + B)

Phase 3 (integration):
  WP-C ─── discipline link pilot + telemetry (after WP-B2)
  WP-E ─── bash audit (independent)
  WP-F ─── coverage gate (independent)

Phase 4 (scale):
  WP-G ─── expand link (ONLY after WP-C pilot metric passes)
```

## Summary

| WP | Hours | Risk | Key Insight |
|---|---|---|---|
| A | 1 | Low | Proves feedback works before building more |
| B | 1.5 | Low | Shared, persisted contract + cross-check cap in Aggregator |
| B2 | 0.5 | Low | One dedup mechanism, not three |
| C | 2.5 | Low | Pilot one link, instrument it, then scale |
| D | 2.5 | Medium | Honest: cooperative — and at least one check consumes it |
| E | 2 | Low | Privacy-first, best-effort redaction stated, retention implemented |
| F | 2.5 | Medium | Read-only at Stop, off by default, stale data never scored |
| G | 1.5 | Low | Only after pilot passes a defined metric |
| **Total** | **14.5** | | |

---

## Appendix: Deferred to v0.9 (no implementing WP — intentionally NOT shipped)

The v1 plan sketched config for TDD-phase enforcement, plan-requirement
thresholds, and complexity limits. None had a work package, and shipping config
keys that silently do nothing is worse than omitting them (a user setting
`strictness = "strict"` would believe TDD is enforced). Recorded here as v0.9
candidates:

```toml
# [gates.complexity]     — max cyclomatic/cognitive, function/file line caps
# [gates.tdd]            — red/green phase enforcement, strictness levels
# [gates.plan]           — plan-required thresholds (files/lines/modules/risk labels)
# [gates.coverage]       — minimum_branch_percent (branch coverage; line-only in v0.8)
```

Each needs its own WP with tests, acceptance criteria, and an enforcement point
before any key is added to the schema.
