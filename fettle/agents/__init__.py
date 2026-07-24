"""WP-140 — Agent abstraction layer.

Normalizes native agent hook payloads into the dispatcher's `HookInput`
event model. Payload parsing lives ONLY here: the dispatcher consumes
normalized events and never touches agent-specific shapes.

Supported agents:
- Claude Code  (hook JSON with `hook_event_name`)
- OpenCode     (plugin event JSON with `type`: tool.execute.* / session.idle)

Unknown shapes fall back to the Claude Code translator, which is maximally
lenient — fail-open is the dispatcher contract.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from fettle.agents import claude_code, opencode
from fettle.dispatcher_types import HookInput


class AgentKind(StrEnum):
    CLAUDE_CODE = "claude_code"
    OPENCODE = "opencode"
    UNKNOWN = "unknown"


def detect_agent(payload: dict[str, Any]) -> AgentKind:
    """Identify the agent that produced *payload* from its shape."""
    if opencode.matches(payload):
        return AgentKind.OPENCODE
    if claude_code.matches(payload):
        return AgentKind.CLAUDE_CODE
    return AgentKind.UNKNOWN


def normalize(payload: dict[str, Any], fallback_cwd: str) -> HookInput:
    """Translate a native agent payload into a normalized `HookInput`.

    Never raises on malformed input — unknown shapes produce a lenient,
    mostly-empty event (the dispatcher then runs no checks and allows).
    """
    kind = detect_agent(payload)
    if kind is AgentKind.OPENCODE:
        return opencode.translate(payload, fallback_cwd)
    return claude_code.translate(payload, fallback_cwd)


__all__ = ["AgentKind", "detect_agent", "normalize"]
