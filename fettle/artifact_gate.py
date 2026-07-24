"""WP-O — Artifact Verification Gate.

PreToolUse(Bash): blocks publish commands without prior verification evidence.
PostToolUse(Bash): records verification commands as evidence.

Evidence model: binds to exact artifact identity + exit code.
Invalidated on rebuild/mutation of the same artifact.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_PUBLISH_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("docker push", re.compile(r"docker\s+push\s+(\S+)")),
    ("npm publish", re.compile(r"npm\s+publish")),
    ("pip upload", re.compile(r"(?:twine\s+upload|pip\s+upload)")),
    ("gh release", re.compile(r"gh\s+release\s+create\s+(\S+)")),
]

_VERIFY_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("cosign", re.compile(r"cosign\s+(?:sign|verify)\s+(\S+)")),
    ("trivy", re.compile(r"trivy\s+image\s+(\S+)")),
    ("sha256sum", re.compile(r"sha256sum\s+(\S+)")),
    ("docker trust", re.compile(r"docker\s+trust\s+sign\s+(\S+)")),
    ("checksum", re.compile(r"(?:md5sum|shasum|sha256sum)\s+(\S+)")),
]

_INVALIDATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"docker\s+build\s+.*-t\s+(\S+)"),
    re.compile(r"npm\s+run\s+build"),
    re.compile(r"cargo\s+build"),
    re.compile(r"go\s+build"),
]


def _extract_artifact_id(command: str, patterns: list[tuple[str, re.Pattern]]) -> tuple[str, str] | None:
    for name, pat in patterns:
        m = pat.search(command)
        if m:
            artifact = m.group(1) if m.lastindex else ""
            return name, artifact
    return None


def _evidence_path(session_id: str) -> Path:
    from fettle.config import state_dir
    return state_dir(session_id) / "artifact_evidence.jsonl"


def _load_evidence(session_id: str) -> list[dict]:
    path = _evidence_path(session_id)
    entries: list[dict] = []
    try:
        if path.is_file():
            for line in path.read_text().splitlines():
                if line.strip():
                    entries.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass
    return entries


def _record_evidence(session_id: str, record: dict) -> None:
    path = _evidence_path(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, separators=(",", ":")) + "\n"
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode())
        finally:
            os.close(fd)
    except OSError:
        logger.debug("fettle: artifact_gate write failed", exc_info=True)


def _has_valid_evidence(session_id: str, artifact_id: str) -> bool:
    entries = _load_evidence(session_id)
    for entry in reversed(entries):
        if entry.get("type") == "invalidate" and entry.get("artifact_id") == artifact_id:
            return False
        if (entry.get("type") == "verify" and entry.get("artifact_id") == artifact_id
                and entry.get("exit_code") == 0):
            return True
    return False


def run_check(ctx):
    """Dual-hook: PreToolUse gates publish, PostToolUse records evidence."""
    from fettle.dispatcher_types import CheckResult

    cfg = ctx.config.get("gates", {}).get("artifact_integrity", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    command = ctx.tool_input.get("command", "")
    if not command:
        return CheckResult.allow()

    session_id = ctx.session_id or "unknown"
    event = ctx.input.hook_event_name

    # PostToolUse: record verification evidence or invalidation
    if event == "PostToolUse":
        response = ctx.input.raw.get("tool_response", {})
        exit_code = response.get("exit_code", -1)

        match = _extract_artifact_id(command, _VERIFY_PATTERNS)
        if match:
            _record_evidence(session_id, {
                "type": "verify",
                "verification_tool": match[0],
                "artifact_id": match[1],
                "exit_code": exit_code if isinstance(exit_code, int) else -1,
                "ts": time.time(),
            })
            return CheckResult.allow()

        for pat in _INVALIDATE_PATTERNS:
            m = pat.search(command)
            if m:
                artifact = m.group(1) if m.lastindex else ""
                if artifact:
                    _record_evidence(session_id, {
                        "type": "invalidate",
                        "artifact_id": artifact,
                        "ts": time.time(),
                    })
                break

        return CheckResult.allow()

    # PreToolUse: check for evidence before publish
    if event == "PreToolUse":
        match = _extract_artifact_id(command, _PUBLISH_PATTERNS)
        if not match:
            return CheckResult.allow()

        publish_tool, artifact_id = match
        if not artifact_id:
            msg = "Artifact publish detected (" + publish_tool + ") but could not determine artifact identity."
            return CheckResult.advisory(msg, hook_specific_output={
                "hookEventName": event,
                "additionalContext": msg,
            })

        if _has_valid_evidence(session_id, artifact_id):
            return CheckResult.allow()

        mode = cfg.get("mode", "advisory")
        msg = ("Artifact publish (" + publish_tool + ") for " + artifact_id +
               " without verification evidence. Run a signing/scanning tool first.")

        if mode == "enforce":
            return CheckResult.block(msg, hook_specific_output={
                "hookEventName": event,
                "additionalContext": msg,
                "permissionDecision": "deny",
                "permissionDecisionReason": msg,
            })
        return CheckResult.advisory(msg, hook_specific_output={
            "hookEventName": event,
            "additionalContext": msg,
        })

    return CheckResult.allow()
