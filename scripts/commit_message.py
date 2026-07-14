#!/usr/bin/env python3
"""WP-112 — Commit Message Validation.

PreToolUse(Bash) hook that validates git commit messages for conventional
commit format before the commit runs.

Fail-open on all errors. Never crashes the session.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config  # noqa: E402

DEFAULT_TYPES = [
    "feat", "fix", "docs", "style", "refactor", "perf",
    "test", "build", "ci", "chore", "revert",
]

CONVENTIONAL_RE = re.compile(
    r"^(?P<type>\w+)(?:\([\w\-./]+\))?!?\s*:\s+(?P<subject>.+)$"
)


def _extract_message(command: str) -> str | None:
    """Extract commit message from git commit command."""
    # Heredoc first: -m "$(cat <<'EOF'\n...\nEOF\n)"
    m = re.search(
        r"-m\s+\"\$\(cat\s+<<['\"]?EOF['\"]?\n(.+?)\nEOF",
        command, re.DOTALL,
    )
    if m:
        return m.group(1).strip()
    # Simple: -m "msg" or -m 'msg' (non-greedy, single line)
    m = re.search(r"""-m\s+["']([^"']+)["']""", command)
    if m:
        return m.group(1)
    return None


def _is_commit_command(command: str) -> bool:
    """Check if command is a git commit with a message."""
    if "git" not in command or "commit" not in command:
        return False
    # Skip amend without message, merge commits, etc.
    if "--amend" in command and "-m" not in command:
        return False
    if "--no-edit" in command:
        return False
    return bool(re.search(r"git\s+commit\b.*-m\s", command))


def _validate_message(msg: str, valid_types: list[str], max_subject: int) -> list[str]:
    """Validate commit message, return list of issues."""
    issues = []
    subject = msg.split("\\n")[0].split("\n")[0].strip()

    match = CONVENTIONAL_RE.match(subject)
    if not match:
        issues.append(
            f"Not conventional format. Expected: <type>(<scope>): <description>. "
            f"Valid types: {', '.join(valid_types)}"
        )
        return issues

    msg_type = match.group("type")
    if msg_type not in valid_types:
        issues.append(f"Invalid type '{msg_type}'. Valid: {', '.join(valid_types)}")

    if len(subject) > max_subject:
        issues.append(f"Subject is {len(subject)} chars (max {max_subject}).")

    if subject.endswith("."):
        issues.append("Subject should not end with a period.")

    return issues


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    if not _is_commit_command(command):
        sys.exit(0)

    cwd = data.get("cwd", ".")
    cfg = load_config(cwd)

    gate_cfg = cfg.get("gates", {}).get("commit_message", {})
    if not gate_cfg.get("enabled", True):
        sys.exit(0)

    mode = gate_cfg.get("mode", "advisory")
    valid_types = gate_cfg.get("types", DEFAULT_TYPES)
    max_subject = gate_cfg.get("max_subject_length", 72)

    msg = _extract_message(command)
    if not msg:
        sys.exit(0)

    issues = _validate_message(msg, valid_types, max_subject)
    if not issues:
        sys.exit(0)

    feedback = "Commit message issues:\n" + "\n".join(f"- {i}" for i in issues)

    if mode == "enforce":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "additionalContext": feedback,
            }
        }
        print(json.dumps(output))
        sys.exit(2)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": feedback,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from dispatcher_types import CheckResult

    command = ctx.tool_input.get("command", "")
    if not command or not _is_commit_command(command):
        return CheckResult.allow()

    gate_cfg = ctx.config.get("gates", {}).get("commit_message", {})
    if not gate_cfg.get("enabled", True):
        return CheckResult.allow()

    mode = gate_cfg.get("mode", "advisory")
    valid_types = gate_cfg.get("types", DEFAULT_TYPES)
    max_subject = gate_cfg.get("max_subject_length", 72)

    msg = _extract_message(command)
    if not msg:
        return CheckResult.allow()

    issues = _validate_message(msg, valid_types, max_subject)
    if not issues:
        return CheckResult.allow()

    feedback = "Commit message issues:\n" + "\n".join(f"- {i}" for i in issues)

    if mode == "enforce":
        return CheckResult.block(
            feedback,
            hook_specific_output={
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "additionalContext": feedback,
            },
        )

    return CheckResult.advisory(
        feedback,
        hook_specific_output={
            "hookEventName": "PreToolUse",
            "additionalContext": feedback,
        },
    )


if __name__ == "__main__":
    main()
