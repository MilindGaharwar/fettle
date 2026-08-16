"""Codex CLI hook payload translator (Stage 13).

Codex's hook wire is deliberately Claude Code-compatible: the same
snake_case stdin payload (``hook_event_name``, ``tool_name``,
``tool_input``, ``cwd``, ``session_id``) plus Codex extensions —
``turn_id`` (always present, per codex-rs/hooks schema.rs), ``model``,
``permission_mode``, ``tool_use_id``. Detection keys off ``turn_id``;
translation delegates to the Claude Code translator, which ignores the
extra fields.

One defensive divergence: Codex's native tool identifiers (``shell``,
``apply_patch``) are mapped to the canonical vocabulary in case they
appear on the wire instead of the Claude-style names Codex's own schema
fixtures use ("Bash"). Spec-derived — pinned by conformance fixtures,
re-verify against a live Codex install when available.
"""

from __future__ import annotations

import re
from typing import Any

from fettle.agents import claude_code
from fettle.dispatcher_types import HookInput

#: Codex-native tool ids -> canonical tool vocabulary (defensive; Codex's
#: own hook fixtures use Claude-style names like "Bash" already).
_TOOL_MAP = {
    "shell": "Bash",
    "local_shell": "Bash",
    "apply_patch": "Edit",
}

_PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def _normalize_tool_input(tool_name: str | None, tool_input: object) -> dict[str, Any]:
    normalized = dict(tool_input) if isinstance(tool_input, dict) else {}
    if tool_name != "apply_patch" or not isinstance(normalized.get("command"), str):
        return normalized
    paths = set(_PATCH_FILE_RE.findall(normalized["command"]))
    if len(paths) == 1:
        normalized["file_path"] = paths.pop()
    return normalized


def matches(payload: dict[str, Any]) -> bool:
    """Codex payloads are Claude-shaped plus a required ``turn_id``."""
    return (
        isinstance(payload.get("hook_event_name"), str)
        and isinstance(payload.get("turn_id"), str)
    )


def translate(payload: dict[str, Any], fallback_cwd: str) -> HookInput:
    tool_name = payload.get("tool_name")
    if isinstance(tool_name, str):
        payload = {
            **payload,
            "tool_name": _TOOL_MAP.get(tool_name, tool_name),
            "tool_input": _normalize_tool_input(tool_name, payload.get("tool_input")),
        }
    return claude_code.translate(payload, fallback_cwd)
