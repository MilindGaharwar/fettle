"""Fettle result taxonomy — explicit categories for hook outcomes.

Every hook must return one of these result types. This eliminates confusion
between policy violations, tool errors, and infrastructure failures.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class ResultStatus(str, Enum):
    """Explicit outcome categories for hook execution."""

    PASS = "pass"
    VIOLATION = "violation"
    TOOL_ERROR = "tool_error"
    CONFIG_ERROR = "config_error"
    SKIPPED = "skipped"


class Severity(str, Enum):
    """Finding severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    """A single quality finding from any tool."""

    tool: str
    severity: Severity
    path: str | None = None
    line: int | None = None
    column: int | None = None
    code: str | None = None
    message: str = ""
    fixable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {k: v.value if isinstance(v, Enum) else v for k, v in asdict(self).items() if v is not None}


@dataclass
class HookResult:
    """Complete result from a hook execution."""

    status: ResultStatus
    findings: list[Finding] = field(default_factory=list)
    message: str = ""
    tool_name: str = ""
    duration_ms: float = 0.0

    @property
    def has_errors(self) -> bool:
        return any(f.severity == Severity.ERROR for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity == Severity.WARNING for f in self.findings)

    def to_hook_output(self, hook_event: str = "PostToolUse", block: bool = False) -> dict[str, Any]:
        """Convert to Claude Code hook output JSON."""
        if self.status == ResultStatus.PASS or (self.status == ResultStatus.SKIPPED):
            return {}

        lines = []
        if self.status == ResultStatus.TOOL_ERROR:
            lines.append(f"[Fettle Tool Error] {self.message}")
        elif self.status == ResultStatus.CONFIG_ERROR:
            lines.append(f"[Fettle Config Error] {self.message}")
        else:
            for f in self.findings:
                sev = f.severity.value.upper()
                loc = f"{f.path}:{f.line}" if f.path and f.line else f.path or ""
                lines.append(f"[{sev}] {loc} {f.code or ''} — {f.message}")

        text = "\n".join(lines)

        output: dict[str, Any] = {
            "hookSpecificOutput": {
                "hookEventName": hook_event,
                "additionalContext": text,
            }
        }

        if block and self.has_errors:
            output["decision"] = "block"
            output["reason"] = text

        return output

    def emit_and_exit(self, hook_event: str = "PostToolUse", block: bool = False) -> None:
        """Print hook output JSON and exit with appropriate code."""
        if self.status in (ResultStatus.PASS, ResultStatus.SKIPPED) and not self.findings:
            sys.exit(0)

        output = self.to_hook_output(hook_event, block)
        if output:
            print(json.dumps(output))

        if block and self.has_errors:
            sys.exit(2)
        sys.exit(0)


def make_pass() -> HookResult:
    """Create a PASS result."""
    return HookResult(status=ResultStatus.PASS)


def make_violation(findings: list[Finding], tool_name: str = "") -> HookResult:
    """Create a VIOLATION result with findings."""
    return HookResult(status=ResultStatus.VIOLATION, findings=findings, tool_name=tool_name)


def make_tool_error(tool: str, message: str) -> HookResult:
    """Create a TOOL_ERROR result (tool not found, crashed, etc)."""
    return HookResult(status=ResultStatus.TOOL_ERROR, message=f"{tool}: {message}", tool_name=tool)


def make_config_error(message: str) -> HookResult:
    """Create a CONFIG_ERROR result."""
    return HookResult(status=ResultStatus.CONFIG_ERROR, message=message)


def make_skipped(reason: str = "") -> HookResult:
    """Create a SKIPPED result (file not in scope, gate disabled, etc)."""
    return HookResult(status=ResultStatus.SKIPPED, message=reason)
