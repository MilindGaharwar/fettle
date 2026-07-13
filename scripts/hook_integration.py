"""Fettle v0.5.0 — WP-76: Hook integration for tiered checks.

Maps Claude Code hook events to the appropriate check tier and
formats results for hook output.
"""

from __future__ import annotations

import re
from typing import Any

from finding import CheckResult


_GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b")
_GIT_PUSH_RE = re.compile(r"\bgit\s+push\b")


def determine_tier_for_event(
    event: str,
    tool: str | None = None,
    command: str | None = None,
) -> str:
    """Determine which check tier to run based on hook event context.

    Returns: 'fast', 'changed', 'deferred', or 'none'.
    """
    if event == "Stop":
        return "deferred"

    if event == "PostToolUse":
        if tool in ("Write", "Edit"):
            return "fast"
        if tool == "Bash" and command and (
            _GIT_COMMIT_RE.search(command) or _GIT_PUSH_RE.search(command)
        ):
            return "changed"
        return "none"

    if event == "PreToolUse":
        return "none"

    return "none"


def format_hook_output(
    result: CheckResult,
    tier: str,
    hook_event: str = "PostToolUse",
) -> dict[str, Any]:
    """Format CheckResult as Claude Code hook output JSON."""
    if not result.findings:
        return {}

    lines = []
    for f in result.findings:
        sev = f.severity.value.upper()
        loc = f"{f.file}:{f.line}" if f.file and f.line else ""
        code_part = f" {f.code}" if f.code else ""
        lines.append(f"[{sev}] {loc}{code_part} — {f.message}")
        if f.suggested_fix:
            lines.append(f"  fix: {f.suggested_fix}")

    text = "\n".join(lines)

    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": hook_event,
            "additionalContext": text,
        }
    }

    if result.has_blocking:
        output["decision"] = "block"
        output["reason"] = text

    return output
