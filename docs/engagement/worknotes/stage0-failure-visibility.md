# Work Note — Stage 0: Failure-Visibility Hardening

Status: complete. Increments S0.1–S0.5 done.

## S0.1 — Dispatcher failure visibility (this increment)

**Problem** (orientation §7.1): `Aggregator` collected check crashes, timings,
and budget exhaustion, but `finish()` never emitted them; dispatcher-level
fail-open paths (bad stdin, normalize failure, config failure, registry
failure) left no persistent record. A chronically crashing gate was invisible.

**Changes**
- `fettle/trace.py`: `log_decision` now returns bool and warns **once per
  process on stderr** when the audit log is unwritable (loss of audit must not
  be silent, but a full disk must not break or spam the hook path). New
  `read_tail(max_bytes)` — bounded recent-history probe, never raises.
- `fettle/dispatcher_aggregate.py`: `add_system_advisory()` — cap-respecting
  advisory injection for dispatcher-originated messages.
- `fettle/dispatcher.py`: every fail-open path now writes a trace entry
  (`hook="dispatcher"`, status `input_error` / `config_error` /
  `registry_error` / `check_error` / `budget_exhausted`) plus a logger record.
  Check crashes are batched into ONE trace write per event (latency-bounded).
  Escalation: a check that has failed ≥3 times in 24h (counted from a bounded
  64KB trace tail) produces a visible in-session advisory pointing at
  `fettle doctor`.

**Decisions & rejected alternatives**
- *Per-error trace writes* rejected — one batched write bounds latency.
- *Trace every clean dispatch* rejected — noise; post_edit already traces the
  lint path. Dispatcher traces failures only.
- *Escalate on first failure* rejected — a one-off crash (e.g. transient FS
  error) would nag; 3-in-24h separates chronic from transient. Threshold is a
  module constant for now; will become `[dispatcher]` config in WP4.
- *Reading full trace for escalation* rejected — `read_tail` reads ≤64KB
  regardless of file size.
- *Fail-closed on check crash* deferred to S0.5: needs per-gate posture
  metadata (enforce-mode security gates only), designed with WP4.
- Self-referential guard: suppressing exceptions around `log_decision` is now
  acceptable *because* `log_decision` itself surfaces write failures on stderr.

**Verification**: 13 new tests (tests/test_dispatcher_failure_visibility.py) —
crash→trace, 3-crash escalation, single-crash silence, stale-window silence,
stdin/config/registry error tracing, budget-exhaustion tracing, write-failure
warn-once, read_tail bounds. Regression: test_dispatcher, test_trace,
test_health_telemetry, test_post_edit, test_report all green. Fettle self-check:
0 ERRORs (4 fixed in review: broad-except logging, suppress-with-rationale);
remaining warnings are the stdout hook protocol (pre-existing, correct).

## Remaining Stage-0 increments
- None — see below.

## S0.2 — doctor + report surface dispatch health

**Changes**
- `fettle/trace.py`: `probe_writable()` → `(ok, path-or-error)` — a doctor-time
  writability probe for the audit trace.
- `fettle/doctor.py`: new `check_dispatch_health()` — flags an unwritable audit
  trace and summarizes fail-open dispatch events from the last 7 days by
  status, naming the failing checks (e.g. `check_error×4 … lean_sniffers (4×)`).
  Advisory (`required=False`): degraded observability should not fail CI.
- `fettle/report.py`: `fettle report` now prints a "Dispatcher fail-open
  events" section — checks that silently didn't run, with counts.

**Decisions & rejected alternatives**
- *required=True doctor check* rejected — an unwritable trace is an
  observability problem, not a correctness problem; advisory + loud wording.
- *Unbounded trace read* rejected — 256KB tail cap, same rationale as S0.1.

**Verification**: 10 new tests (tests/test_doctor_dispatch_health.py) — clean
ok, failing-check names surfaced, unwritable trace flagged, never-required
contract, report section, probe_writable, doctor --json contract.

## S0.3 — CLI scanners stop swallowing tool failures

**Problem** (orientation §7.1): `security-review` with ruff AND semgrep dead
printed "0 findings" and exited 0. `threat-model` with dead grep printed "None
detected". `pr-review` with a broken quality scan reported a quiet zero.
`_cargo_check` timeout vanished. All read as "clean" when they mean "blind".

**Changes**
- `fettle/security_review.py`: `_run_ruff_security` / `_run_semgrep_owasp` now
  return `(findings, error)`; report carries `tool_errors`; `format_report`
  renders an "⚠ INCOMPLETE REVIEW — tool failures" section; `main()` exits 2
  when any tool failed (mirrors `fettle check` exit contract).
- `fettle/pr_review.py`: a failed quality scan renders "⚠ UNAVAILABLE — scan
  failed … Do not treat this PR as scanned." instead of zero counts.
- `fettle/threat_model.py`: grep probes unified into `_grep_probe` returning
  `(matches, errors)`; any probe failure inserts a "⚠ Auto-detection
  incomplete" banner at the top of the generated model.
- `fettle/stop_quality_gate.py`: `_cargo_check` timeout/OSError (toolchain
  present but check unrunnable) now leaves a `tool_error` audit-trace entry
  before failing open; toolchain-missing stays clean (doctor's job).

**Decisions & rejected alternatives**
- *Exit 1 on tool failure* rejected — 1 means "findings"; 2 distinguishes
  "review incomplete" so CI can gate differently.
- *Fail-closed cargo gate* rejected — Stop-hook budget forbids retries and a
  flaky cargo would block every session end; trace + doctor is proportionate.

**Verification**: updated tuple-contract tests + 5 new tests — incomplete
review section + tool_errors, clean-report negative case, threat-model
incomplete banner (probe timeout) + clean negative case.

## S0.4 — health telemetry write failures visible

`fettle/health_telemetry.py`: `record_loaded_rules` returns bool and warns
once per process on stderr on OSError (same pattern/rationale as trace.py —
losing the telemetry that detects silent degradation must not be silent).
2 new tests: returns-True on success; warn-once + returns-False on failure.

## S0.5 — mcp_trust_gate fails closed on unreadable allowlist

**Problem**: a corrupt/unreadable allowlist silently became an empty one —
protected-path and registry protections vanished exactly when tampering was
most likely.

**Changes**: `load_allowlist()` now returns `(allowlist, error)`, where a
*missing* file is benign (gate enabled but unconfigured — unchanged behavior)
but an *existing-yet-unreadable/corrupt* file is an error. Both entry points
(`main()` and dispatcher `run_check`) deny with "Failing closed. Fix or
restore <path>." when error is set.

**Decisions & rejected alternatives**
- *Deny on missing file too* rejected — would brick fresh enablement; missing
  ≠ tampered, and installs are still denied by the empty-allowlist default.

**Verification**: 3 new tests — corrupt allowlist denies benign command with
"Failing closed", missing allowlist stays benign, load_allowlist reports
corruption. Full suite: 1176 passed, 4 skipped. Fettle self-check: 0 ERRORs.
