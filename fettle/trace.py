"""Fettle trace — persistent, append-only audit log of hook decisions.

Writes to $XDG_STATE_HOME/fettle/trace.jsonl (one JSON object per line).

Schema v2 (WP-145 — stable, versioned; consumers must tolerate unknown keys):
    schema      int    — audit schema version (this file: 2)
    timestamp   str    — local ISO-8601
    ts          float  — unix epoch
    hook        str    — hook/gate that decided
    status      str    — pass | violation | blocked | tool_error | ...
    tool        str
    file        str
    repo        str    — repo root basename ('' when indeterminate) — enables
                         cross-repo aggregation (`fettle report --org`)
    findings    list[dict]
    duration_ms float
    session_id  str
    parent_session_id str — spawning session ('' when solo; WP-158)
    capsule_digest    str — 16-hex digest of the governing policy capsule
                             ('' when ungoverned; WP-158)
    role              str — effective P52 role ('' when undeclared)

v1 entries (no `schema`/`repo` keys) remain readable forever.
"""

import json
import hashlib
import os
import re
import sys
import time
from typing import Any

from fettle.evidence import EvidenceReference

AUDIT_SCHEMA_VERSION = 2
_MAX_TEXT = 2048
_MAX_FINDINGS = 50
_MAX_EVIDENCE = 20
_MAX_OVERRIDES = 20
_SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:ghp_|sk-)[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(?:api[_-]?key|password|secret|token)\w*\s*[=:]\s*\S+"),
    re.compile(r"(?i)bearer\s+\S+"),
)

# Opportunistic rotation threshold (WP-6, audit C4): rotate_trace()
# existed but nothing in the production path ever called it, so the trace
# grew without bound. ~5 MB ≈ tens of thousands of entries.
_ROTATE_BYTES = 5 * 1024 * 1024

# One-time stderr warning flag: audit-log loss must be visible (WP: Stage-0
# failure-visibility), but must never spam or break the hook path.
_write_failure_warned = False


def _redact_text(value: object, limit: int = _MAX_TEXT) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("***REDACTED***", text)
    return text[:limit]


def build_evidence(kind: str, **fields: Any) -> dict[str, Any]:
    """Build a bounded, redacted evidence artifact with a content-derived ID."""
    evidence: dict[str, Any] = {"kind": _redact_text(kind, 64)}
    for key in ("command", "exit_code", "duration_ms", "scope", "tool_version", "workspace"):
        value = fields.get(key)
        if value is None:
            continue
        if key == "command":
            if isinstance(value, (list, tuple)):
                evidence[key] = [_redact_text(part, 256) for part in value[:50]]
            else:
                evidence[key] = _redact_text(value)
        elif key in {"exit_code", "duration_ms"} and isinstance(value, (int, float)):
            evidence[key] = value
        else:
            evidence[key] = _redact_text(value, 256)
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    evidence["evidence_id"] = "ev-" + hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return evidence


def _bounded_finding(finding: dict) -> dict:
    allowed = {
        "schema_version", "checker", "severity", "file", "line", "column", "code",
        "message", "blocking", "confidence", "workspace", "suggested_fix", "impact",
        "action", "rerun_command", "evidence_id", "result_state", "redacted", "check",
        "error", "detail", "skipped_from", "budget_ms", "event", "_suppressed",
        "capsule", "lineage", "worktree_item", "runner_error", "fp",
    }
    result: dict[str, Any] = {}
    for key, value in finding.items():
        if key not in allowed:
            continue
        if isinstance(value, str):
            result[key] = _redact_text(value)
        elif isinstance(value, (bool, int, float)) or value is None:
            result[key] = value
    return result


def _bounded_evidence(evidence: dict) -> dict:
    bounded = build_evidence(
        str(evidence.get("kind", "unknown")),
        **{key: evidence[key] for key in (
            "command", "exit_code", "duration_ms", "scope", "tool_version", "workspace"
        ) if key in evidence},
    )
    if evidence.get("evidence_id"):
        bounded["evidence_id"] = _redact_text(evidence["evidence_id"], 128)
    if "artifact_digest" in evidence:
        try:
            reference = EvidenceReference(
                artifact_digest=evidence["artifact_digest"],
                kind=evidence["kind"],
                schema_version=evidence["schema_version"],
                expected=evidence.get("expected", {}),
            )
        except (KeyError, TypeError, ValueError):
            return bounded
        availability = evidence.get("availability")
        if availability not in {"available", "missing", "unavailable"}:
            return bounded
        bounded.update(reference.to_dict())
        bounded["availability"] = availability
        bounded["authority"] = "diagnostic_only"
        inspection = evidence.get("inspection")
        if isinstance(inspection, dict):
            allowed_text = {
                "producer", "scope", "source_binding", "policy_binding", "result",
                "completeness", "freshness", "validity", "reason", "recovery_action",
            }
            projected = {
                key: _redact_text(value, 512)
                for key, value in inspection.items()
                if key in allowed_text and isinstance(value, str)
            }
            if isinstance(inspection.get("accepted"), bool):
                projected["accepted"] = inspection["accepted"]
            if projected:
                bounded["inspection"] = projected
    return bounded


