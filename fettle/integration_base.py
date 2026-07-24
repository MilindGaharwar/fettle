"""Shared IntegrationAdapter protocol for external tool integrations.

All vendor adapters implement this interface. Provides 5-state result
model and configurable fail-open/fail-closed behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class IntegrationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"
    MISCONFIGURED = "misconfigured"
    NOT_ENABLED = "not_enabled"


@dataclass
class IntegrationFinding:
    severity: str
    message: str
    file: str = ""
    line: int = 0
    code: str = ""
    url: str = ""


@dataclass
class IntegrationReport:
    status: IntegrationStatus
    findings: list[IntegrationFinding] = field(default_factory=list)
    summary: str = ""
    tool_version: str | None = None


class IntegrationAdapter(Protocol):
    name: str

    def is_available(self, config: dict[str, Any]) -> IntegrationStatus: ...

    def run(self, cwd: str, config: dict[str, Any]) -> IntegrationReport: ...


def format_integration_report(report: IntegrationReport, adapter_name: str) -> str:
    """Format an integration report as human-readable output."""
    lines = ["## " + adapter_name + " — " + report.status.value.upper()]
    if report.summary:
        lines.append(report.summary)
    if report.tool_version:
        lines.append("Tool version: " + report.tool_version)
    lines.append("")

    if report.findings:
        for f in report.findings[:20]:
            loc = (f.file + ":" + str(f.line)) if f.file else ""
            lines.append("- [" + f.severity + "] " + loc + " " + f.message)
        lines.append("")

    return "\n".join(lines)
