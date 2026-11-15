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


def status(session_id: str | None, config: dict) -> tuple[str, str, str]:
    path = state_dir(session_id or "unknown") / "session-start.json"
    try:
        start = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return "unknown", "", _digest(config)
    before = start.get("policy_digest")
    after = _digest(config)
    if not isinstance(before, str) or not before:
        return "unknown", "", after
    return ("pass" if before == after else "changed"), before, after


def run_check(ctx):
    current, _before, _after = status(ctx.session_id, ctx.config)
    if current == "pass":
        return CheckResult.allow()
    message = (
        "Verify gate: policy changed during this session (effective policy digest). "
        "Run: fettle config --explain"
        if current == "changed"
        else "Verify gate: policy integrity evidence is unavailable. Run: fettle doctor"
    )
    mode = ctx.config.get("gates", {}).get("config_protect", {}).get("mode", "advisory")
    return CheckResult.block(message) if mode == "enforce" else CheckResult.advisory(message)
