# Fettle v0.8 Implementation Plan (Sol-Reviewed)

**Authored by:** GPT-5.6 Sol + Claude Opus (collaborative)
**Status:** Ready for implementation
**Total effort:** ~11 hours across 7 work packages

---

## Part 1: New User-Configurable Inputs (.fettle.toml)

These are NEW sections to add to the config schema (in `config.py` DEFAULTS):

```toml
[quality.coverage]
scope = "changed_lines"          # "project", "changed_files", or "changed_lines"
minimum_line_percent = 80.0      # Required coverage for edited lines
minimum_branch_percent = 70.0    # Required branch coverage (future)
on_unavailable = "warn"          # "ignore", "warn", or "fail" when coverage data missing

[quality.complexity]
max_cyclomatic = 10              # Max complexity for new/modified functions
max_cognitive = 15               # Max cognitive complexity
max_function_lines = 80          # 0 = disabled
max_file_lines = 500             # 0 = disabled
changed_code_only = true         # Only evaluate new/modified code
on_unavailable = "warn"

[process.tdd]
strictness = "advisory"          # "off", "advisory", "strict"
require_red_phase = true         # Test must fail before implementation
require_green_phase = true       # Test must pass after implementation
exempt_paths = ["docs/**", "**/*.md", "**/*.snap", "**/fixtures/**"]

[process.plan]
changed_files_threshold = 5      # Require plan when N+ files change
estimated_changed_lines_threshold = 150
affected_modules_threshold = 2
risk_labels = ["auth", "data", "migration", "privacy", "security"]
minimum_steps = 3                # Plan must have 3+ actionable steps
require_verification = true      # Plan must include verification criteria

[advisory]
cooldown_seconds = 300           # Min time before repeating same advisory
dedup_window_seconds = 900       # Same rule+file suppression window
aggressiveness = "medium"        # "low", "medium", "high"
max_per_turn = 3                 # Max advisories per hook event
allow_escalation = true          # Changed finding can bypass cooldown

[disciplines]
active_skills = [                # Skill IDs to link with hooks
  "systematic-debugging",
  "verification-before-completion",
  "writing-plans",
]
reminder_style = "compact"       # "silent", "compact", "guided"
reminder_timing = "on_violation" # "on_violation", "before_action", "both"
reminder_cooldown_seconds = 600  # Don't repeat same skill reminder within this

[audit.bash]
enabled = false                  # Opt-in only
capture_command = false          # If true, logs redacted command text
capture_exit_code = true
capture_duration = true
retention_days = 14              # Auto-delete after N days (0 = keep forever)

[audit.redaction]
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

    # Deduplicate by dedupe_key
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
        "hookEventName": "PostToolUse", "additionalContext": text,
    })
```

**Tests:** (1) silent mode with findings → allow; (2) advisory mode, 5 findings with 2 dupes → 3 unique surfaced; (3) advisory mode, 0 findings → allow

**Acceptance:** Silent unchanged. Non-silent surfaces max 3 deduped. JSONL always written. No regressions.

---

### WP-B: Normalized Advisory Contract (1 hr)

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
    def __init__(self, cooldown_s: float = 300.0): ...
    def should_emit(self, advisory: Advisory) -> bool: ...

def format_advisories(advisories: list[Advisory], max_total_bytes: int = 2048) -> str: ...
```

**Migration:** Additive. Existing checks unchanged. New checks and WP-LINK use Advisory.

**Tests:** (1) dedup within cooldown → suppressed; (2) after cooldown → emitted; (3) format respects size cap; (4) auto-generated dedupe_key deterministic

---

### WP-C: Discipline Link Pilot — loop_detect (2 hrs)

**Problem:** loop_detect gives generic advice. Should inject discipline-debugging reminder.

**Changes to `scripts/loop_detect.py`:**

```python
_FALLBACK_REMINDER = (
    "Pause and inspect the evidence before repeating the same action. "
    "Form a new hypothesis, then choose a tool call that tests it."
)

def _load_discipline_snippet(config): ...  # Load 2 sentences from SKILL.md
def _reminder_due(state_dir, session_id, cooldown_s): ...  # Timestamp-based dedup
```

After existing advisory message construction:
```python
    disc_cfg = ctx.config.get("gates", {}).get("discipline_link", {})
    cooldown = disc_cfg.get("cooldown_seconds", 300)
    if _reminder_due(state_dir, session_id, cooldown):
        snippet = _load_discipline_snippet(ctx.config)
        if snippet:
            msg += f"\n\nDiscipline reminder: {snippet}"
