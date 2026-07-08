"""Fettle false-positive stamps — mark findings as FP in trace.

Usage:
    python3 fp_stamp.py --rule BLE001 --file app.py --line 42 --reason "Intentional catch-all"
    python3 fp_stamp.py --list
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace import log_decision


def _get_fp_path() -> str:
    state_dir = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    fp_dir = os.path.join(state_dir, "fettle")
    os.makedirs(fp_dir, exist_ok=True)
    return os.path.join(fp_dir, "false-positives.jsonl")


def stamp_fp(rule: str, file: str, line: int, reason: str) -> None:
    """Record a false-positive stamp."""
    entry = {
        "ts": time.time(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rule": rule,
        "file": file,
        "line": line,
        "reason": reason,
        "fp": True,
    }
    fp_path = _get_fp_path()
    with open(fp_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    log_decision(
        hook="fp_stamp",
        status="stamped",
        tool="manual",
        file=file,
        findings=[{"code": rule, "message": reason, "line": line, "fp": True}],
    )


def load_fp_stamps() -> list[dict]:
    """Load all false-positive stamps."""
    fp_path = _get_fp_path()
    if not os.path.isfile(fp_path):
        return []
    stamps = []
    with open(fp_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    stamps.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return stamps


def is_fp_stamped(rule: str, file: str, line: int) -> bool:
    """Check if a specific finding is stamped as FP."""
    for stamp in load_fp_stamps():
        if stamp.get("rule") == rule and stamp.get("file") == file and stamp.get("line") == line:
            return True
    return False


def fp_rate(findings_count: int) -> float:
    """Calculate FP rate: stamped FPs / total findings."""
    stamps = load_fp_stamps()
    if findings_count == 0:
        return 0.0
    return len(stamps) / max(findings_count, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle false-positive stamp")
    parser.add_argument("--rule", help="Rule code (e.g. BLE001)")
    parser.add_argument("--file", help="File path")
    parser.add_argument("--line", type=int, help="Line number")
    parser.add_argument("--reason", help="Why this is a false positive")
    parser.add_argument("--list", action="store_true", help="List all FP stamps")
    args = parser.parse_args()

    if args.list:
        stamps = load_fp_stamps()
        if not stamps:
            print("No false-positive stamps recorded.")
            return
        print(f"── {len(stamps)} False-Positive Stamp(s) ──\n")
        for s in stamps:
            print(f"  [{s.get('timestamp', '?')}] {s.get('rule', '?')} in {s.get('file', '?')}:{s.get('line', '?')}")
            print(f"    Reason: {s.get('reason', '?')}")
        return

    if not (args.rule and args.file and args.reason):
        print("Usage: fp_stamp.py --rule RULE --file FILE --line N --reason 'why'")
        sys.exit(1)

    stamp_fp(args.rule, args.file, args.line or 0, args.reason)
    print(f"✓ Stamped as false positive: {args.rule} in {args.file}:{args.line}")


if __name__ == "__main__":
    main()
