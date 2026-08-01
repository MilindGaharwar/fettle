# Work Note — Stage 0: Failure-Visibility Hardening

Status: in progress. Increment S0.1 complete.

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
- S0.2: `doctor` + `report` surface dispatcher failure/budget events + trace
  writability probe.
- S0.3: CLI scanners (`security_review`, `threat_model`, `pr_review`,
  `deploy_gate`, `stop_quality_gate._cargo_check`) stop swallowing
  tool-missing/timeout — exit 2 / explicit tool_error findings.
- S0.4: health_telemetry write failures surfaced (same pattern as trace.py).
- S0.5: fail-closed posture for enforce-mode security gates
  (`mcp_trust_gate` unreadable allowlist ⇒ deny when enabled).
