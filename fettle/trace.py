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

v1 entries (no `schema`/`repo` keys) remain readable forever.
"""

import json
import os
import sys
import time

AUDIT_SCHEMA_VERSION = 2

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
            if os.path.isdir(os.path.join(probe, ".git")) or \
               os.path.isfile(os.path.join(probe, ".fettle.toml")):
                return os.path.basename(probe)
            probe = os.path.dirname(probe)
    except OSError:
        pass
    return ""


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
    }
    try:
        trace_path = _get_trace_path()
        with open(trace_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
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
    """Read recent trace entries."""
    trace_path = _get_trace_path()
    if not os.path.isfile(trace_path):
        return []
    entries = []
    with open(trace_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
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
