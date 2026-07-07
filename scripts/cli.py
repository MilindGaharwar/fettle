#!/usr/bin/env python3
"""Fettle CLI — quality enforcement from the command line.

Commands:
    fettle check [--all] [--changed] [--json] [--fix] [--baseline]
    fettle config [--print-effective]
    fettle explain [--last]
    fettle baseline create|update
    fettle doctor
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_check(args: argparse.Namespace) -> None:
    """Run quality checks (CI-friendly, no hook context needed)."""
    from config import load_config
    from paths import find_repo_root
    from quality_scan import scan_project

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(1)

    config = load_config(str(repo_root))
    results = scan_project(str(repo_root), config, json_output=args.json)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results.get("findings"):
            print("✓ No issues found.")
        else:
            for f in results["findings"]:
                sev = f.get("severity", "info").upper()
                loc = f"{f.get('file', '')}:{f.get('line', '')}" if f.get("file") else ""
                print(f"  [{sev}] {loc} {f.get('code', '')} — {f.get('message', '')}")
            print(f"\n{len(results['findings'])} finding(s).")
            sys.exit(1 if any(f.get("severity") == "error" for f in results["findings"]) else 0)


def cmd_config(args: argparse.Namespace) -> None:
    """Show effective configuration."""
    from config import load_config, DEFAULTS
    from paths import find_repo_root

    repo_root = find_repo_root()
    config = load_config(str(repo_root) if repo_root else None)

    if args.print_effective:
        print("── Effective Fettle Configuration ──\n")
        print(f"  Repo root: {repo_root or '(not found)'}")
        print(f"  Config file: {repo_root / '.fettle.toml' if repo_root and (repo_root / '.fettle.toml').exists() else '(defaults only)'}")
        print()
        print(json.dumps(config, indent=2, default=str))
    else:
        print("Use --print-effective to see merged config.")


def cmd_explain(args: argparse.Namespace) -> None:
    """Explain the last hook decision."""
    from config import load_config

    state_dir = os.environ.get(
        "XDG_STATE_HOME", os.path.expanduser("~/.local/state")
    )
    trace_dir = os.path.join(state_dir, "fettle")

    if not os.path.isdir(trace_dir):
        print("No Fettle state found. Run a hook first.")
        return

    trace_file = os.path.join(trace_dir, "trace.jsonl")
    if not os.path.isfile(trace_file):
        print("No trace file found.")
        return

    with open(trace_file) as f:
        lines = f.readlines()

    if not lines:
        print("Trace is empty.")
        return

    last_entries = []
    for line in reversed(lines[-20:]):
        try:
            entry = json.loads(line.strip())
            last_entries.append(entry)
        except json.JSONDecodeError:
            continue

    if not last_entries:
        print("No parseable trace entries.")
        return

    print("── Last Fettle Decision(s) ──\n")
    for entry in last_entries[:5]:
        hook = entry.get("hook", "?")
        status = entry.get("status", "?")
        tool = entry.get("tool", "?")
        file_path = entry.get("file", "")
        findings = entry.get("findings", [])
        ts = entry.get("timestamp", "")

        print(f"  [{ts}] {hook} → {status}")
        if file_path:
            print(f"    File: {file_path}")
        if tool:
            print(f"    Tool: {tool}")
        if findings:
            for f in findings[:3]:
                print(f"    • {f.get('code', '')} {f.get('message', '')}")
        print()


def cmd_baseline(args: argparse.Namespace) -> None:
    """Manage violation baselines."""
    from config import load_config
    from paths import find_repo_root

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository.", file=sys.stderr)
        sys.exit(1)

    baseline_path = repo_root / ".fettle-baseline.json"

    if args.action == "create":
        config = load_config(str(repo_root))
        from quality_scan import scan_project
        results = scan_project(str(repo_root), config, json_output=True)
        findings = results.get("findings", [])

        baseline = {
            "version": 1,
            "created": __import__("datetime").datetime.now().isoformat(),
            "findings_count": len(findings),
            "findings": findings,
        }
        baseline_path.write_text(json.dumps(baseline, indent=2))
        print(f"✓ Baseline created: {len(findings)} finding(s) at {baseline_path}")

    elif args.action == "update":
        if not baseline_path.exists():
            print("No baseline found. Run `fettle baseline create` first.")
            sys.exit(1)
        config = load_config(str(repo_root))
        from quality_scan import scan_project
        results = scan_project(str(repo_root), config, json_output=True)
        findings = results.get("findings", [])

        baseline = {
            "version": 1,
            "updated": __import__("datetime").datetime.now().isoformat(),
            "findings_count": len(findings),
            "findings": findings,
        }
        baseline_path.write_text(json.dumps(baseline, indent=2))
        print(f"✓ Baseline updated: {len(findings)} finding(s)")


def cmd_doctor(args: argparse.Namespace) -> None:
    """Run environment self-check."""
    import subprocess
    script_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.run([sys.executable, os.path.join(script_dir, "doctor.py")], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(prog="fettle", description="Quality enforcement CLI")
    subparsers = parser.add_subparsers(dest="command")

    p_check = subparsers.add_parser("check", help="Run quality checks")
    p_check.add_argument("--all", action="store_true", help="Check all files")
    p_check.add_argument("--changed", action="store_true", help="Check only changed files")
    p_check.add_argument("--json", action="store_true", help="JSON output")
    p_check.add_argument("--fix", action="store_true", help="Apply safe autofixes")
    p_check.add_argument("--baseline", action="store_true", help="Only report new violations")

    p_config = subparsers.add_parser("config", help="Show configuration")
    p_config.add_argument("--print-effective", action="store_true", help="Show merged effective config")

    p_explain = subparsers.add_parser("explain", help="Explain last hook decision")
    p_explain.add_argument("--last", action="store_true", default=True)

    p_baseline = subparsers.add_parser("baseline", help="Manage violation baselines")
    p_baseline.add_argument("action", choices=["create", "update"], help="Baseline action")

    subparsers.add_parser("doctor", help="Environment self-check")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "check": cmd_check,
        "config": cmd_config,
        "explain": cmd_explain,
        "baseline": cmd_baseline,
        "doctor": cmd_doctor,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
