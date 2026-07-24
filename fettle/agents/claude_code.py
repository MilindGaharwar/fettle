"""Claude Code hook payload translator (WP-140).

Claude Code delivers hook JSON on stdin with `hook_event_name`,
`tool_name`, `tool_input`, `cwd`, and `session_id`. This is Fettle's
canonical event vocabulary, so translation is mostly validation and
defaulting — but it is the ONLY place that vocabulary is parsed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fettle.dispatcher_types import HookInput

#: Events the dispatcher routes. Anything else still normalizes (fail-open).
KNOWN_EVENTS = frozenset({"PreToolUse", "PostToolUse", "Stop", "SubagentStart"})


def matches(payload: dict[str, Any]) -> bool:
    """Claude Code payloads carry `hook_event_name`."""
    return isinstance(payload.get("hook_event_name"), str)


def translate(payload: dict[str, Any], fallback_cwd: str) -> HookInput:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str):
        tool_name = None

    cwd_raw = payload.get("cwd")
    if not isinstance(cwd_raw, str) or not cwd_raw:
        cwd_raw = fallback_cwd or os.getcwd()

    session_id = payload.get("session_id")
    if not isinstance(session_id, str):
        session_id = None

    return HookInput(
        hook_event_name=str(payload.get("hook_event_name") or ""),
        tool_name=tool_name,
        tool_input=tool_input,
        cwd=Path(cwd_raw),
        session_id=session_id,
        raw=payload,
    )
