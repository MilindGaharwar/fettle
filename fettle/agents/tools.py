"""Canonical tool names and target extraction for agent hook payloads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_CANONICAL = {
    "bash": "Bash", "shell": "Bash", "local_shell": "Bash",
    "powershell": "Bash", "run_shell_command": "Bash",
    "write": "Write", "write_file": "Write",
    "edit": "Edit", "replace": "Edit", "notebookedit": "Edit",
    "multiedit": "Edit", "patch": "Edit", "apply_patch": "Edit",
    "read": "Read", "read_file": "Read",
    "grep": "Search", "glob": "Search", "search": "Search",
}
_PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def canonical_tool(name: str | None) -> str | None:
    if not isinstance(name, str):
        return None
    return _CANONICAL.get(name.casefold(), name)


def targets(tool_input: dict[str, Any]) -> tuple[Path, ...]:
    values: list[str] = []
    for key in ("file_path", "filePath", "path", "notebook_path", "notebookPath"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            values.append(value)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                for key in ("file_path", "filePath", "path", "notebook_path", "notebookPath"):
                    value = edit.get(key)
                    if isinstance(value, str) and value:
                        values.append(value)
                        break
    command = tool_input.get("command")
    if isinstance(command, str):
        values.extend(_PATCH_FILE_RE.findall(command))
    return tuple(dict.fromkeys(Path(value) for value in values))
