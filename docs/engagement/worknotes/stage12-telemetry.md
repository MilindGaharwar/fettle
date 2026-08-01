# Stage 12 — WP-148 Opt-in Telemetry (privacy-first)

Date: 2026-08 · Scope: enterprise plan WP-148 · Commit: see below

## What shipped

1. **`fettle/telemetry.py`** — payload schema `fettle-telemetry/1`: aggregate
   integers only (decisions / fired / blocked / overridden / tool_errors)
   plus the fettle version. The module docstring *is* the payload
   documentation; `test_payload_is_anonymous` pins the exact key set so the
   payload can't grow silently.
2. **Org-only opt-in** — `telemetry_settings()` honors `[telemetry] enabled`
   solely when it arrives via the digest-pinned central policy (WP-144
   `[extends]` cache). A repo-level `enabled = true` is *ignored and
   surfaced* in `fettle telemetry status` — an individual developer cannot
   opt a repo in, accidentally or otherwise. Default off: no config = no
   telemetry.
3. **CLI** — `fettle telemetry status` (enabled? by whom? where to?),
   `show [--days]` (the exact payload — the documented-payload requirement
   made executable), `send [--days]` (refused with exit 1 when disabled;
   fire-and-forget POST, 5 s timeout, never raises).
4. **Config surface** — `[telemetry] {enabled=false, endpoint=""}` in
   DEFAULTS, schema regenerated, docs/CONFIG.md section beside `[extends]`.

## Design decisions

- **Separate module, not health_telemetry.py.** The plan says "extend
  health_telemetry.py", but that module is the *rules-loaded health* trace
  writer (WP-121) — a different concern with a different audience. Org
  telemetry is a trace *consumer* like report.py/compliance.py; repo
  convention is one module per feature. Merging them would couple a hook-path
  writer with a network sender — exactly what the "never network in hooks"
  rule (audit D6) forbids.
- **"overridden" is reserved, not faked.** No current trace status maps to
  an override; the counter exists in the schema (so the payload contract is
  stable) and counts `overridden`/`override` statuses when gates start
  logging them. It reports 0 today — honest, not invented.
- **Endpoint must be https://** (loopback http allowed for tests). Enforced
  at settings resolution, so `send_payload`'s urlopen never sees an
  unvalidated scheme.
- **Sending is never wired into hooks.** Only the explicit `fettle telemetry
  send` CLI transmits; a cron/CI job is the intended caller. Hooks stay
  network-free.

## Verification

- `tests/test_telemetry.py` — 13 tests: opt-in matrix (default off,
  repo-enable ignored+surfaced, org-enable honored via real digest-pinned
  cache files, non-https rejected, org-policy-without-telemetry off),
  counter computation with window filtering, anonymity pin, live-HTTP send
  (loopback http.server) + failure path, CLI status/show/send-refused/
  send-enabled.
- Live smoke on this repo: status=off, show printed 1645 decisions / 847
  fired (real trace), send refused with exit 1.

## Follow-ups

- v1.3.x scope (WP-146/147/148) is complete — release cut candidate.
- Stage 13: runner adapters (codex/gemini/opencode) behind the
  fettle.runners protocol.
