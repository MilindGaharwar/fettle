#!/usr/bin/env python3
"""Fettle effectiveness report — EXPERIMENTAL.

Analyzes LogAct session data and Fettle trace files to measure enforcement
effectiveness.  This is a measurement/diagnostic tool, not production code.

Usage:
    python3 effectiveness_report.py [--logact-dir DIR] [--trace-file FILE] [--baseline FILE] [--json]
"""

import argparse
import json
import os
import sqlite3
import statistics
import sys
from pathlib import Path

DEFAULT_LOGACT_DIR = os.path.expanduser("~/.claude/logact")
DEFAULT_TRACE_FILE = ".fettle/trace.jsonl"


# ---------------------------------------------------------------------------
# LogAct analysis
# ---------------------------------------------------------------------------

def _analyze_logact(logact_dir: str) -> dict:
    buses_dir = os.path.join(logact_dir, "buses")
    if not os.path.isdir(buses_dir):
        return {"sessions": 0, "error": f"buses dir not found: {buses_dir}"}

    db_files = list(Path(buses_dir).glob("*.db"))
    total_by_type: dict[str, int] = {}
    tool_breakdown: dict[str, int] = {}
    abort_reasons: dict[str, int] = {}
    sessions = 0

    for db_path in db_files:
        sessions += 1
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.execute("PRAGMA query_only = ON")

            # Payload type counts
            try:
                for row in conn.execute(
                    "SELECT payload_type, COUNT(*) FROM entries GROUP BY payload_type"
                ):
                    total_by_type[row[0]] = total_by_type.get(row[0], 0) + row[1]
            except sqlite3.OperationalError:
                pass

            # Tool name breakdown from intents
            try:
                for row in conn.execute(
                    "SELECT json_extract(payload, '$.tool_name'), COUNT(*) "
                    "FROM entries WHERE payload_type = 'intent' "
                    "GROUP BY json_extract(payload, '$.tool_name')"
                ):
                    if row[0]:
                        tool_breakdown[row[0]] = tool_breakdown.get(row[0], 0) + row[1]
            except sqlite3.OperationalError:
                pass

            # Abort reasons
            try:
                for row in conn.execute(
                    "SELECT json_extract(payload, '$.reason'), COUNT(*) "
                    "FROM entries WHERE payload_type = 'abort' "
                    "GROUP BY json_extract(payload, '$.reason')"
                ):
                    if row[0]:
                        abort_reasons[row[0]] = abort_reasons.get(row[0], 0) + row[1]
            except sqlite3.OperationalError:
                pass

            conn.close()
        except (sqlite3.Error, OSError) as exc:
            print(f"WARNING: could not read {db_path}: {exc}", file=sys.stderr)

    total_calls = sum(total_by_type.values())
    safety_blocks = sum(abort_reasons.values())

    return {
        "sessions": sessions,
        "total_calls": total_calls,
        "by_type": total_by_type,
        "tool_breakdown": tool_breakdown,
        "safety_blocks": safety_blocks,
        "block_rate": round(safety_blocks / total_calls * 100, 2) if total_calls else 0.0,
        "abort_reasons": abort_reasons,
    }


# ---------------------------------------------------------------------------
# Fettle trace analysis
# ---------------------------------------------------------------------------

def _analyze_trace(trace_file: str) -> dict:
    if not os.path.isfile(trace_file):
        return {"found": False}

    findings: list[dict] = []
    metrics: list[dict] = []
    dedup_suppressed = 0

    with open(trace_file) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = entry.get("type", "")
            if etype == "finding":
                findings.append(entry)
            elif etype == "metric":
                metrics.append(entry)
            if entry.get("dedup_suppressed"):
                dedup_suppressed += 1

    by_severity = {"ERROR": 0, "WARNING": 0, "INFO": 0}
    for f in findings:
        sev = f.get("severity", "INFO")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    hook_durations = [m.get("hook_duration_ms", 0) for m in metrics if "hook_duration_ms" in m]
    ruff_durations = [m.get("ruff_duration_ms", 0) for m in metrics if "ruff_duration_ms" in m]
    semgrep_skips = sum(1 for m in metrics if m.get("semgrep_skipped"))
    semgrep_total = sum(1 for m in metrics if "semgrep_skipped" in m)

    return {
        "found": True,
        "total_findings": len(findings),
        "by_severity": by_severity,
        "dedup_suppressed": dedup_suppressed,
        "dedup_rate": round(dedup_suppressed / max(len(findings) + dedup_suppressed, 1) * 100, 2),
        "hook_durations": hook_durations,
        "avg_hook_ms": round(statistics.mean(hook_durations), 1) if hook_durations else 0,
        "max_hook_ms": max(hook_durations) if hook_durations else 0,
        "p95_hook_ms": round(sorted(hook_durations)[int(len(hook_durations) * 0.95)] if hook_durations else 0, 1),
        "avg_ruff_ms": round(statistics.mean(ruff_durations), 1) if ruff_durations else 0,
        "semgrep_skip_rate": round(semgrep_skips / max(semgrep_total, 1) * 100, 2),
        "escalations": sum(1 for f in findings if f.get("repeat_count", 0) >= 3),
    }


