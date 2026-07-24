#!/usr/bin/env python3
"""WP-121 — Loaded-rules health telemetry.

Every hook run logs rules loaded/skipped per config source into trace;
`doctor` asserts expected counts; a drop to zero in any pack raises a
blocking config error.

Usage (standalone debugging):
    scripts/run.sh health_telemetry.py [--pack llm-antipatterns] [--history] [--doctor]
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = PLUGIN_ROOT / "rules"

_EVENT_TYPE = "rules_loaded"


# ──────────────────────────────────────────────────────────────────────
# Trace I/O (same file as trace.py: $XDG_STATE_HOME/fettle/trace.jsonl)
# ──────────────────────────────────────────────────────────────────────


def _get_trace_path() -> str:
    state_dir = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    trace_dir = os.path.join(state_dir, "fettle")
    os.makedirs(trace_dir, exist_ok=True)
    return os.path.join(trace_dir, "trace.jsonl")


# ──────────────────────────────────────────────────────────────────────
# 1. record_loaded_rules — write a health trace entry
# ──────────────────────────────────────────────────────────────────────


def record_loaded_rules(
    pack_name: str,
    rules_loaded: int,
    rules_skipped: int,
    config_source: str,
) -> None:
    """Append a rules-loaded health entry to the global trace."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ts": time.time(),
        "hook": "health_telemetry",
        "event": _EVENT_TYPE,
        "pack": pack_name,
        "rules_loaded": rules_loaded,
        "rules_skipped": rules_skipped,
        "config_source": config_source,
        "session_id": os.environ.get("FETTLE_SESSION_ID", ""),
    }
    try:
        trace_path = _get_trace_path()
        with open(trace_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
    except OSError:
        pass


# ──────────────────────────────────────────────────────────────────────
# Internal: read health entries from the trace
# ──────────────────────────────────────────────────────────────────────


def _read_health_entries() -> list[dict[str, Any]]:
    """Return all health_telemetry entries from the trace file."""
    trace_path = _get_trace_path()
    if not os.path.isfile(trace_path):
        return []
    entries: list[dict[str, Any]] = []
    with open(trace_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("hook") == "health_telemetry" and obj.get("event") == _EVENT_TYPE:
                entries.append(obj)
    return entries


# ──────────────────────────────────────────────────────────────────────
# 2. check_health — detect zero-rule packs and missing packs
# ──────────────────────────────────────────────────────────────────────


def check_health(expected_packs: list[str]) -> list[dict[str, str]]:
    """Check health of loaded rules against expectations.

    Returns a list of issues:
      - ERROR if a pack has zero rules loaded in the most recent run
      - ERROR if a pack's loaded count dropped to zero vs. prior runs
      - WARNING if a pack was expected but never seen in trace
    """
    entries = _read_health_entries()
    issues: list[dict[str, str]] = []

    # Group entries by pack, preserving order (most recent last)
    by_pack: dict[str, list[dict]] = {}
    for e in entries:
        by_pack.setdefault(e["pack"], []).append(e)

    for pack in expected_packs:
        pack_entries = by_pack.get(pack, [])

        if not pack_entries:
            issues.append({
                "level": "warning",
                "pack": pack,
                "message": f"pack '{pack}' expected but never seen in trace",
            })
            continue

        latest = pack_entries[-1]

        # Zero rules loaded in latest run
        if latest["rules_loaded"] == 0:
            issues.append({
                "level": "error",
                "pack": pack,
                "message": (
                    f"pack '{pack}' loaded 0 rules in most recent run "
                    f"(source: {latest.get('config_source', '?')})"
                ),
            })
            continue

        # Dropped to zero compared to any previous non-zero run
        if len(pack_entries) >= 2:
            previous_non_zero = [e for e in pack_entries[:-1] if e["rules_loaded"] > 0]
            if previous_non_zero and latest["rules_loaded"] == 0:
                # Already caught above, but kept for clarity
                issues.append({
                    "level": "error",
                    "pack": pack,
                    "message": (
                        f"pack '{pack}' dropped to 0 rules "
                        f"(was {previous_non_zero[-1]['rules_loaded']})"
                    ),
                })

    return issues


# ──────────────────────────────────────────────────────────────────────
# 3. get_pack_history — last N records for a pack
# ──────────────────────────────────────────────────────────────────────


def get_pack_history(pack_name: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return the last `limit` load records for a given pack."""
    entries = _read_health_entries()
    pack_entries = [e for e in entries if e["pack"] == pack_name]
    return pack_entries[-limit:]


# ──────────────────────────────────────────────────────────────────────
# 4. doctor_check — integration with `fettle doctor`
# ──────────────────────────────────────────────────────────────────────


def _discover_expected_packs() -> list[str]:
    """Discover pack names from rules/*.yml in the plugin root."""
    packs: list[str] = []
    if RULES_DIR.is_dir():
        for f in sorted(RULES_DIR.glob("*.yml")):
            packs.append(f.stem)
    return packs


def doctor_check() -> tuple[bool, list[str]]:
    """Run health telemetry check for the doctor command.

    Returns:
        (passed, messages) where passed is False if any ERROR-level issues found.
    """
    expected = _discover_expected_packs()
    if not expected:
        return True, ["no rule packs found in rules/ — nothing to check"]

    issues = check_health(expected)
    messages: list[str] = []
    has_error = False

    for issue in issues:
        prefix = "ERROR" if issue["level"] == "error" else "WARN "
        messages.append(f"[{prefix}] {issue['pack']}: {issue['message']}")
        if issue["level"] == "error":
            has_error = True

    if not messages:
        messages.append(f"all {len(expected)} rule packs healthy")

    return not has_error, messages


# ──────────────────────────────────────────────────────────────────────
# Standalone CLI for debugging
# ──────────────────────────────────────────────────────────────────────


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fettle rules-loaded health telemetry")
    parser.add_argument("--pack", help="Show history for a specific pack")
    parser.add_argument("--history", action="store_true", help="Show pack history (use with --pack)")
    parser.add_argument("--doctor", action="store_true", help="Run doctor check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.history and args.pack:
        history = get_pack_history(args.pack)
        if args.json:
            print(json.dumps(history, indent=2))
        else:
            for entry in history:
                print(
                    f"  {entry['timestamp']}  loaded={entry['rules_loaded']}  "
                    f"skipped={entry['rules_skipped']}  source={entry['config_source']}"
                )
        return 0

    if args.doctor:
        passed, messages = doctor_check()
        if args.json:
            print(json.dumps({"passed": passed, "messages": messages}, indent=2))
        else:
            for msg in messages:
                print(msg)
            print()
            print("PASS" if passed else "FAIL")
        return 0 if passed else 1

    # Default: show all health entries
    entries = _read_health_entries()
    if args.json:
        print(json.dumps(entries, indent=2))
    else:
        if not entries:
            print("no health telemetry entries found")
        else:
            for e in entries[-20:]:
                print(
                    f"  {e['timestamp']}  {e['pack']:<20}  "
                    f"loaded={e['rules_loaded']}  skipped={e['rules_skipped']}  "
                    f"source={e['config_source']}"
                )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
