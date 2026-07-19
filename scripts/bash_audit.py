"""WP-E — Bash Structured Audit.

PostToolUse(Bash) check that logs structured audit events.
Privacy-first: does NOT log raw commands by default.
Always returns allow — audit only, never blocks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time


logger = logging.getLogger(__name__)


def _redact(command: str, patterns: list[str], replacement: str = "[REDACTED]") -> str:
    for pat in patterns:
        try:
            command = re.sub(pat, replacement, command, flags=re.IGNORECASE)
        except re.error:
            return "[REDACTION_ERROR]"
    return command


def _safe_session_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", value) or "unknown"


def run_check(ctx):
    """PostToolUse(Bash) — write structured audit event. Never blocks."""
    from dispatcher_types import CheckResult

    gate_cfg = ctx.config.get("gates", {}).get("bash_audit", {})
    if not gate_cfg.get("enabled", False):
        return CheckResult.allow()

    try:
        command = ctx.tool_input.get("command", "")
        response = ctx.input.raw.get("tool_response", {})

        record: dict = {
            "ts": time.time(),
            "command_hash": hashlib.sha256(command.encode("utf-8")[:100]).hexdigest()[:16],
        }

        if gate_cfg.get("capture_exit_code", True):
            record["exit_code"] = response.get("exit_code")
        if gate_cfg.get("capture_duration", True):
            record["duration_ms"] = response.get("duration_ms")

        if gate_cfg.get("capture_command", False):
            redaction_cfg = gate_cfg.get("redaction", {})
            patterns = redaction_cfg.get("patterns", [
                r"(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*\S+",
                r"(?i)bearer\s+\S+",
            ])
            replacement = redaction_cfg.get("replacement", "[REDACTED]")

            if redaction_cfg.get("fail_closed", True):
                redacted = _redact(command, patterns, replacement)
                if redacted != "[REDACTION_ERROR]":
                    record["command"] = redacted
            else:
                record["command"] = _redact(command, patterns, replacement)

        session_id = _safe_session_id(ctx.session_id or "unknown")
        from config import state_dir
        output_dir = state_dir(session_id)
        output_path = output_dir / "bash_events.jsonl"

        line = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
        fd = os.open(str(output_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)

    except Exception:  # noqa: BLE001 — audit must never block
        logger.debug("fettle: bash_audit write failed", exc_info=True)

    return CheckResult.allow()
