"""Fettle path utilities — centralized resolution, validation, and security.

All path handling goes through this module. Prevents:
- Directory traversal (../)
- Symlink escape outside repo
- Incorrect relative path resolution
- Paths with spaces breaking shell commands
"""

from __future__ import annotations

import os
from pathlib import Path


def find_repo_root(start: str | Path | None = None) -> Path | None:
    """Find the repository root by walking up from start (or CWD) looking for .git."""
    if start is None:
        start = Path.cwd()
    else:
        start = Path(start).resolve()

    current = start
    for _ in range(50):
        if (current / ".git").exists():
            return current
        if (current / ".fettle.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def resolve_path(path: str | Path, repo_root: Path | None = None) -> Path:
    """Resolve a path to absolute, expanding user and resolving symlinks."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        if repo_root:
            p = repo_root / p
        else:
            p = Path.cwd() / p
    return p.resolve()


def is_within_repo(path: str | Path, repo_root: Path) -> bool:
    """Check if a resolved path is within the repository root.

    Prevents directory traversal and symlink escape.
    """
    try:
        resolved = Path(path).resolve()
        repo_resolved = repo_root.resolve()
        return str(resolved).startswith(str(repo_resolved) + os.sep) or resolved == repo_resolved
    except (OSError, ValueError):
        return False


def relative_to_repo(path: str | Path, repo_root: Path) -> str:
    """Get a normalized relative path from repo root. Returns '' if outside repo."""
    try:
        resolved = Path(path).resolve()
        return str(resolved.relative_to(repo_root.resolve()))
    except (ValueError, OSError):
        return ""


def is_implementation_file(path: str | Path) -> bool:
    """Check if a path is an implementation file (not config, not docs)."""
    IMPL_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".sh"}
    return Path(path).suffix in IMPL_EXTENSIONS


def is_test_file(path: str | Path) -> bool:
    """Check if a path is a test file."""
    p = Path(path)
    name = p.name.lower()
    parts = [part.lower() for part in p.parts]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.ts")
        or name.endswith(".test.js")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.js")
        or "tests" in parts
        or "test" in parts
    )


def is_excluded(path: str | Path, exclude_patterns: list[str] | None = None) -> bool:
    """Check if a path matches any exclude pattern."""
    if not exclude_patterns:
        return False
    p = str(Path(path))
    for pattern in exclude_patterns:
        if pattern in p:
            return True
    return False


def safe_relative_display(path: str | Path, repo_root: Path | None = None) -> str:
    """Get a safe display string for a path (relative if possible, no sensitive info)."""
    if repo_root:
        rel = relative_to_repo(path, repo_root)
        if rel:
            return rel
    return Path(path).name
