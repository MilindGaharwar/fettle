"""Fettle event model — normalized internal representation of hook events.

Replaces raw hook JSON with a typed dataclass. Resilient to Claude Code
payload shape changes — normalize once at the boundary, use typed data internally.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class HookType(StrEnum):
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"


@dataclass
class FettleEvent:
    """Normalized hook event — the single internal representation."""

    hook: HookType
    tool_name: str = ""
    file_path: str = ""
    changed_files: list[str] = field(default_factory=list)
    command: str = ""
    cwd: str = "."
    session_id: str = "unknown"
    repo_root: Path | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_stdin(cls, hook_type: HookType) -> FettleEvent:
        """Parse hook stdin JSON into a FettleEvent."""
        try:
            data = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError, EOFError):
            data = {}

        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        command = tool_input.get("command", "")

        changed_files = []
        if file_path:
            changed_files.append(file_path)

        return cls(
            hook=hook_type,
            tool_name=data.get("tool_name", ""),
            file_path=file_path,
            changed_files=changed_files,
            command=command,
            cwd=data.get("cwd", "."),
            session_id=data.get("session_id", "unknown"),
            raw_payload=data,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], hook_type: HookType) -> FettleEvent:
        """Create event from a pre-parsed dict (for testing)."""
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        return cls(
            hook=hook_type,
            tool_name=data.get("tool_name", ""),
            file_path=file_path,
            changed_files=[file_path] if file_path else [],
            command=tool_input.get("command", ""),
            cwd=data.get("cwd", "."),
            session_id=data.get("session_id", "unknown"),
            raw_payload=data,
        )

    @property
    def has_file(self) -> bool:
        return bool(self.file_path)

    @property
    def file_extension(self) -> str:
        if self.file_path:
            return Path(self.file_path).suffix
        return ""

    @property
    def is_python(self) -> bool:
        return self.file_extension in {".py", ".pyi"}

    @property
    def is_typescript(self) -> bool:
        return self.file_extension in {".ts", ".tsx"}

    @property
    def is_javascript(self) -> bool:
        return self.file_extension in {".js", ".jsx"}

    @property
    def is_frontend(self) -> bool:
        return self.is_typescript or self.is_javascript
