"""Gemini CLI hook payload translator (Stage 13).

Gemini CLI hooks deliver snake_case JSON on stdin with the same field
names as Claude Code (``hook_event_name``, ``tool_name``, ``tool_input``,
``cwd``, ``session_id``) but their own event and tool vocabularies
(docs/hooks/reference.md):

    BeforeTool / AfterTool / AfterAgent  ->  PreToolUse / PostToolUse / Stop
    run_shell_command / write_file / replace / read_file
                                         ->  Bash / Write / Edit / Read

Tool argument keys are already snake_case (``file_path``, ``command``,
``old_string`` …), so only the vocabularies need mapping. Detection keys
off the Gemini event names — they never collide with Claude/Codex events.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fettle.dispatcher_types import HookInput
from fettle.agents.tools import canonical_tool, targets

_EVENT_MAP = {
    "BeforeTool": "PreToolUse",
    "AfterTool": "PostToolUse",
    "AfterAgent": "Stop",
}

def matches(payload: dict[str, Any]) -> bool:
    """Gemini payloads carry a Gemini-vocabulary ``hook_event_name``."""
    return payload.get("hook_event_name") in _EVENT_MAP


def translate(payload: dict[str, Any], fallback_cwd: str) -> HookInput:
    event = _EVENT_MAP.get(str(payload.get("hook_event_name")), "")

    tool_raw = payload.get("tool_name")
    tool_name = canonical_tool(tool_raw)

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    cwd_raw = payload.get("cwd")
    if not isinstance(cwd_raw, str) or not cwd_raw:
        cwd_raw = fallback_cwd or os.getcwd()

    session_id = payload.get("session_id")
    if not isinstance(session_id, str):
        session_id = None

    return HookInput(
        hook_event_name=event,
        tool_name=tool_name,
        tool_input=tool_input,
        cwd=Path(cwd_raw),
        session_id=session_id,
        raw=payload,
        invocation_cwd=Path(cwd_raw),
        targets=targets(tool_input),
    )