def _bounded_override(override: dict) -> dict:
    allowed = {
        "schema_version", "override_id", "actor", "reason", "timestamp", "expiry",
        "check_id", "scope", "revision", "policy_digest", "evidence_id", "surface",
    }
    return {
        key: _redact_text(value, 2048 if key == "reason" else 256)
        for key, value in override.items()
        if key in allowed and isinstance(value, str)
    }


def _get_trace_path() -> str:
    state_dir = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    trace_dir = os.path.join(state_dir, "fettle")
    os.makedirs(trace_dir, exist_ok=True)
    return os.path.join(trace_dir, "trace.jsonl")


def _repo_name(file: str) -> str:
    """Best-effort repo identity for org-level aggregation — never raises."""
    try:
        probe = os.path.dirname(os.path.abspath(file)) if file else os.getcwd()
        while probe and probe != os.path.dirname(probe):
            # .git may be a file (linked worktree), not only a dir
            if os.path.exists(os.path.join(probe, ".git")) or \
               os.path.isfile(os.path.join(probe, ".fettle.toml")):
                return os.path.basename(probe)
            probe = os.path.dirname(probe)
    except OSError:
        pass
    return ""


def _lineage_fields() -> tuple[str, str]:
    """(parent_session_id, capsule_digest) from the spawn env — never raises.

    Set by `fettle spawn` (WP-157); empty for solo sessions. The digest is
    the capsule filename stem — recorded even when unverified, so tampering
    still leaves an audit trail pointing at the file.
    """
    parent = os.environ.get("FETTLE_PARENT_SESSION", "")
    capsule = os.environ.get("FETTLE_POLICY_CAPSULE", "")
    digest = ""
    if capsule:
        digest = os.path.splitext(os.path.basename(capsule))[0]
    return parent, digest


def log_decision(
    hook: str,
    status: str,
    tool: str = "",
    file: str = "",
    findings: list[dict] | None = None,
    evidence: list[dict] | None = None,
    overrides: list[dict] | None = None,
    duration_ms: float = 0.0,
    session_id: str = "",
    role: str = "",
) -> bool:
    """Log a hook decision to the trace file.

    Returns True when the entry was durably appended. On write failure the
    entry is lost, but the failure is surfaced once per process on stderr —
    loss of the audit log must never be silent.
    """
    parent_session_id, capsule_digest = _lineage_fields()
    entry = {
        "schema": AUDIT_SCHEMA_VERSION,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ts": time.time(),
        "hook": hook,
        "status": status,
        "tool": tool,
        "file": file,
        "repo": _repo_name(file),
        "findings": [_bounded_finding(f) for f in (findings or [])[:_MAX_FINDINGS]],
        "evidence": [_bounded_evidence(e) for e in (evidence or [])[:_MAX_EVIDENCE]],
        "overrides": [_bounded_override(o) for o in (overrides or [])[:_MAX_OVERRIDES]],
        "duration_ms": round(duration_ms, 2),
        "session_id": session_id,
        "parent_session_id": parent_session_id,
        "capsule_digest": capsule_digest,
        "role": _redact_text(role, 32),
    }
    try:
        trace_path = _get_trace_path()
        with open(trace_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
        # Size-stat is cheap; actual rotation fires rarely. Concurrent
        # rotators are safe (atomic os.replace) — worst case a few entries
        # from the overlap window are dropped, which beats unbounded growth.
        if os.path.getsize(trace_path) > _ROTATE_BYTES:
            rotate_trace()
        return True
    except OSError as exc:
        global _write_failure_warned
        if not _write_failure_warned:
            sys.stderr.write(
                f"fettle: WARNING — audit trace write failed ({exc}); "
                "hook decisions are NOT being recorded. Run `fettle doctor`.\n"
            )
            _write_failure_warned = True
        return False


def probe_writable() -> tuple[bool, str]:
    """Check the audit trace is appendable — doctor's audit-log health probe.

    Returns (ok, path-or-error). Loss of the audit log must be detectable
    from outside the log itself.
    """
    try:
        path = _get_trace_path()
        with open(path, "a"):
            pass
        return True, path
    except OSError as exc:
        return False, str(exc)


def read_tail(max_bytes: int = 65536) -> list[dict]:
    """Parse trace entries from the last `max_bytes` of the trace file.

    Cheap recent-history probe (bounded read regardless of file size) for
    in-hook consumers like the dispatcher's repeated-failure escalation.
    Never raises; returns [] when the trace is missing or unreadable.
    """
    try:
        trace_path = _get_trace_path()
        if not os.path.isfile(trace_path):
            return []
        size = os.path.getsize(trace_path)
        with open(trace_path, "rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()  # discard partial first line
            raw = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def get_recent_decisions(limit: int = 20) -> list[dict]:
    """Read recent trace entries — bounded tail-read, not a full-file scan."""
    entries = read_tail(max_bytes=max(65536, limit * 2048))
    return entries[-limit:]


def rotate_trace(max_entries: int = 5000) -> None:
    """Rotate trace file if it exceeds max_entries."""
    trace_path = _get_trace_path()
    if not os.path.isfile(trace_path):
        return
    try:
        with open(trace_path) as f:
            lines = f.readlines()
        if len(lines) > max_entries:
            keep = lines[-max_entries:]
            tmp = trace_path + ".tmp"
            with open(tmp, "w") as f:
                f.writelines(keep)
            os.replace(tmp, trace_path)
    except OSError:
        pass
