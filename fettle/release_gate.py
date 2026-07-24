"""WP-X3 — CHANGELOG and Semver Enforcement.

PreToolUse(Bash) check that validates git tag commands:
- Semver format required
- CHANGELOG.md must have matching entry
- Breaking changes noted if MAJOR bump missing
"""

from __future__ import annotations

import os
import re
import subprocess


_TAG_RE = re.compile(r"git\s+tag\s+(?:-[asm]\s+)?v?(\d+\.\d+\.\d+(?:-[\w.]+)?)")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[\w.]+)?$")


def _extract_version(command: str) -> str | None:
    m = _TAG_RE.search(command)
    return m.group(1) if m else None


def _changelog_has_version(cwd: str, version: str, changelog_path: str) -> bool:
    path = os.path.join(cwd, changelog_path)
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        return version in content or ("v" + version) in content
    except OSError:
        return False


def _has_breaking_commits(cwd: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "log", "--oneline", "--format=%B",
             "HEAD...$(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~10)"],
            capture_output=True, text=True, timeout=5, shell=False,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["git", "-C", cwd, "log", "--oneline", "-20", "--format=%s%n%b"],
                capture_output=True, text=True, timeout=5,
            )
        return "BREAKING CHANGE" in result.stdout or "!:" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def run_check(ctx):
    """PreToolUse(Bash) — validate git tag commands."""
    from fettle.dispatcher_types import CheckResult

    cfg = ctx.config.get("gates", {}).get("release", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    command = ctx.tool_input.get("command", "")
    version = _extract_version(command)
    if not version:
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    findings: list[str] = []

    if cfg.get("require_semver", True) and not _SEMVER_RE.match(version):
        findings.append("Version '" + version + "' is not valid semver (expected MAJOR.MINOR.PATCH)")

    changelog_path = cfg.get("changelog_path", "CHANGELOG.md")
    if not _changelog_has_version(cwd, version, changelog_path):
        if os.path.isfile(os.path.join(cwd, changelog_path)):
            findings.append(changelog_path + " has no entry for version " + version)
        else:
            findings.append("No " + changelog_path + " found")

    if cfg.get("check_breaking_changes", True) and _has_breaking_commits(cwd):
        parts = version.split(".")
        if len(parts) >= 1 and parts[0] == "0":
            pass
        elif len(parts) >= 1:
            findings.append("BREAKING CHANGE detected in commits but version may not reflect a MAJOR bump")

    if not findings:
        return CheckResult.allow()

    mode = cfg.get("mode", "advisory")
    msg = "Release gate:\n" + "\n".join("  - " + f for f in findings)

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
