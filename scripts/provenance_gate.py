"""WP-N — Provenance Policy Gate.

PostToolUse(Write) check that enforces configurable provenance/disclosure
policy for AI-generated files. NOT a universal "every file must have a header."

Modes:
  none     — no provenance enforcement (default)
  manifest — AI-touched files tracked in .fettle/provenance.jsonl (audit only)
  marker   — new files require a configurable marker comment (advisory)
  commit   — defers to commit_message check for provenance tag
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".so", ".dll", ".dylib",
    ".exe", ".bin", ".dat", ".vsix",
}

_EXEMPT_EXTENSIONS = {
    ".json", ".lock", ".toml", ".yaml", ".yml",
    ".cfg", ".ini", ".env", ".csv",
}


def _is_exempt(file_path: str, exempt_paths: list[str]) -> bool:
    import fnmatch
    basename = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _BINARY_EXTENSIONS or ext in _EXEMPT_EXTENSIONS:
        return True
    if basename.startswith("."):
        return True
    return any(fnmatch.fnmatch(file_path, pat) for pat in exempt_paths)


def _is_new_file(file_path: str, cwd: str) -> bool:
    """Check if this is a newly created file (not an edit to existing)."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "ls-files", "--error-unmatch", file_path],
            capture_output=True, timeout=0.5,
        )
        return result.returncode != 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _record_manifest(file_path: str, cwd: str, session_id: str) -> None:
    """Append to .fettle/provenance.jsonl."""
    manifest_dir = Path(cwd) / ".fettle"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "provenance.jsonl"
    record = json.dumps({
        "ts": time.time(),
        "file": os.path.relpath(file_path, cwd),
        "session_id": session_id,
    }, separators=(",", ":"))
    try:
        fd = os.open(str(manifest_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, (record + "\n").encode())
        finally:
            os.close(fd)
    except OSError:
        pass


def _has_marker(file_path: str, marker_text: str) -> bool:
    """Check if file contains the required provenance marker."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            head = f.read(2048)
        return marker_text in head
    except OSError:
        return True


def run_check(ctx):
    """PostToolUse(Write) — provenance policy enforcement."""
    from dispatcher_types import CheckResult

    cfg = ctx.config.get("gates", {}).get("provenance", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    mode = cfg.get("mode", "none")
    if mode == "none":
        return CheckResult.allow()

    file_path = ctx.tool_input.get("file_path", "")
    if not file_path:
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    session_id = ctx.session_id or "unknown"
    exempt_paths = cfg.get("exempt_paths", [
        "**/*.json", "**/*.lock", "**/migrations/**", "**/*.generated.*",
    ])

    if _is_exempt(file_path, exempt_paths):
        return CheckResult.allow()

    if not _is_new_file(file_path, cwd):
        return CheckResult.allow()

    # Manifest mode: record silently
    if mode == "manifest":
        _record_manifest(file_path, cwd, session_id)
        return CheckResult.allow()

    # Marker mode: check for marker text in new files
    if mode == "marker":
        marker_text = cfg.get("marker_text", "")
        if not marker_text:
            return CheckResult.allow()
        if _has_marker(file_path, marker_text):
            return CheckResult.allow()

        rel = os.path.relpath(file_path, cwd)
        msg = "Provenance: new file " + rel + " missing marker: " + marker_text
        return CheckResult.advisory(msg, hook_specific_output={
            "hookEventName": ctx.input.hook_event_name,
            "additionalContext": msg,
        })

    # Commit mode: defers to commit_message check (no action here)
    if mode == "commit":
        _record_manifest(file_path, cwd, session_id)
        return CheckResult.allow()

    return CheckResult.allow()
