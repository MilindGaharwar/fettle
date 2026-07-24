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


def _which(name: str) -> str | None:
    """Find a tool on PATH, including ~/.local/bin (uv tool install location)."""
    import os
    path = shutil.which(name)
    if path:
        return path
    local_bin = os.path.expanduser(f"~/.local/bin/{name}")
    if os.path.isfile(local_bin) and os.access(local_bin, os.X_OK):
        return local_bin
    return None


def check_environment() -> list[dict]:
    checks: list[dict] = []

    py_ok = sys.version_info >= (3, 11)
    checks.append({
        "name": "python",
        "required": True,
        "ok": py_ok,
        "detail": f"{sys.version.split()[0]} at {sys.executable}"
                  + ("" if py_ok else " — need >= 3.11 (set FETTLE_PYTHON)"),
    })

    tools = [
        ("ruff", True, "lint layer disabled without it"),
        ("semgrep", False, "LLM-antipattern layer skipped without it"),
        ("cargo", False, "Rust checks skipped without it"),
        ("shellcheck", False, "shell checks skipped without it"),
        ("claude", False, "cross-review/learn providers unavailable without it (v0.4.0)"),
    ]
    for name, required, consequence in tools:
        path = _which(name)
        version = _version_of(path) if path else None
        checks.append({
            "name": name,
            "required": required,
            "ok": bool(path),
            "detail": f"{version} at {path}" if path else f"not on PATH — {consequence}",
        })

    return checks


def check_commit_guards() -> list[dict]:
    """Warn when the repo declares pre-commit hooks but they aren't wired (WP-141).

    A .pre-commit-config.yaml without `pre-commit install` means commit-time
    guards silently don't run — the exact gap behind the 2026-07-24 CI scrub
    failure. Non-required: repos without pre-commit config are untouched.
    """
    import os
    checks: list[dict] = []
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from fettle.paths import find_repo_root
        repo_root = find_repo_root()
    except Exception:  # noqa: BLE001 — doctor must never crash
        return checks
    if not repo_root or not (repo_root / ".pre-commit-config.yaml").is_file():
        return checks
    hook = repo_root / ".git" / "hooks" / "pre-commit"
    try:
        wired = hook.is_file() and "pre-commit" in hook.read_text()
    except OSError:
        wired = False
    checks.append({
        "name": "commit-guards",
        "required": False,
        "ok": wired,
        "detail": "pre-commit hooks wired" if wired
                  else "repo has .pre-commit-config.yaml but hooks not installed — run: pre-commit install",
    })
    return checks


def check_org_policy() -> list[dict]:
    """Warn when [extends] is configured but the org policy isn't cached (WP-144).

    Hooks resolve org policy cache-only (no network in the hook path), so a
    configured-but-unsynced policy silently doesn't apply until someone runs
    `fettle policy sync` — exactly the kind of gap doctor exists to surface.
    """
    import os
    import tomllib
    checks: list[dict] = []
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fettle.paths import find_repo_root
    from fettle.policy_remote import PolicyError, load_cached, parse_extends
    try:
        repo_root = find_repo_root()
        if not repo_root or not (repo_root / ".fettle.toml").is_file():
            return checks
        with open(repo_root / ".fettle.toml", "rb") as fh:
            raw_cfg = tomllib.load(fh)
        extends = parse_extends(raw_cfg)
        if extends is None:
            return checks
        cached = load_cached(extends) is not None
        checks.append({
            "name": "org-policy",
            "required": False,
            "ok": cached,
            "detail": "org policy cached (digest verified)" if cached
                      else "[extends] configured but policy not cached — run: fettle policy sync",
        })
    except (PolicyError, OSError, ValueError) as exc:  # ValueError covers TOMLDecodeError
        checks.append({
            "name": "org-policy", "required": False, "ok": False,
            "detail": f"[extends] invalid: {exc}",
        })
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Fettle environment self-check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    checks = check_environment() + check_commit_guards() + check_org_policy()
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
