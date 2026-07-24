"""WP-X4 — Mutation Testing Command.

Wraps mutmut to run mutation testing on changed Python files.
Reports surviving mutants and mutation score.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def _get_changed_py_files(root: str, paths: list[str]) -> list[str]:
    """Get changed .py files from git diff, filtered to configured paths."""
    try:
        result = subprocess.run(
            ["git", "-C", root, "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["git", "-C", root, "diff", "--name-only", "--cached"],
                capture_output=True, text=True, timeout=5,
            )
        files = [f for f in result.stdout.strip().splitlines() if f.endswith(".py")]
        if paths:
            files = [f for f in files if any(f.startswith(p) for p in paths)]
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _has_mutmut() -> bool:
    import shutil
    if shutil.which("mutmut"):
        return True
    local = os.path.expanduser("~/.local/bin/mutmut")
    return os.path.isfile(local) and os.access(local, os.X_OK)


def _run_mutmut(root: str, paths_to_mutate: list[str], timeout_s: int) -> dict:
    """Run mutmut and parse results."""
    if not paths_to_mutate:
        return {"status": "nothing_to_mutate", "survivors": [], "killed": 0, "survived": 0}

    paths_arg = ",".join(paths_to_mutate)
    try:
        subprocess.run(
            ["mutmut", "run", "--paths-to-mutate=" + paths_arg, "--no-progress"],
            capture_output=True, text=True, timeout=timeout_s,
            cwd=root, env=_ENV,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "survivors": [], "killed": 0, "survived": 0}
    except FileNotFoundError:
        return {"status": "tool_missing", "survivors": [], "killed": 0, "survived": 0}

    # Parse results from mutmut results
    try:
        results_proc = subprocess.run(
            ["mutmut", "results"],
            capture_output=True, text=True, timeout=30,
            cwd=root, env=_ENV,
        )
        return _parse_results(results_proc.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"status": "parse_error", "survivors": [], "killed": 0, "survived": 0}


def _parse_results(output: str) -> dict:
    """Parse mutmut results output."""
    survivors: list[str] = []
    killed = 0
    survived = 0

    in_survived = False
    for line in output.splitlines():
        line = line.strip()
        if "Survived" in line or "survived" in line:
            in_survived = True
            continue
        if "Killed" in line or "killed" in line:
            in_survived = False
            continue
        if in_survived and line.startswith("- "):
            survivors.append(line[2:])
            survived += 1
        elif line.startswith("- ") and not in_survived:
            killed += 1

    # Fallback: count from summary line if present
    import re
    m = re.search(r"(\d+)\s+killed", output)
    if m:
        killed = int(m.group(1))
    m = re.search(r"(\d+)\s+survived", output)
    if m:
        survived = int(m.group(1))

    return {"status": "completed", "survivors": survivors[:20], "killed": killed, "survived": survived}


def compute_score(killed: int, survived: int) -> float:
    total = killed + survived
    if total == 0:
        return 100.0
    return (killed / total) * 100


def run_mutation_test(root: str, cfg: dict) -> dict:
    """Run mutation testing and return report."""
    if not _has_mutmut():
        return {
            "status": "tool_missing",
            "message": "mutmut not found. Install: pip install mutmut",
            "score": None,
        }

    paths = cfg.get("paths", ["src/"])
    exclude = cfg.get("exclude", ["tests/", "migrations/"])
    timeout_s = int(cfg.get("timeout_s", 300))
    threshold = float(cfg.get("threshold", 70))

    changed_files = _get_changed_py_files(root, paths)
    changed_files = [f for f in changed_files if not any(f.startswith(e) for e in exclude)]

    if not changed_files:
        return {
            "status": "nothing_to_mutate",
            "message": "No implementation files changed",
            "score": None,
        }

    results = _run_mutmut(root, changed_files, timeout_s)

    if results["status"] in ("timeout", "tool_missing", "parse_error"):
        return {
            "status": results["status"],
            "message": "Mutation testing " + results["status"],
            "score": None,
        }

    score = compute_score(results["killed"], results["survived"])
    passed = score >= threshold

    return {
        "status": "completed",
        "score": round(score, 1),
        "killed": results["killed"],
        "survived": results["survived"],
        "survivors": results["survivors"],
        "threshold": threshold,
        "passed": passed,
        "files_tested": changed_files,
    }


def format_report(report: dict) -> str:
    """Format mutation test report."""
    lines = ["# Mutation Test Report", ""]

    if report["status"] == "tool_missing":
        return lines[0] + "\n\n" + report["message"]
    if report["status"] == "nothing_to_mutate":
        return lines[0] + "\n\n" + report["message"]

    lines.append("**Score:** " + str(report.get("score", "N/A")) + "%"
                 + (" PASS" if report.get("passed") else " FAIL"))
    lines.append("**Killed:** " + str(report.get("killed", 0)))
    lines.append("**Survived:** " + str(report.get("survived", 0)))
    lines.append("**Threshold:** " + str(report.get("threshold", 70)) + "%")
    lines.append("")

    survivors = report.get("survivors", [])
    if survivors:
        lines.append("## Surviving Mutants")
        for s in survivors[:10]:
            lines.append("- " + s)
    lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fettle mutation testing")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--paths", default="src/", help="Comma-separated paths to mutate")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    parser.add_argument("--threshold", type=float, default=70, help="Minimum score")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = {
        "paths": args.paths.split(","),
        "timeout_s": args.timeout,
        "threshold": args.threshold,
    }

    report = run_mutation_test(args.root, cfg)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))

    return 0 if report.get("passed", True) else 1


if __name__ == "__main__":
    sys.exit(main())
