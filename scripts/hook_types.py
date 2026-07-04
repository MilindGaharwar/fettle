"""Fettle hook JSON contract types.

TypedDict definitions for the stdin/stdout JSON shapes that Claude Code
sends to PreToolUse / PostToolUse / Stop hooks and expects back.
"""

from __future__ import annotations

from typing import TypedDict


class ToolInput(TypedDict, total=False):
    """Tool-specific input fields. Shape varies by tool_name."""

    file_path: str
    command: str
    old_string: str
    new_string: str
    content: str
    description: str


class HookInput(TypedDict, total=False):
    """JSON blob that Claude Code writes to hook stdin."""

    tool_name: str
    tool_input: ToolInput
    cwd: str
    session_id: str
    stop_hook_active: bool


class HookSpecificOutput(TypedDict, total=False):
    """Inner detail block returned inside HookResponse."""

    hookEventName: str
    permissionDecision: str
    permissionDecisionReason: str
    additionalContext: str


class HookResponse(TypedDict, total=False):
    """JSON blob that a hook prints to stdout."""

    decision: str
    reason: str
    hookSpecificOutput: HookSpecificOutput
