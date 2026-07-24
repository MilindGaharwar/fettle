#!/usr/bin/env python3
"""WP-110 — Destructive Command Guard.

PreToolUse(Bash) hook that detects dangerous commands (rm -rf, git reset --hard,
git push --force, DROP TABLE, etc.) and either warns (advisory) or blocks (enforce).

Fail-open on all errors. Never crashes the session.
"""

import contextlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.config import load_config  # noqa: E402

DESTRUCTIVE_PATTERNS = [
    r"rm\s+(-[^\s]*r[^\s]*f|--recursive\s+--force|--force\s+--recursive|-[^\s]*f[^\s]*r)\b",
    r"rm\s+(-[^\s]*R[^\s]*f|-[^\s]*f[^\s]*R)\b",
    r"git\s+reset\s+--hard",
    r"git\s+push\s+(--force|-f)\b",
    r"git\s+clean\s+-fd",
    r"git\s+checkout\s+\.\s*$",
    r"git\s+branch\s+-D\b",
    r"DROP\s+(TABLE|DATABASE|SCHEMA)",
    r"TRUNCATE\s+TABLE",
    r"pkill\s+-9",
    r"kill\s+-9",
    r"chmod\s+(-R\s+)?777",
    r"dd\s+.*of=/dev/",
    r"mkfs\.",
    r"xargs\s+rm\s+(-[^\s]*r[^\s]*f|-[^\s]*R[^\s]*f|-[^\s]*f[^\s]*r)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DESTRUCTIVE_PATTERNS]

SAFE_PREFIXES = re.compile(
    r"^\s*(grep|egrep|fgrep|rg|ag|echo|printf|cat|#)", re.IGNORECASE
)


def _normalize_command(cmd: str) -> list[str]:
    """Split command into segments for independent checking."""
    segments = re.split(r"\s*(?:;|&&|\|\|)\s*", cmd)
    pipe_expanded = []
    for seg in segments:
        pipe_expanded.extend(re.split(r"\s*\|\s*", seg))
    result = []
    for seg in pipe_expanded:
        result.append(seg.strip())
        quoted = re.findall(r'(?:bash\s+-c\s+)(["\'])(.+?)\1', seg)
        for _, inner in quoted:
            result.append(inner.strip())
    return [s for s in result if s]


def _is_safe_context(segment: str) -> bool:
    """Return True if the segment is in a non-executing context."""
    return bool(SAFE_PREFIXES.match(segment))


def _check_segment(segment: str) -> str | None:
    """Return the matched pattern description if destructive, else None."""
    if _is_safe_context(segment):
        return None
    for pattern in COMPILED_PATTERNS:
        if pattern.search(segment):
            return segment.strip()
    return None


def _is_allowed(segment: str, allow_list: list[str]) -> bool:
    """A segment is allowed only if it exactly matches an allow-list entry
    (whitespace-normalized). Substring matching would let an allow entry
    forgive an entire chained command (`rm -rf node_modules; rm -rf ~`).
    """
    normalized = " ".join(segment.split())
    return any(" ".join(a.split()) == normalized for a in allow_list)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    cwd = data.get("cwd", ".")
    cfg = load_config(cwd)

    gate_cfg = cfg.get("gates", {}).get("destructive", {})
    if not gate_cfg.get("enabled", True):
        sys.exit(0)

    mode = gate_cfg.get("mode", "advisory")
    allow_commands = gate_cfg.get("allow_commands", [])
    extra_patterns = gate_cfg.get("extra_patterns", [])

    if extra_patterns:
        for pat in extra_patterns:
            with contextlib.suppress(re.error):
                COMPILED_PATTERNS.append(re.compile(pat, re.IGNORECASE))

    segments = _normalize_command(command)
    matched = None
    for seg in segments:
        if _is_allowed(seg, allow_commands):
            continue
        matched = _check_segment(seg)
        if matched:
            break

    if not matched:
        sys.exit(0)

    matched_display = matched[:80]
    if mode == "enforce":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "additionalContext": (
                    f"Destructive command blocked: `{matched_display}`. "
                    f'Set [gates.destructive].mode = "advisory" to allow with warning.'
                ),
            }
        }
        print(json.dumps(output))
        sys.exit(2)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"Destructive command detected: `{matched_display}`. "
                f"Consider a safer alternative."
            ),
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from fettle.dispatcher_types import CheckResult

    command = ctx.tool_input.get("command", "")
    if not command:
        return CheckResult.allow()

    gate_cfg = ctx.config.get("gates", {}).get("destructive", {})
    if not gate_cfg.get("enabled", True):
        return CheckResult.allow()

    mode = gate_cfg.get("mode", "advisory")
    allow_commands = gate_cfg.get("allow_commands", [])
    extra_patterns = gate_cfg.get("extra_patterns", [])

    if extra_patterns:
        for pat in extra_patterns:
            with contextlib.suppress(re.error):
                COMPILED_PATTERNS.append(re.compile(pat, re.IGNORECASE))

    segments = _normalize_command(command)
    matched = None
    for seg in segments:
        if _is_allowed(seg, allow_commands):
            continue
        matched = _check_segment(seg)
        if matched:
            break

    if not matched:
        return CheckResult.allow()

    matched_display = matched[:80]
    if mode == "enforce":
        return CheckResult.block(
            f"Destructive command blocked: `{matched_display}`.",
            hook_specific_output={
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "additionalContext": (
                    f"Destructive command blocked: `{matched_display}`. "
                    f'Set [gates.destructive].mode = "advisory" to allow with warning.'
                ),
            },
        )

    return CheckResult.advisory(
        f"Destructive command detected: `{matched_display}`. Consider a safer alternative.",
        hook_specific_output={
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"Destructive command detected: `{matched_display}`. "
                f"Consider a safer alternative."
            ),
        },
    )


if __name__ == "__main__":
    main()
