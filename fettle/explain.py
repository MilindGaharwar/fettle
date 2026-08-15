#!/usr/bin/env python3
"""Fettle explain — show why the last hook decision was made.

Reads from the trace log and presents a human-readable explanation.

Usage:
    python3 explain.py [--last N]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.trace import get_recent_decisions


def explain_entry(entry: dict, *, detailed: bool = False, json_output: bool = False) -> str:
    """Format a single trace entry as a human-readable explanation."""
    if json_output:
        return json.dumps(entry, sort_keys=True)
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
            if detailed:
                for label, key in (("Impact", "impact"), ("Action", "action"),
                                   ("Rerun", "rerun_command"), ("Evidence", "evidence_id")):
                    if f.get(key):
                        lines.append(f"      {label}: {f[key]}")
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
    elif status == "overridden":
        overrides = entry.get("overrides", [])
        lines.append("  Outcome: The check did not pass; an authorized override allowed it.")
        for override in overrides[:5]:
            lines.append(
                f"    {override.get('override_id', '?')} by {override.get('actor', '?')}: "
                f"{override.get('reason', '(no reason)')} (expires {override.get('expiry', '?')})"
            )
    elif status == "skipped":
        lines.append("  Outcome: Skipped — file was not in scope for checking.")

    if detailed and entry.get("evidence"):
        lines.append("  Evidence:")
        for evidence in entry["evidence"][:5]:
            detail = ", ".join(
                f"{key}={evidence[key]}" for key in ("exit_code", "duration_ms", "scope", "tool_version")
                if key in evidence
            )
            identity = evidence.get("artifact_digest") or evidence.get("evidence_id", "?")
            lines.append(f"    {identity} ({evidence.get('kind', '?')})"
                         + (f": {detail}" if detail else ""))
            inspection = evidence.get("inspection")
            if isinstance(inspection, dict):
                accepted = "accepted" if inspection.get("accepted") else "rejected"
                lines.extend((
                    f"      Decision: {accepted}; validity={inspection.get('validity', 'unknown')}; "
                    f"availability={evidence.get('availability', 'unknown')}",
                    f"      Producer: {inspection.get('producer', '?')}; "
                    f"scope={inspection.get('scope', '?')}",
                    f"      Bindings: source={inspection.get('source_binding', '?')}; "
                    f"policy={inspection.get('policy_binding', '?')}",
                    f"      Observation: result={inspection.get('result', 'unknown')}; "
                    f"completeness={inspection.get('completeness', 'unknown')}; "
                    f"freshness={inspection.get('freshness', 'unknown')}",
                    f"      Reason: {inspection.get('reason', '?')}",
                ))
                if inspection.get("recovery_action"):
                    lines.append(f"      Recover: {inspection['recovery_action']}")
                if evidence.get("authority") == "diagnostic_only":
                    lines.append("      Authority: diagnostic only (not an attestation)")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle explain")
    parser.add_argument("--last", type=int, default=1, help="Show last N decisions")
    parser.add_argument("--detailed", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    entries = get_recent_decisions(limit=args.last)
    if not entries:
        print("No Fettle decisions recorded yet.")
        print("Decisions are logged when hooks fire during Claude Code sessions.")
        return

    print(f"── Last {len(entries)} Fettle Decision(s) ──\n")
    for entry in reversed(entries):
        print(explain_entry(entry, detailed=args.detailed, json_output=args.json))
        print()


if __name__ == "__main__":
    main()
