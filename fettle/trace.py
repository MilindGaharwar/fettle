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
import time

AUDIT_SCHEMA_VERSION = 2


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
) -> None:
    """Log a hook decision to the trace file."""
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
    except OSError:
        pass


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
