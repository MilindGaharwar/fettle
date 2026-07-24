#!/usr/bin/env python3
"""Fettle explain — show why the last hook decision was made.

Reads from the trace log and presents a human-readable explanation.

Usage:
    python3 explain.py [--last N]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.trace import get_recent_decisions


def explain_entry(entry: dict) -> str:
    """Format a single trace entry as a human-readable explanation."""
    lines = []
    hook = entry.get("hook", "unknown")
    status = entry.get("status", "unknown")
    tool = entry.get("tool", "")
    file_path = entry.get("file", "")
    findings = entry.get("findings", [])
    ts = entry.get("timestamp", "")
    duration = entry.get("duration_ms", 0)

    lines.append(f"  Time: {ts}")
    lines.append(f"  Hook: {hook}")
    lines.append(f"  Status: {status}")

    if tool:
        lines.append(f"  Tool: {tool}")
    if file_path:
        lines.append(f"  File: {file_path}")
    if duration:
        lines.append(f"  Duration: {duration:.0f}ms")

    if status == "pass":
        lines.append("  Outcome: No issues found — edit was allowed.")
    elif status == "violation":
        lines.append(f"  Outcome: {len(findings)} violation(s) found.")
        for f in findings[:5]:
            code = f.get("code", "")
            msg = f.get("message", "")
            loc = f"{f.get('file', '')}:{f.get('line', '')}" if f.get("file") else ""
            lines.append(f"    • [{code}] {loc} — {msg}")
        if len(findings) > 5:
            lines.append(f"    ... and {len(findings) - 5} more")
        lines.append("")
        lines.append("  To fix: address the violation(s) above.")
        lines.append(f"  To suppress: add `# noqa: {findings[0].get('code', '')}` (ruff) or `# nosemgrep: {findings[0].get('code', '')}` (semgrep)")
    elif status == "tool_error":
        lines.append("  Outcome: Tool error — Fettle could not run the check.")
        lines.append(f"  This is NOT a code quality issue. The tool ({tool}) may be missing or misconfigured.")
        lines.append("  Run `fettle doctor` to diagnose.")
    elif status == "config_error":
        lines.append("  Outcome: Configuration error — .fettle.toml may be invalid.")
    elif status == "skipped":
        lines.append("  Outcome: Skipped — file was not in scope for checking.")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle explain")
    parser.add_argument("--last", type=int, default=1, help="Show last N decisions")
    args = parser.parse_args()

    entries = get_recent_decisions(limit=args.last)
    if not entries:
        print("No Fettle decisions recorded yet.")
        print("Decisions are logged when hooks fire during Claude Code sessions.")
        return

    print(f"── Last {len(entries)} Fettle Decision(s) ──\n")
    for entry in reversed(entries):
        print(explain_entry(entry))
        print()


if __name__ == "__main__":
    main()
