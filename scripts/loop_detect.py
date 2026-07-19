#!/usr/bin/env python3
"""WP-111 — Tool Loop Detection.

PostToolUse hook that detects repeated identical tool calls and warns.
Advisory only — never blocks.

Fail-open on all errors.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config  # noqa: E402


def _hash_call(tool_name: str, tool_input: dict) -> str:
    """Deterministic hash of tool_name + params."""
    raw = json.dumps({"t": tool_name, "i": tool_input}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_state_path(state_dir: str, session_id: str) -> str:
    import re
    safe_id = re.sub(r"[^a-zA-Z0-9_.\-]", "_", session_id)
    return os.path.join(state_dir, f"{safe_id}.loop.jsonl")


def _read_recent(state_path: str, window: int) -> list[str]:
    """Read last N call hashes from state file."""
    if not os.path.isfile(state_path):
        return []
    try:
        with open(state_path) as f:
            lines = f.readlines()
        return [line.strip() for line in lines[-window:] if line.strip()]
    except OSError:
        return []


def _append_hash(state_path: str, call_hash: str) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "a") as f:
        f.write(call_hash + "\n")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_name: str = data.get("tool_name", "")
    tool_input: dict = data.get("tool_input", {})
    if not tool_name:
        sys.exit(0)

    cwd = data.get("cwd", ".")
    session_id: str = data.get("session_id", "unknown")

    cfg = load_config(cwd)
    gate_cfg = cfg.get("gates", {}).get("loop_detect", {})
    if not gate_cfg.get("enabled", True):
        sys.exit(0)

    threshold = gate_cfg.get("threshold", 3)
    window = gate_cfg.get("window", 7)

    state_dir = os.environ.get(
        "FETTLE_LOOP_STATE_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".state", "sessions"),
    )

    state_path = _get_state_path(state_dir, session_id)
    call_hash = _hash_call(tool_name, tool_input)

    # Read recent calls
    recent = _read_recent(state_path, window - 1)

    # Append current call
    try:
        _append_hash(state_path, call_hash)
    except OSError:
        sys.exit(0)

    # Check for loop: count consecutive identical calls at tail of window
    recent.append(call_hash)
    windowed = recent[-window:]
    count = 0
    for h in reversed(windowed):
        if h == call_hash:
            count += 1
        else:
            break

    if count >= threshold:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"Loop detected: `{tool_name}` called {count}x with identical params "
                    f"in last {window} calls. Consider a different approach."
                ),
            }
        }
        print(json.dumps(output))

    sys.exit(0)


_FALLBACK_REMINDER = (
    "Pause and inspect the evidence before repeating the same action. "
    "Form a new hypothesis, then choose a tool call that tests it."
)


def _get_discipline_reminder(disc_cfg: dict, state_dir: str, session_id: str) -> str:
    """Load a 2-sentence reminder from discipline-debugging, with cooldown."""
    import re
    import time
    from pathlib import Path

    cooldown_s = float(disc_cfg.get("cooldown_seconds", 300))

    # Cooldown check via timestamp file
    safe_id = re.sub(r"[^a-zA-Z0-9_.\-]", "_", session_id)
    marker = Path(state_dir) / f"{safe_id}.discipline-ts"
    now = time.time()
    if marker.is_file():
        try:
            last = float(marker.read_text().strip())
            if now - last < cooldown_s:
                return ""
        except (ValueError, OSError):
            pass
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(now))
    except OSError:
        pass

    # Load snippet from disciplines plugin
    skills_path = Path(os.path.expanduser(
        disc_cfg.get("skills_path", "~/.claude/plugins/disciplines/skills")
    ))
    skill_file = skills_path / "discipline-debugging" / "SKILL.md"
    if not skill_file.is_file():
        return _FALLBACK_REMINDER

    try:
        text = skill_file.read_text(encoding="utf-8")
        if text.startswith("---"):
            _, _, text = text.partition("---\n")
            _, _, text = text.partition("---\n")
        text = " ".join(
            line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        sentences = re.findall(r"[^.!?]+[.!?]", text)
        return " ".join(sentences[:2]).strip() if len(sentences) >= 2 else _FALLBACK_REMINDER
    except OSError:
        return _FALLBACK_REMINDER


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from dispatcher_types import CheckResult

    tool_name = ctx.tool_name or ""
    tool_input = ctx.tool_input
    if not tool_name:
        return CheckResult.allow()

    gate_cfg = ctx.config.get("gates", {}).get("loop_detect", {})
    if not gate_cfg.get("enabled", True):
        return CheckResult.allow()

    threshold = gate_cfg.get("threshold", 3)
    window = gate_cfg.get("window", 7)
    session_id = ctx.session_id or "unknown"

    state_dir = os.environ.get(
        "FETTLE_LOOP_STATE_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".state", "sessions"),
    )

    state_path = _get_state_path(state_dir, session_id)
    call_hash = _hash_call(tool_name, tool_input)

    recent = _read_recent(state_path, window - 1)
    try:
        _append_hash(state_path, call_hash)
    except OSError:
        return CheckResult.allow()

    recent.append(call_hash)
    windowed = recent[-window:]
    count = 0
    for h in reversed(windowed):
        if h == call_hash:
            count += 1
        else:
            break

    if count >= threshold:
        msg = (
            f"Loop detected: `{tool_name}` called {count}x with identical params "
            f"in last {window} calls. Consider a different approach."
        )

        # WP-C: Discipline link — inject debugging reminder on loop detection
        disc_cfg = ctx.config.get("gates", {}).get("discipline_link", {})
        if disc_cfg.get("enabled", True):
            reminder = _get_discipline_reminder(disc_cfg, state_dir, session_id)
            if reminder:
                msg += f"\n\nDiscipline reminder: {reminder}"

        return CheckResult.advisory(
            msg,
            hook_specific_output={
                "hookEventName": ctx.input.hook_event_name,
                "additionalContext": msg,
            },
        )

    return CheckResult.allow()


if __name__ == "__main__":
    main()
