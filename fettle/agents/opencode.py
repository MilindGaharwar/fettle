"""OpenCode plugin event translator (WP-140).

OpenCode's native plugin events look like:

    {"type": "tool.execute.before",
     "tool": "edit",
     "args": {"filePath": "/x/a.py", ...},
     "directory": "/repo", "sessionID": "s1"}

    {"type": "session.idle", "properties": {"sessionID": "s1"}, "directory": "/repo"}

Historically the TypeScript shim (integrations/opencode/fettle.ts)
re-shaped these into Claude-style payloads before piping to the
dispatcher. That translation now lives here so it is versioned and
conformance-tested in one language; the TS shim can pass native events
through unchanged (it may keep pre-shaping during the deprecation
window — `matches` recognizes only native shapes, so pre-shaped
payloads simply take the Claude Code path, which is identical).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fettle.dispatcher_types import HookInput

_EVENT_MAP = {
    "tool.execute.before": "PreToolUse",
    "tool.execute.after": "PostToolUse",
    "session.idle": "Stop",
}

_TOOL_MAP = {
    "bash": "Bash",
    "edit": "Edit",
    "read": "Read",
    "write": "Write",
}


def matches(payload: dict[str, Any]) -> bool:
    """OpenCode native events carry `type` from the plugin event vocabulary."""
    return payload.get("type") in _EVENT_MAP


def _normalize_args(args: dict[str, Any]) -> dict[str, Any]:
    """camelCase OpenCode args -> snake_case tool_input keys."""
    normalized = dict(args)
    file_path = args.get("filePath", args.get("file_path"))
    if isinstance(file_path, str):
        normalized["file_path"] = file_path
    return normalized


def translate(payload: dict[str, Any], fallback_cwd: str) -> HookInput:
    event = _EVENT_MAP.get(str(payload.get("type")), "")

    tool_raw = payload.get("tool")
    tool_name = _TOOL_MAP.get(str(tool_raw).lower()) if isinstance(tool_raw, str) else None

    args = payload.get("args")
    tool_input = _normalize_args(args) if isinstance(args, dict) else {}

    cwd_raw = payload.get("directory")
    if not isinstance(cwd_raw, str) or not cwd_raw:
        cwd_raw = fallback_cwd or os.getcwd()

    session_id = payload.get("sessionID")
    if not isinstance(session_id, str):
        properties = payload.get("properties")
        session_id = properties.get("sessionID") if isinstance(properties, dict) else None
        if not isinstance(session_id, str):
            session_id = None

    return HookInput(
        hook_event_name=event,
        tool_name=tool_name,
        tool_input=tool_input,
        cwd=Path(cwd_raw),
        session_id=session_id,
        raw=payload,
    )
