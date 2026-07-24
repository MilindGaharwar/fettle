"""WP-X2 — Deployment Safety Gate.

PreToolUse(Bash) check that verifies safety preconditions before
deploy/release commands: tests ran, CHANGELOG updated, health
endpoint exists, no debug flags in production code.
"""

from __future__ import annotations

import os
import re
import subprocess


_DEPLOY_PATTERNS: list[re.Pattern] = [
    re.compile(r"kubectl\s+apply"),
    re.compile(r"terraform\s+apply"),
    re.compile(r"cdk\s+deploy"),
    re.compile(r"fly\s+deploy"),
    re.compile(r"docker\s+compose\s+up\s+-d"),
    re.compile(r"git\s+push\s+heroku"),
    re.compile(r"gcloud\s+(?:app\s+deploy|run\s+deploy)"),
    re.compile(r"aws\s+(?:ecs\s+update|lambda\s+update)"),
]

_HEALTH_PATTERNS = [
    r"/health",
    r"/healthz",
    r"/ready",
    r"health_check",
    r"healthcheck",
]

_DEBUG_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*DEBUG\s*=\s*True", re.MULTILINE),
    re.compile(r"^\s*console\.log\(", re.MULTILINE),
]


def _is_deploy_command(command: str) -> bool:
    return any(pat.search(command) for pat in _DEPLOY_PATTERNS)


def _check_tests_ran(session_id: str) -> bool:
    from fettle.config import state_dir
    edits_path = state_dir(session_id) / "edits.jsonl"
    if not edits_path.is_file():
        return False
    try:
        import json
        for line in edits_path.read_text().splitlines():
            if line.strip():
                entry = json.loads(line)
                if entry.get("tested"):
                    return True
    except (OSError, ValueError):
        pass
    return False


def _check_changelog_edited(session_id: str) -> bool:
    from fettle.config import state_dir
    edits_path = state_dir(session_id) / "edits.jsonl"
    if not edits_path.is_file():
        return False
    try:
        import json
        for line in edits_path.read_text().splitlines():
            if line.strip():
                entry = json.loads(line)
                fpath = str(entry.get("file", ""))
                if "changelog" in fpath.lower():
                    return True
    except (OSError, ValueError):
        pass
    return False


def _check_health_endpoint(cwd: str) -> bool:
    for pat in _HEALTH_PATTERNS:
        try:
            result = subprocess.run(
                ["grep", "-rl", pat, cwd,
                 "--include=*.py", "--include=*.ts", "--include=*.js",
                 "--include=*.go", "--include=*.yaml", "--include=*.yml"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip():
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return False


def _check_debug_flags(cwd: str) -> list[str]:
    findings: list[str] = []
    for dirpath, dirnames, filenames in os.walk(cwd):
        dirnames[:] = [d for d in dirnames if d not in (
            "__pycache__", ".venv", "node_modules", ".git", "dist", "build", "tests", "test",
        )]
        for fname in filenames:
            if not fname.endswith((".py", ".ts", ".js")):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    content = f.read(65536)
                for pat in _DEBUG_PATTERNS:
                    if pat.search(content):
                        rel = os.path.relpath(fpath, cwd)
                        findings.append(rel)
                        break
            except OSError:
                continue
    return findings[:5]


def run_check(ctx):
    """PreToolUse(Bash) — verify deploy safety preconditions."""
    from fettle.dispatcher_types import CheckResult

    cfg = ctx.config.get("gates", {}).get("deploy_safety", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    command = ctx.tool_input.get("command", "")
    if not _is_deploy_command(command):
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    session_id = ctx.session_id or "unknown"
    issues: list[str] = []

    if cfg.get("require_tests", True) and not _check_tests_ran(session_id):
        issues.append("No tests ran this session")

    if cfg.get("require_changelog", False) and not _check_changelog_edited(session_id):
        issues.append("CHANGELOG not updated this session")

    if cfg.get("require_health_endpoint", True) and not _check_health_endpoint(cwd):
        issues.append("No health endpoint found in source")

    if cfg.get("check_debug_flags", True):
        debug_files = _check_debug_flags(cwd)
        if debug_files:
            issues.append("Debug flags found: " + ", ".join(debug_files))

    if not issues:
        return CheckResult.allow()

    mode = cfg.get("mode", "advisory")
    msg = "Deploy safety:\n" + "\n".join("  - " + i for i in issues)

    if mode == "enforce":
        return CheckResult.block(msg, hook_specific_output={
            "hookEventName": ctx.input.hook_event_name,
            "additionalContext": msg,
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        })
    return CheckResult.advisory(msg, hook_specific_output={
        "hookEventName": ctx.input.hook_event_name,
        "additionalContext": msg,
    })