# ---------------------------------------------------------------------------
# Counterfactual
# ---------------------------------------------------------------------------

def _counterfactual(baseline_path: str) -> dict:
    if not os.path.isfile(baseline_path):
        return {"available": False}

    with open(baseline_path) as fh:
        data = json.load(fh)

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("findings", data.get("entries", []))
    else:
        return {"available": False}

    py_files = set()
    files_with_issues = set()
    for item in items:
        f = item.get("file", "")
        if f.endswith(".py"):
            py_files.add(f)
            if item.get("severity") in ("ERROR", "WARNING"):
                files_with_issues.add(f)

    total = len(py_files) or 1
    return {
        "available": True,
        "historical_py_files": len(py_files),
        "files_with_issues": len(files_with_issues),
        "incremental_coverage": round(len(files_with_issues) / total * 100, 1),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _print_human(logact: dict, fettle: dict, counterfactual: dict, combined_actions: int) -> None:
    print("=== LogAct Effectiveness ===")
    print(f"Sessions analyzed: {logact.get('sessions', 0)}")
    print(f"Total tool calls: {logact.get('total_calls', 0)}", end="")
    tb = logact.get("tool_breakdown", {})
    if tb:
        parts = [f"{k}: {v}" for k, v in sorted(tb.items(), key=lambda x: -x[1])]
        print(f" ({', '.join(parts)})")
    else:
        print()
    print(f"Safety blocks: {logact.get('safety_blocks', 0)} (rate: {logact.get('block_rate', 0)}%)")
    reasons = logact.get("abort_reasons", {})
    if reasons:
        print("Block reasons:")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"  - {reason}: {count} times")
    print()

    print("=== Fettle Effectiveness ===")
    if not fettle.get("found"):
        print("No trace file found — run Fettle hooks to generate trace data.")
    else:
        sev = fettle.get("by_severity", {})
        total_edits = max(len(fettle.get("hook_durations", [])), 1)
        print(f"Files checked: {total_edits}")
        print(f"Findings: {sev.get('ERROR', 0)} errors, {sev.get('WARNING', 0)} warnings, {sev.get('INFO', 0)} info")
        print(f"Findings per edit: {fettle['total_findings'] / total_edits:.2f}")
        print(f"Dedup suppressed: {fettle['dedup_suppressed']} (rate: {fettle['dedup_rate']}%)")
        print(f"Escalations (3+ repeats): {fettle.get('escalations', 0)}")
    print()

    print("=== Combined Enforcement ===")
    block_rate = logact.get("block_rate", 0)
    fettle_rate = 0.0
    if fettle.get("found"):
        total_edits = max(len(fettle.get("hook_durations", [])), 1)
        fettle_rate = round(fettle["total_findings"] / total_edits * 100, 1)
    print(f"Layer 1 (LogAct safety): {block_rate}% of dangerous ops blocked")
    print(f"Layer 2 (Fettle quality): {fettle_rate}% of edits had quality findings")
    print(f"Combined enforcement actions: {combined_actions}")
    print()

    print("=== Latency Impact ===")
    if fettle.get("found") and fettle.get("avg_hook_ms"):
        print(f"Avg hook duration: {fettle['avg_hook_ms']}ms (ruff: {fettle['avg_ruff_ms']}ms)")
        print(f"Semgrep skip rate: {fettle['semgrep_skip_rate']}% (lazy loading)")
        print(f"Max hook duration: {fettle['max_hook_ms']}ms")
        print(f"P95 hook duration: {fettle['p95_hook_ms']}ms")
    else:
        print("No latency data available.")
    print()

    print("=== Counterfactual ===")
    if not counterfactual.get("available"):
        print("No baseline provided — cannot compute counterfactual.")
    else:
        print(f"Historical .py files written/edited: {counterfactual['historical_py_files']}")
        print(f"Files with current quality issues: {counterfactual['files_with_issues']}")
        print(f"Incremental coverage: +{counterfactual['incremental_coverage']}%")


def _print_json(logact: dict, fettle: dict, counterfactual: dict, combined_actions: int) -> None:
    print(json.dumps({
        "logact": logact,
        "fettle": fettle,
        "counterfactual": counterfactual,
        "combined_actions": combined_actions,
    }, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Fettle effectiveness report (experimental)")
    parser.add_argument("--logact-dir", default=DEFAULT_LOGACT_DIR, help="LogAct data directory")
    parser.add_argument("--trace-file", default=DEFAULT_TRACE_FILE, help="Fettle trace JSONL file")
    parser.add_argument("--baseline", default=None, help="Phase 0 baseline for counterfactual")
    parser.add_argument("--json", action="store_true", dest="json_output", help="JSON output")
    args = parser.parse_args()

    logact = _analyze_logact(args.logact_dir)
    fettle = _analyze_trace(args.trace_file)
    counterfactual = _counterfactual(args.baseline) if args.baseline else {"available": False}

    combined_actions = logact.get("safety_blocks", 0) + fettle.get("total_findings", 0)

    if args.json_output:
        _print_json(logact, fettle, counterfactual, combined_actions)
    else:
        _print_human(logact, fettle, counterfactual, combined_actions)

    return 0


if __name__ == "__main__":
    sys.exit(main())