```

**Config:**
```toml
[gates.discipline_link]
enabled = true
skills_path = "~/.claude/plugins/disciplines/skills"
cooldown_seconds = 300
```

**Tests:** (1) disciplines present → 2-sentence reminder appended; (2) absent → fallback; (3) within cooldown → no reminder

**Acceptance:** Graceful absence. Max 2 sentences. p95 < 50ms. Cooldown enforced.

---

### WP-D: Cooperative Budget Enforcement (2 hrs)

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

**Note:** Cooperative only — checks should self-budget. No thread killing. Overruns logged for observability, not enforced by process kill.

**Tests:** (1) check within budget → no log; (2) check over budget → overrun logged; (3) global deadline clamp works

---

### WP-E: Bash Structured Audit (1.5 hrs)

**New file:** `scripts/bash_audit.py`

- PostToolUse(Bash) check, order=99, budget_ms=30
- Logs: timestamp, command_hash, exit_code, duration_ms
- NOT raw commands by default (privacy-first)
- Opt-in `capture_command` applies redaction before write
- Redaction: regex patterns from config, fail-closed on invalid regex
- Storage: state_dir/session/bash_events.jsonl, permissions 0o600
- Always returns `CheckResult.allow()`

**Config:** `[gates.bash_audit]` with `enabled=false`, `capture_command=false`, `redaction_patterns=[...]`

**Tests:** (1) disabled → no file; (2) enabled no capture → hash only; (3) capture with secrets → redacted

---

### WP-F: Diff Coverage Gate (2 hrs)

**New file:** `scripts/coverage_gate.py`

- Stop hook check, order=55, budget_ms=100
- Reads pre-existing `coverage.json` (coverage.py format) — NOT generated in hook
- Measures covered/total edited lines per .py file from edits.jsonl
- Advisory or block per mode when below threshold
- Silent skip when no coverage.json exists

**Config:** `[gates.coverage]` with `enabled=false`, `threshold=80`, `mode="advisory"`, `scope="changed_lines"`

**Tests:** (1) no coverage.json → allow; (2) above threshold → allow; (3) below + advisory → advisory; (4) below + enforce → block

---

### WP-G: Expand Discipline Link (1.5 hrs) — GATED on WP-C pilot success

**Prerequisite:** WP-C demonstrates measurable improvement.

**Mappings:**
| Trigger | Skill | Theme |
|---|---|---|
| loop_detect | discipline-debugging | Observe, hypothesize, test |
| scope_creep | discipline-planning | Define blast radius |
| quality_gate (tests) | discipline-testing | Test error paths |
| lean_sniffers | discipline-coding | YAGNI ladder |

**Implementation:** Extract helpers from WP-C into `scripts/discipline_link.py`. Each check calls shared `get_reminder()`.

**Config:** Per-trigger mappings in `[gates.discipline_link.mappings]`

---

## Execution Order & Parallelism

```
Phase 1 (validate feedback mechanism):
  WP-A ─── proves model responds to advisories

Phase 2 (foundation):
  WP-B ─── advisory contract (parallel with Phase 1 results)
  WP-D ─── budget fix (independent)

Phase 3 (integration):
  WP-C ─── discipline link pilot (after WP-A validates)
  WP-E ─── bash audit (independent)
  WP-F ─── coverage gate (independent)

Phase 4 (scale):
  WP-G ─── expand link (ONLY after WP-C proven)
```

## Summary

| WP | Hours | Risk | Key Insight |
|---|---|---|---|
| A | 1 | Low | Proves feedback works before building more |
| B | 1 | Low | Shared contract prevents ad-hoc advisory chaos |
| C | 2 | Low | Pilot one link, measure, then scale |
| D | 2 | Medium | Honest: cooperative, not enforced |
| E | 1.5 | Low | Privacy-first, audit-only, never blocks |
| F | 2 | Medium | Read-only at Stop, off by default |
| G | 1.5 | Low | Only after pilot proves value |
| **Total** | **11** | | |
