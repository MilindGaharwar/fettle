"""Fettle v0.5.0 — WP-72: Tool/runtime discovery.

Detect available tools, runtime versions, and lockfile status.
Foundational for all checkers — tells them what's available to run.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RuntimeInfo:
    """Information about an available runtime."""

    name: str
    available: bool = False
    version: str = ""
    path: str | None = None
    expected_version: str = ""


@dataclass
class ToolInfo:
    """Information about an available tool."""

    name: str
    available: bool = False
    version: str = ""
    path: str | None = None


@dataclass
class LockfileSyncResult:
    """Whether a lockfile is in sync with its source."""

    in_sync: bool = True
    message: str = ""


_RUNTIME_COMMANDS: dict[str, tuple[str, list[str]]] = {
    "python": ("python3", ["--version"]),
    "node": ("node", ["--version"]),
    "rust": ("rustc", ["--version"]),
    "go": ("go", ["version"]),
}

_VERSION_FILES: dict[str, str] = {
    "python": ".python-version",
    "node": ".node-version",
}


def _run_version_cmd(cmd: str, args: list[str]) -> tuple[bool, str, str]:
    path = shutil.which(cmd)
    if not path:
        return False, "", ""
    try:
        proc = subprocess.run(
            [path, *args],
            capture_output=True,
            timeout=5,
        )
        output = proc.stdout.decode("utf-8", errors="replace").strip()
        if not output:
            output = proc.stderr.decode("utf-8", errors="replace").strip()
        version = _extract_version(output)
        return True, version, path
    except (subprocess.TimeoutExpired, OSError):
        return False, "", path or ""


def _extract_version(output: str) -> str:
    import re
    match = re.search(r"(\d+\.\d+[\.\d]*)", output)
    return match.group(1) if match else output


def discover_runtime(name: str, cwd: str | None = None) -> RuntimeInfo:
    """Discover a runtime (python, node, rust, go) and its version."""
    if name not in _RUNTIME_COMMANDS:
        return RuntimeInfo(name=name, available=False)

    cmd, args = _RUNTIME_COMMANDS[name]
    available, version, path = _run_version_cmd(cmd, args)

    expected = ""
    if cwd:
        version_file = _VERSION_FILES.get(name)
        if version_file:
            vf_path = Path(cwd) / version_file
            if vf_path.is_file():
                expected = vf_path.read_text().strip()

    return RuntimeInfo(
        name=name,
        available=available,
        version=version,
        path=path if available else None,
        expected_version=expected,
    )


def discover_tool(name: str, search_paths: list[str] | None = None) -> ToolInfo:
    """Discover whether a tool is available and where."""
    if search_paths:
        for sp in search_paths:
            candidate = os.path.join(sp, name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return ToolInfo(name=name, available=True, path=candidate)

    path = shutil.which(name)
    if path:
        return ToolInfo(name=name, available=True, path=path)
    return ToolInfo(name=name, available=False)


def check_lockfile_sync(cwd: str, source_file: str, lock_file: str) -> LockfileSyncResult:
    """Check if lockfile is newer than or in sync with its source."""
    root = Path(cwd)
    source = root / source_file
    lock = root / lock_file

    if not source.is_file():
        return LockfileSyncResult(in_sync=True, message="Source file not found")
    if not lock.is_file():
        return LockfileSyncResult(in_sync=False, message=f"{lock_file} missing")

    source_mtime = source.stat().st_mtime_ns
    lock_mtime = lock.stat().st_mtime_ns

    if source_mtime > lock_mtime:
        return LockfileSyncResult(
            in_sync=False,
            message=f"{source_file} is newer than {lock_file} — out of sync",
        )
    return LockfileSyncResult(in_sync=True)
