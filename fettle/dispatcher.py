#!/usr/bin/env python3
"""Fettle Single Dispatcher — v2 Foundation.

One Python process per hook event. Reads stdin once, loads config once,
selects and runs applicable checks, aggregates output.

Fail-open on all errors. Never crashes the session.
"""

from __future__ import annotations

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
from fettle.dispatcher_types import CheckResult, HookContext, HookInput  # noqa: E402


logger = logging.getLogger(__name__)


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
    except Exception:  # noqa: BLE001 — fail-open by design
        print(_empty_output())
        return 0

    event_name = str(payload.get("hook_event_name") or "")

    try:
        cwd_raw = payload.get("cwd") or os.getcwd()
        cwd = Path(cwd_raw)
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        hook_input = HookInput(
            hook_event_name=event_name,
            tool_name=payload.get("tool_name"),
            tool_input=tool_input,
            cwd=cwd,
            session_id=payload.get("session_id"),
            raw=payload,
        )
    except Exception:  # noqa: BLE001 — fail-open by design
        print(_empty_output(event_name))
        return 0

    try:
        config = load_config(str(cwd))
    except Exception:  # noqa: BLE001 — fail-open by design
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
    except Exception:  # noqa: BLE001 — fail-open by design
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

    output, exit_code = aggregator.finish()
    print(json.dumps(output, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 — last-resort fail-open
        traceback.print_exc(file=sys.stderr)
        print(_empty_output())
        raise SystemExit(0) from None
