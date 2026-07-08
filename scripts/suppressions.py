"""Fettle rule suppressions — skip specific findings with reason and expiry.

Configuration in .fettle.toml:

    [[suppressions]]
    tool = "semgrep"
    rule = "sql-fstring"
    path = "legacy/old_code.py"
    reason = "Legacy migration, rewrite planned Q3"
    expires = "2026-09-01"
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Suppression:
    tool: str
    rule: str
    path: str
    reason: str
    expires: str


def load_suppressions(config: dict) -> list[Suppression]:
    """Load suppressions from config."""
    raw = config.get("suppressions", [])
    suppressions = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        suppressions.append(Suppression(
            tool=entry.get("tool", ""),
            rule=entry.get("rule", ""),
            path=entry.get("path", ""),
            reason=entry.get("reason", ""),
            expires=entry.get("expires", ""),
        ))
    return suppressions


def is_suppressed(finding: dict, suppressions: list[Suppression]) -> bool:
    """Check if a finding matches an active (non-expired) suppression."""
    today = date.today().isoformat()

    for s in suppressions:
        if s.expires and s.expires < today:
            continue

        tool_match = not s.tool or s.tool == finding.get("tool", finding.get("source", ""))
        rule_match = not s.rule or s.rule == finding.get("rule", finding.get("code", ""))
        path_match = not s.path or s.path in str(finding.get("file", finding.get("path", "")))

        if tool_match and rule_match and path_match:
            return True

    return False


def filter_suppressed(findings: list[dict], config: dict) -> tuple[list[dict], list[dict]]:
    """Split findings into active and suppressed.

    Returns (active_findings, suppressed_findings).
    """
    suppressions = load_suppressions(config)
    if not suppressions:
        return findings, []

    active = []
    suppressed = []
    for f in findings:
        if is_suppressed(f, suppressions):
            suppressed.append(f)
        else:
            active.append(f)

    return active, suppressed


def expiring_soon(config: dict, days: int = 14) -> list[Suppression]:
    """Find suppressions expiring within N days."""
    from datetime import datetime, timedelta
    suppressions = load_suppressions(config)
    cutoff = (datetime.now() + timedelta(days=days)).date().isoformat()
    today = date.today().isoformat()

    return [s for s in suppressions if s.expires and today <= s.expires <= cutoff]
