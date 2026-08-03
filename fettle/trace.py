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

v1 entries (no `schema`/`repo` keys) remain readable forever.
"""

import json
import os
import sys
import time

AUDIT_SCHEMA_VERSION = 2

# Opportunistic rotation threshold (WP-6, audit Opus C4): rotate_trace()
# existed but nothing in the production path ever called it, so the trace
# grew without bound. ~5 MB ≈ tens of thousands of entries.
_ROTATE_BYTES = 5 * 1024 * 1024

# One-time stderr warning flag: audit-log loss must be visible (WP: Stage-0
# failure-visibility), but must never spam or break the hook path.
_write_failure_warned = False


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
    duration_ms: float = 0.0,
    session_id: str = "",
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
        "findings": findings or [],
        "duration_ms": round(duration_ms, 2),
        "session_id": session_id,
        "parent_session_id": parent_session_id,
        "capsule_digest": capsule_digest,
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
            print(
                f"fettle: WARNING — audit trace write failed ({exc}); "
                "hook decisions are NOT being recorded. Run `fettle doctor`.",
                file=sys.stderr,
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
