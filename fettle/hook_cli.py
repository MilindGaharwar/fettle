"""Legacy script adapter for dispatcher check functions."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

from fettle.agents import normalize
from fettle.config import load_config
from fettle.dispatcher_types import CheckResult, Decision, HookContext
from fettle.paths import find_project_root


def context_from_stdin() -> HookContext | None:
    """Build the same normalized context used by the shipped dispatcher."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        return None
    if not isinstance(payload, dict):
        return None
    if "hook_event_name" not in payload and isinstance(payload.get("hook_event"), str):
        payload["hook_event_name"] = payload["hook_event"]
    if "hook_event_name" not in payload and "stop_hook_active" in payload:
        payload["hook_event_name"] = "Stop"
    hook_input = normalize(payload, str(Path.cwd()))
    invocation_cwd = hook_input.invocation_cwd or hook_input.cwd
    root = find_project_root(invocation_cwd)
    hook_input = type(hook_input)(
        hook_event_name=hook_input.hook_event_name,
        tool_name=hook_input.tool_name,
        tool_input=hook_input.tool_input,
        cwd=root,
        session_id=hook_input.session_id,
        raw=hook_input.raw,
        invocation_cwd=invocation_cwd,
        targets=hook_input.targets,
    )
    start = time.monotonic()
    return HookContext(
        input=hook_input,
        config=load_config(str(root)),
        plugin_root=Path(__file__).resolve().parent.parent,
        hook_start_monotonic=start,
        global_deadline_monotonic=start + 30,
    )


def emit(result: CheckResult) -> int:
    """Render a check result using the historical hook stdout protocol."""
    if result.decision == Decision.ALLOW and not result.message:
        return 0
    hook_output = dict(result.hook_specific_output)
    if not hook_output:
        hook_output = {"additionalContext": result.message or ""}
    output = {"hookSpecificOutput": hook_output}
    if result.decision == Decision.BLOCK:
        output.setdefault("decision", "block")
        output.setdefault("reason", result.message or "Blocked by Fettle")
    elif result.decision == Decision.ADVISORY:
        output.setdefault("decision", "continue")
        output.setdefault("reason", "[ADVISORY] " + (result.message or ""))
    print(json.dumps(output))  # nosemgrep: debug-print-statement -- hook stdout protocol
    return 2 if result.decision == Decision.BLOCK else 0


def run_main(
    run_check: Callable[[HookContext], CheckResult],
    *,
    advisory_to_stderr: bool = False,
) -> None:
    """Read stdin once, invoke the canonical check, and exit with its decision."""
    context = context_from_stdin()
    if context is None:
        raise SystemExit(0)
    result = run_check(context)
    if advisory_to_stderr and result.decision == Decision.ADVISORY:
        print(result.message or "", file=sys.stderr)
        raise SystemExit(0)
    raise SystemExit(emit(result))
