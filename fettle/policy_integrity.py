"""Detect effective-policy changes during a hook session."""

from __future__ import annotations

import hashlib
import json

from fettle.config import state_dir
from fettle.dispatcher_types import CheckResult


def _digest(config: dict) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def status(session_id: str | None, config: dict) -> tuple[str, str, str, bool]:
    path = state_dir(session_id or "unknown") / "session-start.json"
    try:
        start = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        start = None
    current_gate = config.get("gates", {}).get("config_protect", {})
    current_enforces = bool(
        current_gate.get("enabled", False) and current_gate.get("mode") == "enforce"
    )
    if start is None:
        return "unknown", "", _digest(config), current_enforces
    before = start.get("policy_digest")
    after = _digest(config)
    start_enforces = bool(
        start.get("config_protect_enabled", False)
        and start.get("config_protect_mode") == "enforce"
    )
    if not isinstance(before, str) or not before:
        return "unknown", "", after, start_enforces or current_enforces
    return (
        "pass" if before == after else "changed",
        before,
        after,
        start_enforces or current_enforces,
    )


def run_check(ctx):
    current, _before, _after, enforce = status(ctx.session_id, ctx.config)
    if current == "pass":
        return CheckResult.allow()
    message = (
        "Verify gate: policy changed during this session (effective policy digest). "
        "Run: fettle config --explain"
        if current == "changed"
        else "Verify gate: policy integrity evidence is unavailable. Run: fettle doctor"
    )
    return CheckResult.block(message) if enforce else CheckResult.advisory(message)
