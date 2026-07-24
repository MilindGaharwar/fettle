"""Fettle v0.5.0 — WP-98: Generated code / schema drift detection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fettle.finding import CheckFinding, FindingSeverity


def check_schema_drift(cwd: str, config: list[dict[str, Any]]) -> list[CheckFinding]:
    """Detect stale generated files when source schemas change."""
    root = Path(cwd)
    findings: list[CheckFinding] = []

    for entry in config:
        source = root / entry["source"]
        output = root / entry["output"]
        command = entry.get("command", "")

        if not source.is_file():
            continue
        if not output.is_file():
            findings.append(CheckFinding(
                checker="schema-drift",
                severity=FindingSeverity.WARNING,
                file=entry["output"],
                line=0,
                message=f"Generated file missing. Source '{entry['source']}' exists but output doesn't.",
                suggested_fix=f"Run: {command}" if command else None,
            ))
            continue

        if source.stat().st_mtime_ns > output.stat().st_mtime_ns:
            findings.append(CheckFinding(
                checker="schema-drift",
                severity=FindingSeverity.WARNING,
                file=entry["output"],
                line=0,
                message=f"Possible drift: '{entry['source']}' is newer than '{entry['output']}'",
                suggested_fix=f"Run: {command}" if command else "Regenerate the output file",
                rerun_command=command or None,
            ))

    return findings
