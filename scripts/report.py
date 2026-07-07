#!/usr/bin/env python3
"""Fettle effectiveness report — metrics from trace data.

Analyzes Fettle's own trace.jsonl to report:
- Hook fire frequency
- Violation vs pass ratio
- Tool error rate
- Most common violations
- Rules that never fire (retire candidates)
- Rules always suppressed (recalibrate candidates)

Usage:
    python3 report.py [--json] [--days 30]
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace import get_recent_decisions


def compute_effectiveness(days: int = 30) -> dict:
    """Compute effectiveness metrics from trace data."""
    entries = get_recent_decisions(limit=10000)

    if not entries:
        return {"error": "No trace data. Run hooks first."}

    cutoff = time.time() - (days * 86400)
    recent = [e for e in entries if e.get("ts", 0) > cutoff]

    if not recent:
        return {"error": f"No trace data in the last {days} days."}

    total = len(recent)
    by_status = Counter(e.get("status", "unknown") for e in recent)
    by_hook = Counter(e.get("hook", "unknown") for e in recent)
    by_tool = Counter(e.get("tool", "unknown") for e in recent)

    violations = [e for e in recent if e.get("status") == "violation"]
    all_findings = []
    for v in violations:
        for f in v.get("findings", []):
            all_findings.append(f)

    by_code = Counter(f.get("code", "unknown") for f in all_findings)
    by_file = Counter(f.get("file", "unknown") for f in all_findings)

    tool_errors = [e for e in recent if e.get("status") == "tool_error"]

    pass_rate = by_status.get("pass", 0) / max(total, 1) * 100
    violation_rate = by_status.get("violation", 0) / max(total, 1) * 100
    error_rate = len(tool_errors) / max(total, 1) * 100

    return {
        "period_days": days,
        "total_decisions": total,
        "by_status": dict(by_status),
        "by_hook": dict(by_hook),
        "by_tool": dict(by_tool),
        "pass_rate_pct": round(pass_rate, 1),
        "violation_rate_pct": round(violation_rate, 1),
        "tool_error_rate_pct": round(error_rate, 1),
        "total_findings": len(all_findings),
        "top_violations": by_code.most_common(10),
        "most_affected_files": by_file.most_common(5),
        "tool_errors": [{"tool": e.get("tool"), "ts": e.get("timestamp")} for e in tool_errors[:5]],
    }


def identify_candidates(days: int = 30) -> dict:
    """Identify rules to retire or recalibrate."""
    entries = get_recent_decisions(limit=10000)
    cutoff = time.time() - (days * 86400)
    recent = [e for e in entries if e.get("ts", 0) > cutoff]

    violations = [e for e in recent if e.get("status") == "violation"]
    all_codes = set()
    fired_codes = set()

    for v in violations:
        for f in v.get("findings", []):
            code = f.get("code", "")
            if code:
                fired_codes.add(code)
                all_codes.add(code)

    # Rules that fired 0 times in the period = retire candidates
    # (We can only detect codes that fired; for never-fired we'd need the rule registry)

    # Rules that fire but are always in "suppressed" entries = recalibrate candidates
    suppressed_codes: Counter = Counter()
    for v in violations:
        for f in v.get("findings", []):
            if f.get("_suppressed"):
                suppressed_codes[f.get("code", "")] += 1

    always_suppressed = [code for code, count in suppressed_codes.items() if count > 3]

    return {
        "retire_candidates": [],
        "recalibrate_candidates": always_suppressed,
        "active_rules": list(fired_codes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle effectiveness report")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    report = compute_effectiveness(args.days)
    candidates = identify_candidates(args.days)

    if args.json:
        print(json.dumps({"effectiveness": report, "candidates": candidates}, indent=2))
        return

    if "error" in report:
        print(f"  {report['error']}")
        return

    print("── Fettle Effectiveness Report ──\n")
    print(f"  Period: last {args.days} days")
    print(f"  Total decisions: {report['total_decisions']}")
    print(f"  Pass rate: {report['pass_rate_pct']}%")
    print(f"  Violation rate: {report['violation_rate_pct']}%")
    print(f"  Tool error rate: {report['tool_error_rate_pct']}%")
    print(f"  Total findings: {report['total_findings']}")

    if report["top_violations"]:
        print(f"\n  Top violations:")
        for code, count in report["top_violations"][:5]:
            print(f"    • {code}: {count}×")

    if report["most_affected_files"]:
        print(f"\n  Most affected files:")
        for file, count in report["most_affected_files"][:3]:
            print(f"    • {file}: {count} finding(s)")

    if report["tool_errors"]:
        print(f"\n  Recent tool errors:")
        for err in report["tool_errors"][:3]:
            print(f"    • {err['tool']} at {err['ts']}")

    if candidates["recalibrate_candidates"]:
        print(f"\n  Recalibrate candidates (always suppressed):")
        for code in candidates["recalibrate_candidates"]:
            print(f"    • {code}")

    print()


if __name__ == "__main__":
    main()
