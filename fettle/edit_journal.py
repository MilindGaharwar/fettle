"""Dispatcher-owned edit journal and session-start source evidence."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from fettle import config
from fettle.paths import classify_file


@dataclass(frozen=True)
class JournalRead:
    entries: tuple[dict, ...]
    malformed_lines: int = 0


def path(session_id: str | None) -> Path:
    override = os.environ.get("FETTLE_EDIT_TRACKING")
    return Path(override) if override else config.state_dir(session_id or "unknown") / "edits.jsonl"


def record(session_id: str | None, target: Path, tool: str | None) -> None:
    destination = path(session_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "file": str(target), "ts": time.time(), "tool": tool or "Edit", "tested": False,
    }, separators=(",", ":")) + "\n"
    fd = os.open(destination, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, payload.encode("utf-8"))
    finally:
        os.close(fd)


def entries(session_id: str | None) -> JournalRead:
    return read(path(session_id))


def read(source: Path) -> JournalRead:
    parsed: list[dict] = []
    malformed = 0
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError:
        return JournalRead(())
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            malformed += 1
            continue
        if not isinstance(value, dict):
            malformed += 1
            continue
        parsed.append(value)
    return JournalRead(tuple(parsed), malformed)


def mark_tested(session_id: str | None) -> None:
    current = entries(session_id)
    if current.malformed_lines:
        return
    destination = path(session_id)
    updated = [
        {**entry, "tested": True, "tested_ts": time.time()}
        if not entry.get("tested") else entry
        for entry in current.entries
    ]
    temporary = destination.with_suffix(".tmp")
    temporary.write_text("".join(json.dumps(item) + "\n" for item in updated), encoding="utf-8")
    os.replace(temporary, destination)


def _code_state(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if result.returncode:
        return "unknown"
    records = []
    for line in result.stdout.splitlines():
        relative = line[3:] if len(line) > 3 else ""
        if " -> " in relative:
            relative = relative.rsplit(" -> ", 1)[1]
        if classify_file(relative) not in {"implementation", "test"}:
            continue
        candidate = root / relative
        try:
            content = hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.is_file() else "missing"
        except OSError:
            content = "unknown"
        records.append((line[:2], relative, content))
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def record_session_start(session_id: str | None, root: Path, policy_digest: str) -> None:
    destination = config.state_dir(session_id or "unknown") / "session-start.json"
    if destination.exists():
        return
    payload = {
        "schema_version": 1,
        "root": str(root.resolve()),
        "source_state": _code_state(root),
        "policy_digest": policy_digest,
    }
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.link(temporary, destination)
    except FileExistsError:
        pass
    finally:
        temporary.unlink(missing_ok=True)


def needs_verification(session_id: str | None, root: Path) -> bool:
    journal = entries(session_id)
    if journal.malformed_lines:
        return True
    if any(classify_file(str(item.get("file", ""))) in {"implementation", "test"}
           for item in journal.entries):
        return True
    start_path = config.state_dir(session_id or "unknown") / "session-start.json"
    try:
        start = json.loads(start_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return _code_state(root) not in {"unknown", hashlib.sha256(b"[]").hexdigest()}
    return start.get("source_state") != _code_state(root)
