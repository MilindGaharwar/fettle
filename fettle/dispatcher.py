#!/usr/bin/env python3
"""Fettle Single Dispatcher — v2 Foundation.

One Python process per hook event. Reads stdin once, loads config once,
selects and runs applicable checks, aggregates output.

Fail-open on all errors. Never crashes the session.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent  # repo root (clone mode)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fettle.config import load_config  # noqa: E402
from fettle.dispatcher_aggregate import Aggregator  # noqa: E402
from fettle.dispatcher_registry import select_checks  # noqa: E402
from fettle.dispatcher_types import CheckResult, HookContext  # noqa: E402
from fettle.trace import log_decision, read_tail  # noqa: E402


logger = logging.getLogger(__name__)

# Repeated-failure escalation: same check failing this many times within the
# window turns silent fail-open into a visible in-session advisory.
_ESCALATION_THRESHOLD = 3
_ESCALATION_WINDOW_S = 24 * 3600


def _trace_dispatch_failure(status: str, detail: str, session_id: str = "") -> None:
    """Record a dispatcher-level fail-open on the audit trail. Never raises."""
    # Tracing must never break the hook path; log_decision itself warns on
    # stderr if the audit log is unwritable, so suppression here is not silent.
    with contextlib.suppress(Exception):
        log_decision(
            hook="dispatcher",
            status=status,
            findings=[{"detail": detail[:500]}] if detail else [],
            session_id=session_id,
        )


def _repeated_failure_checks(errors: list[dict]) -> list[str]:
    """Names of checks that also failed >= threshold times in the window."""
    if not errors:
        return []
    try:
        now = time.time()
        counts: dict[str, int] = {}
        for entry in read_tail():
            if entry.get("hook") != "dispatcher" or entry.get("status") != "check_error":
                continue
            if now - float(entry.get("ts", 0)) > _ESCALATION_WINDOW_S:
                continue
            for finding in entry.get("findings", []):
                name = finding.get("check", "")
                if name:
                    counts[name] = counts.get(name, 0) + 1
        return [
            err["check"]
            for err in errors
            # The current run's failure is already traced before this check
            # runs, so the tail count includes it.
            if counts.get(err["check"], 0) >= _ESCALATION_THRESHOLD
        ]
    except Exception as exc:  # noqa: BLE001 — escalation is best-effort
        logger.error("fettle: failure-escalation probe failed: %s", exc, exc_info=True)
        return []


DEFAULT_EVENT_BUDGETS_MS = {
    "PreToolUse": 250,
    "PostToolUse": 400,
    "Stop": 600,
}


def _event_budget_ms(config: dict, event: str) -> int:
    dispatcher_cfg = config.get("dispatcher", {})
    by_event = dispatcher_cfg.get("event_budgets_ms", {}).get(event)
    if isinstance(by_event, int) and by_event > 0:
        return by_event
    global_budget = dispatcher_cfg.get("global_budget_ms")
    if isinstance(global_budget, int) and global_budget > 0:
        return global_budget
    return DEFAULT_EVENT_BUDGETS_MS.get(event, 400)


def _empty_output(event_name: str = "") -> str:
    hso = {"hookEventName": event_name} if event_name else {}
    return json.dumps({"hookSpecificOutput": hso}, separators=(",", ":"))


def main() -> int:
    start = time.monotonic()

    if os.environ.get("FETTLE_DISABLE_DISPATCHER") == "1":
        print(_empty_output())
        return 0

    try:
        raw_stdin = sys.stdin.read()
        payload = json.loads(raw_stdin or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception as exc:  # noqa: BLE001 — fail-open by design, but never silently
        logger.error("fettle: stdin parse failed: %s", exc, exc_info=True)
        _trace_dispatch_failure("input_error", f"{type(exc).__name__}: {exc}")
        print(_empty_output())
        return 0

    # WP-140: agent-specific payload parsing lives ONLY in fettle.agents.
    # The dispatcher consumes the normalized event model exclusively.
    try:
        from fettle.agents import normalize
        hook_input = normalize(payload, fallback_cwd=os.getcwd())
    except Exception as exc:  # noqa: BLE001 — fail-open by design, but never silently
        logger.error("fettle: event normalize failed: %s", exc, exc_info=True)
        _trace_dispatch_failure("input_error", f"normalize: {type(exc).__name__}: {exc}")
        print(_empty_output(str(payload.get("hook_event_name") or "")))
        return 0
    cwd = hook_input.cwd
    session_id = hook_input.session_id or ""

    try:
        config = load_config(str(cwd))
    except Exception as exc:  # noqa: BLE001 — fail-open by design, but never silently
        logger.error("fettle: config load failed: %s", exc, exc_info=True)
        _trace_dispatch_failure(
            "config_error", f"{type(exc).__name__}: {exc}", session_id
        )
        config = {}

    budget_ms = _event_budget_ms(config, hook_input.hook_event_name)
    deadline = start + (budget_ms / 1000.0)

    ctx = HookContext(
        input=hook_input,
        config=config,
        plugin_root=_REPO_ROOT,
        hook_start_monotonic=start,
        global_deadline_monotonic=deadline,
    )

    advisory_cfg = config.get("gates", {}).get("advisory", {})
    aggregator = Aggregator(
        total_budget_ms=budget_ms,
        hook_event_name=hook_input.hook_event_name,
        max_advisories_per_turn=int(advisory_cfg.get("max_per_turn", 3)),
        max_advisory_bytes=int(advisory_cfg.get("max_total_bytes", 2048)),
    )

    try:
        checks = select_checks(ctx)
    except Exception as exc:  # noqa: BLE001 — fail-open by design, but never silently
        logger.error("fettle: check registry failed: %s", exc, exc_info=True)
        _trace_dispatch_failure(
            "registry_error", f"{type(exc).__name__}: {exc}", session_id
        )
        checks = []

    for spec in checks:
        if time.monotonic() > deadline:
            aggregator.record_budget_exhausted(spec.name)
            break

        check_start = time.monotonic()

        # WP-D: Per-check deadline = min(global, start + budget_ms)
        check_deadline = deadline
        if spec.budget_ms:
            check_deadline = min(deadline, check_start + spec.budget_ms / 1000.0)

        ctx.check_deadline_monotonic = check_deadline

        try:
            result = spec.run(ctx)
            if result is None:
                result = CheckResult.allow()
        except Exception as exc:  # noqa: BLE001 — isolate check failures
            logger.error("fettle: check %s failed: %s", spec.name, exc)
            aggregator.record_check_error(spec.name, f"{type(exc).__name__}: {exc}")
            continue

        elapsed_ms = int((time.monotonic() - check_start) * 1000)
        aggregator.add_result(spec.name, result, elapsed_ms)

        # WP-D: Log overruns for observability
        if time.monotonic() > check_deadline:
            logger.warning(
                "fettle: check %s overran budget (%dms budget, %dms actual)",
                spec.name, spec.budget_ms or 0, elapsed_ms,
            )

        if aggregator.has_block:
            break

    # Stage-0 failure visibility: a check crash or budget kill is a fail-open
    # that MUST leave a persistent record and, when chronic, become visible
    # in-session. One bounded trace write; escalation reads a bounded tail.
    if aggregator.errors:
        _trace_dispatch_failure_findings(aggregator.errors, session_id)
        for name in _repeated_failure_checks(aggregator.errors):
            aggregator.add_system_advisory(
                f"fettle: check '{name}' has failed repeatedly and is being "
                "skipped (fail-open) — findings may be missed. "
                "Run `fettle doctor` to diagnose."
            )
    if aggregator.budget_exhausted_before:
        # Suppression is not silent: log_decision warns on stderr if unwritable.
        with contextlib.suppress(Exception):
            log_decision(
                hook="dispatcher",
                status="budget_exhausted",
                findings=[{
                    "skipped_from": aggregator.budget_exhausted_before,
                    "budget_ms": budget_ms,
                    "event": hook_input.hook_event_name,
                }],
                session_id=session_id,
            )

    output, exit_code = aggregator.finish()
    print(json.dumps(output, separators=(",", ":")))
    return exit_code


def _trace_dispatch_failure_findings(errors: list[dict], session_id: str) -> None:
    """Persist per-check crash details as one trace entry. Never raises."""
    # Suppression is not silent: log_decision warns on stderr if unwritable.
    with contextlib.suppress(Exception):
        log_decision(
            hook="dispatcher",
            status="check_error",
            findings=[
                {"check": e.get("check", ""), "error": str(e.get("error", ""))[:500]}
                for e in errors
            ],
            session_id=session_id,
        )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 — last-resort fail-open
        traceback.print_exc(file=sys.stderr)
        print(_empty_output())
        raise SystemExit(0) from None
