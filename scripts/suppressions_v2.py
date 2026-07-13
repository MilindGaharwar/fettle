"""Fettle v0.5.0 — WP-77: Suppressions and baselines v2.

Allow teams to adopt Fettle without fixing every historical issue.
Supports baseline files, inline suppressions, and expiry dates.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from finding import CheckFinding


_INLINE_RE = re.compile(
    r"#\s*fettle:ignore\[([^\]]+)\]\s*(.*)"
)


def parse_inline_suppression(line_content: str) -> dict[str, str] | None:
    """Parse an inline fettle:ignore comment. Returns {rule, reason} or None."""
    match = _INLINE_RE.search(line_content)
    if not match:
        return None
    return {
        "rule": match.group(1).strip(),
        "reason": match.group(2).strip(),
    }


def is_suppressed(finding: CheckFinding, suppression_rules: list[dict[str, Any]]) -> bool:
    """Check if a finding is suppressed by any active rule."""
    today = date.today().isoformat()
    for rule in suppression_rules:
        expires = rule.get("expires", "")
        if expires and expires <= today:
            continue
        if rule.get("checker") and rule["checker"] != finding.checker:
            continue
        if rule.get("rule") and rule["rule"] != finding.code:
            continue
        if rule.get("path") and finding.file and not finding.file.startswith(rule["path"]):
            continue
        return True
    return False


def _finding_key(f: CheckFinding) -> str:
    """Stable key for baseline matching."""
    return f"{f.file}:{f.line}:{f.code or f.checker}:{f.message}"


def create_baseline(findings: list[CheckFinding], path: str) -> None:
    """Create a baseline file from current findings."""
    entries = [_finding_key(f) for f in findings]
    Path(path).write_text(json.dumps(entries, indent=2))


def load_baseline(path: str) -> list[str]:
    """Load baseline entries from file. Returns [] on error."""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text())
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError) as e:
        print(f"fettle: invalid baseline at {path}: {e}", file=sys.stderr)
        return []


def apply_suppressions(
    findings: list[CheckFinding],
    baseline: list[str] | None = None,
    suppression_rules: list[dict[str, Any]] | None = None,
) -> list[CheckFinding]:
    """Filter findings against baseline and suppression rules."""
    result = []
    baseline_set = set(baseline) if baseline else set()

    for f in findings:
        key = _finding_key(f)
        if key in baseline_set:
            continue
        if suppression_rules and is_suppressed(f, suppression_rules):
            continue
        result.append(f)

    return result
