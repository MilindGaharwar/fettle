"""Fettle v0.5.0 — WP-99: Database migration safety (advisory)."""

from __future__ import annotations

import re
from pathlib import Path

from fettle.finding import CheckFinding, FindingSeverity

_RISKY_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("DROP TABLE", re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE)),
    ("DROP COLUMN", re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE)),
    ("DROP DATABASE", re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE)),
    ("TRUNCATE", re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE)),
    ("NOT NULL without DEFAULT", re.compile(
        r"\bNOT\s+NULL\b(?!.*\bDEFAULT\b)", re.IGNORECASE
    )),
    ("RENAME TABLE", re.compile(r"\bRENAME\s+TABLE\b", re.IGNORECASE)),
]


def check_migration_safety(files: list[str]) -> list[CheckFinding]:
    """Flag risky migration patterns. Advisory only."""
    findings: list[CheckFinding] = []

    for file_path in files:
        try:
            content = Path(file_path).read_text()
        except OSError:
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            for desc, pattern in _RISKY_PATTERNS:
                if pattern.search(line):
                    findings.append(CheckFinding(
                        checker="migration-safety",
                        severity=FindingSeverity.WARNING,
                        file=file_path,
                        line=line_num,
                        message=f"Risky migration: {desc}",
                        blocking=False,
                    ))

    return findings
