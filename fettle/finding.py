"""Fettle v0.5.0 — WP-69: Structured finding/result schema.

The canonical format all checkers emit. Every downstream consumer
(runner, hooks, CI comparison, dashboard) reads this schema.

This extends the v0.4.0 result.py with richer metadata while remaining
backwards-compatible — existing hooks can continue using result.py.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


SCHEMA_VERSION = "0.5.0"
MAX_RAW_OUTPUT_LEN = 2048

_SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"(?i)(secret|password|token|key)\w*\s*[=:]\s*\S+"),
]


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def weight(self) -> int:
        return {"high": 3, "medium": 2, "low": 1}[self.value]


@dataclass
class CheckFinding:
    """A single quality finding from any checker."""

    checker: str
    severity: FindingSeverity
    file: str
    line: int
    message: str
    column: int | None = None
    code: str | None = None
    workspace: str | None = None
    blocking: bool | None = None
    confidence: Confidence = Confidence.HIGH
    suggested_fix: str | None = None
    rerun_command: str | None = None
    raw_tool_output: str | None = None
    redacted: bool = False

    def __post_init__(self):
        if self.blocking is None:
            self.blocking = self.severity == FindingSeverity.ERROR
        if self.raw_tool_output and len(self.raw_tool_output) > MAX_RAW_OUTPUT_LEN:
            self.raw_tool_output = self.raw_tool_output[:MAX_RAW_OUTPUT_LEN]

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "checker": self.checker,
            "severity": self.severity.value,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "blocking": self.blocking,
            "confidence": self.confidence.value,
        }
        if self.column is not None:
            data["column"] = self.column
        if self.code:
            data["code"] = self.code
        if self.workspace:
            data["workspace"] = self.workspace
        if self.suggested_fix:
            data["suggested_fix"] = self.suggested_fix
        if self.rerun_command:
            data["rerun_command"] = self.rerun_command
        if self.raw_tool_output:
            data["raw_tool_output"] = self.raw_tool_output
        if self.redacted:
            data["redacted"] = True
        return data

    def to_human(self) -> str:
        sev = self.severity.value.upper()
        loc = f"{self.file}:{self.line}"
        if self.column:
            loc += f":{self.column}"
        code_part = f" {self.code}" if self.code else ""
        return f"[{sev}] {loc}{code_part} — {self.message}"


@dataclass
class CheckResult:
    """Aggregated result from a check run (one or more checkers)."""

    findings: list[CheckFinding] = field(default_factory=list)
    duration_ms: float = 0.0
    checker: str | None = None
    workspace: str | None = None

    @property
    def has_blocking(self) -> bool:
        return any(f.blocking for f in self.findings)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.WARNING)

    @property
    def exit_code(self) -> int:
        if self.has_blocking:
            return 2
        if self.findings:
            return 1
        return 0


def sort_findings(findings: list[CheckFinding]) -> list[CheckFinding]:
    """Deterministic sort: file ASC, line ASC, severity weight DESC."""
    severity_order = {FindingSeverity.ERROR: 0, FindingSeverity.WARNING: 1, FindingSeverity.INFO: 2}
    return sorted(findings, key=lambda f: (f.file, f.line, severity_order.get(f.severity, 9)))


def redact_finding(f: CheckFinding) -> CheckFinding:
    """Return a copy with secrets redacted from message and raw_tool_output."""
    msg = f.message
    raw = f.raw_tool_output or ""
    for pat in _SECRET_PATTERNS:
        msg = pat.sub("***REDACTED***", msg)
        raw = pat.sub("***REDACTED***", raw)
    return CheckFinding(
        checker=f.checker,
        severity=f.severity,
        file=f.file,
        line=f.line,
        column=f.column,
        code=f.code,
        message=msg,
        workspace=f.workspace,
        blocking=f.blocking,
        confidence=f.confidence,
        suggested_fix=f.suggested_fix,
        rerun_command=f.rerun_command,
        raw_tool_output=raw if raw else None,
        redacted=True,
    )


def to_json(findings: list[CheckFinding]) -> str:
    """Serialize findings list to JSON string."""
    return json.dumps(
        {"schema_version": SCHEMA_VERSION, "findings": [f.to_dict() for f in findings]},
        indent=2,
    )


def to_human(findings: list[CheckFinding]) -> str:
    """Human-readable multi-line output, grouped by workspace if present."""
    if not findings:
        return ""
    sorted_f = sort_findings(findings)
    workspaces: dict[str, list[CheckFinding]] = {}
    for f in sorted_f:
        ws = f.workspace or ""
        workspaces.setdefault(ws, []).append(f)

    lines: list[str] = []
    if len(workspaces) == 1 and "" in workspaces:
        for f in sorted_f:
            lines.append(f.to_human())
    else:
        for ws in sorted(workspaces.keys()):
            if ws:
                lines.append(f"\n[{ws}]")
            for f in workspaces[ws]:
                lines.append(f"  {f.to_human()}" if ws else f.to_human())
    return "\n".join(lines)


def to_sarif(findings: list[CheckFinding]) -> dict[str, Any]:
    """Export findings as SARIF 2.1.0 for GitHub code scanning."""
    results = []
    rules_seen: dict[str, dict[str, Any]] = {}

    for f in findings:
        rule_id = f.code or f.checker
        if rule_id not in rules_seen:
            rules_seen[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": f.message},
            }
        level_map = {"error": "error", "warning": "warning", "info": "note"}
        result: dict[str, Any] = {
            "ruleId": rule_id,
            "level": level_map.get(f.severity.value, "warning"),
            "message": {"text": f.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.file},
                        "region": {"startLine": f.line},
                    }
                }
            ],
        }
        if f.column:
            result["locations"][0]["physicalLocation"]["region"]["startColumn"] = f.column
        results.append(result)

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "fettle",
                        "version": SCHEMA_VERSION,
                        "rules": list(rules_seen.values()),
                    }
                },
                "results": results,
            }
        ],
    }
