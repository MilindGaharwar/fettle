#!/usr/bin/env python3
"""Fettle doctor — environment self-check.

Verifies the interpreter and every external tool Fettle's gates rely on, so a
misconfigured environment is diagnosed in one command instead of silently
degrading gate coverage.

Usage:
    scripts/run.sh doctor.py [--json]
"""

import argparse
import json
import shutil
import subprocess
import sys


def _version_of(binary: str, args: list[str] | None = None) -> str | None:
    try:
        out = subprocess.run(
            [binary] + (args or ["--version"]),
            capture_output=True,
            text=True,
            timeout=15,
        )
        first = (out.stdout or out.stderr).strip().splitlines()
        return first[0] if first else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def check_environment() -> list[dict]:
    checks: list[dict] = []

    py_ok = sys.version_info >= (3, 10)
    checks.append({
        "name": "python",
        "required": True,
        "ok": py_ok,
        "detail": f"{sys.version.split()[0]} at {sys.executable}"
                  + ("" if py_ok else " — need >= 3.10 (set FETTLE_PYTHON)"),
    })

    tools = [
        ("ruff", True, "lint layer disabled without it"),
        ("semgrep", False, "LLM-antipattern layer skipped without it"),
        ("cargo", False, "Rust checks skipped without it"),
        ("shellcheck", False, "shell checks skipped without it"),
        ("claude", False, "cross-review/learn providers unavailable without it (v0.4.0)"),
    ]
    for name, required, consequence in tools:
        path = shutil.which(name)
        version = _version_of(path) if path else None
        checks.append({
            "name": name,
            "required": required,
            "ok": bool(path),
            "detail": f"{version} at {path}" if path else f"not on PATH — {consequence}",
        })

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Fettle environment self-check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    checks = check_environment()
    required_failures = [c for c in checks if c["required"] and not c["ok"]]

    if args.json:
        print(json.dumps({"checks": checks, "healthy": not required_failures}, indent=2))
    else:
        for c in checks:
            mark = "ok " if c["ok"] else ("FAIL" if c["required"] else "warn")
            print(f"[{mark}] {c['name']:<10} {c['detail']}")
        print()
        print("healthy" if not required_failures else "UNHEALTHY — required tools missing")

    return 1 if required_failures else 0


if __name__ == "__main__":
    sys.exit(main())
