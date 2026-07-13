"""Fettle v0.5.0 — WP-71: Git change-set detection.

Robust source of truth for "what changed" — drives --changed tier
and workspace routing.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import StrEnum


class ChangeStatus(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"
    UNTRACKED = "untracked"


_STATUS_MAP = {
    "A": ChangeStatus.ADDED,
    "M": ChangeStatus.MODIFIED,
    "D": ChangeStatus.DELETED,
    "R": ChangeStatus.RENAMED,
    "C": ChangeStatus.COPIED,
    "?": ChangeStatus.UNTRACKED,
}


@dataclass
class ChangedFile:
    """A file that changed, with its status and optional workspace."""

    path: str
    status: ChangeStatus
    workspace: str | None = None


def _git(cwd: str, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            timeout=10,
        )
        return proc.returncode, proc.stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return -1, ""


def _is_git_repo(cwd: str) -> bool:
    rc, _ = _git(cwd, "rev-parse", "--git-dir")
    return rc == 0


def _parse_status_line(line: str) -> ChangedFile | None:
    if not line or len(line) < 4:
        return None
    status_char = line[0] if line[0] != " " else line[1]
    if status_char in ("R", "C"):
        parts = line[3:].split(" -> ")
        path = parts[-1].strip() if parts else line[3:].strip()
    else:
        path = line[3:].strip()
    status = _STATUS_MAP.get(status_char)
    if not status or not path:
        return None
    return ChangedFile(path=path, status=status)


def _parse_diff_output(output: str) -> list[ChangedFile]:
    files = []
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", maxsplit=2)
        if len(parts) < 2:
            continue
        status_char = parts[0][0]
        path = parts[-1]
        status = _STATUS_MAP.get(status_char)
        if status and path:
            files.append(ChangedFile(path=path, status=status))
    return files


def get_staged(cwd: str) -> list[ChangedFile]:
    """Files staged for commit (git diff --cached)."""
    rc, output = _git(cwd, "diff", "--cached", "--name-status")
    if rc != 0:
        return []
    return _parse_diff_output(output)


def get_unstaged(cwd: str) -> list[ChangedFile]:
    """Modified tracked files not yet staged."""
    rc, output = _git(cwd, "diff", "--name-status")
    if rc != 0:
        return []
    return _parse_diff_output(output)


def get_untracked(cwd: str) -> list[ChangedFile]:
    """Untracked files (respects .gitignore)."""
    rc, output = _git(cwd, "ls-files", "--others", "--exclude-standard")
    if rc != 0:
        return []
    files = []
    for line in output.strip().split("\n"):
        path = line.strip()
        if path:
            files.append(ChangedFile(path=path, status=ChangeStatus.UNTRACKED))
    return files


def get_vs_base(cwd: str, base: str = "main") -> list[ChangedFile]:
    """Files changed since merge-base with given branch."""
    rc, merge_base_out = _git(cwd, "merge-base", base, "HEAD")
    if rc != 0:
        rc, merge_base_out = _git(cwd, "merge-base", f"origin/{base}", "HEAD")
        if rc != 0:
            return []
    merge_base = merge_base_out.strip()
    if not merge_base:
        return []
    rc, output = _git(cwd, "diff", "--name-status", merge_base, "HEAD")
    if rc != 0:
        return []
    return _parse_diff_output(output)


def get_changed_files(cwd: str) -> list[ChangedFile]:
    """All changed files: staged + unstaged + untracked. Safe on non-git dirs."""
    if not _is_git_repo(cwd):
        return []
    return get_staged(cwd) + get_unstaged(cwd) + get_untracked(cwd)
