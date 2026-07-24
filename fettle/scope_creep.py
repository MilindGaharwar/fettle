#!/usr/bin/env python3
"""WP-114 — Scope Creep Warning.

PostToolUse(Write|Edit|Bash) hook that warns when too many distinct files
are modified in a session. Advisory only — never blocks.

Also detects git commit in Bash commands to reset the counter.

Fail-open on all errors.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.config import load_config  # noqa: E402


def _get_state_path(state_dir: str, session_id: str) -> str:
    safe_id = re.sub(r"[^a-zA-Z0-9_.\-]", "_", session_id)
    return os.path.join(state_dir, f"{safe_id}.scope.json")


def _load_state(state_path: str) -> dict:
    if not os.path.isfile(state_path):
        return {"files": [], "warned_at": [], "committed": False}
    try:
        with open(state_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"files": [], "warned_at": [], "committed": False}


def _save_state(state_path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(state, f)


def _is_commit(command: str) -> bool:
    return bool(re.search(r"git\s+commit\b", command))


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_name: str = data.get("tool_name", "")
    tool_input: dict = data.get("tool_input", {})
    cwd = data.get("cwd", ".")
    session_id: str = data.get("session_id", "unknown")

    cfg = load_config(cwd)
    gate_cfg = cfg.get("gates", {}).get("scope_creep", {})
    if not gate_cfg.get("enabled", True):
        sys.exit(0)

    warning_threshold = gate_cfg.get("warning_threshold", 15)
    critical_threshold = gate_cfg.get("critical_threshold", 25)
    reset_on_commit = gate_cfg.get("reset_on_commit", True)

    state_dir = os.environ.get(
        "FETTLE_SCOPE_STATE_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".state", "sessions"),
    )
    state_path = _get_state_path(state_dir, session_id)
    state = _load_state(state_path)

    # Handle commit reset
    if tool_name == "Bash" and reset_on_commit:
        command = tool_input.get("command", "")
        if _is_commit(command):
            state["files"] = []
            state["warned_at"] = []
            _save_state(state_path, state)
            sys.exit(0)

    # Track file edits
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if file_path and file_path not in state["files"]:
            state["files"].append(file_path)

    file_count = len(state["files"])

    # Check thresholds
    output = None
    if file_count >= critical_threshold and critical_threshold not in state.get("warned_at", []):
        state.setdefault("warned_at", []).append(critical_threshold)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"Scope creep risk: {file_count} files modified (threshold: {critical_threshold}). "
                    f"Strongly consider stopping, reviewing, and committing before continuing."
                ),
            }
        }
    elif file_count >= warning_threshold and warning_threshold not in state.get("warned_at", []):
        state.setdefault("warned_at", []).append(warning_threshold)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"Scope check: {file_count} files modified this session (threshold: {warning_threshold}). "
                    f"Is this still on-task? Consider committing current changes."
                ),
            }
        }

    _save_state(state_path, state)

    if output:
        print(json.dumps(output))

    sys.exit(0)


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from fettle.dispatcher_types import CheckResult

    tool_name = ctx.tool_name or ""
    tool_input = ctx.tool_input
    session_id = ctx.session_id or "unknown"

    gate_cfg = ctx.config.get("gates", {}).get("scope_creep", {})
    if not gate_cfg.get("enabled", True):
        return CheckResult.allow()

    warning_threshold = gate_cfg.get("warning_threshold", 15)
    critical_threshold = gate_cfg.get("critical_threshold", 25)
    reset_on_commit = gate_cfg.get("reset_on_commit", True)

    state_dir = os.environ.get(
        "FETTLE_SCOPE_STATE_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".state", "sessions"),
    )
    state_path = _get_state_path(state_dir, session_id)
    state = _load_state(state_path)

    if tool_name == "Bash" and reset_on_commit:
        command = tool_input.get("command", "")
        if _is_commit(command):
            state["files"] = []
            state["warned_at"] = []
            _save_state(state_path, state)
            return CheckResult.allow()

    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if file_path and file_path not in state["files"]:
            state["files"].append(file_path)

    file_count = len(state["files"])

    msg = None
    if file_count >= critical_threshold and critical_threshold not in state.get("warned_at", []):
        state.setdefault("warned_at", []).append(critical_threshold)
        msg = (
            f"Scope creep risk: {file_count} files modified (threshold: {critical_threshold}). "
            f"Strongly consider stopping, reviewing, and committing before continuing."
        )
    elif file_count >= warning_threshold and warning_threshold not in state.get("warned_at", []):
        state.setdefault("warned_at", []).append(warning_threshold)
        msg = (
            f"Scope check: {file_count} files modified this session (threshold: {warning_threshold}). "
            f"Is this still on-task? Consider committing current changes."
        )

    _save_state(state_path, state)

    if msg:
        return CheckResult.advisory(
            msg,
            hook_specific_output={"hookEventName": "PostToolUse", "additionalContext": msg},
        )
    return CheckResult.allow()


if __name__ == "__main__":
    main()
