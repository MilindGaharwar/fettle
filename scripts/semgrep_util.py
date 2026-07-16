"""Anchored semgrep invocation.

Semgrep >= 1.136 resolves ``paths.include``/``paths.exclude`` rule filters
against the *project root* (the enclosing git root). When a scanned file is
not inside a git repo, path-scoped rules silently never match — or excludes
silently stop excluding. This module pins the project root explicitly so
path filters behave identically everywhere.
"""

import os


def _find_git_root(start_dir: str) -> str | None:
    """Return the nearest ancestor of start_dir containing .git, else None."""
    current = start_dir
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def anchored_semgrep_args(file_path: str, cwd: str | None = None) -> tuple[list[str], str]:
    """Build anchored semgrep target args for scanning file_path.

    Returns (args, run_cwd): append ``args`` to the semgrep command line
    and run it with ``cwd=run_cwd``. The project root is the file's git
    root, else the session cwd (if it contains the file), else the file's
    own directory.
    """
    abs_path = os.path.abspath(file_path)
    file_dir = os.path.dirname(abs_path)
    root = _find_git_root(file_dir)
    if root is None and cwd:
        abs_cwd = os.path.abspath(cwd)
        if abs_path.startswith(abs_cwd + os.sep):
            root = abs_cwd
    if root is None:
        root = file_dir
    target = os.path.relpath(abs_path, root)
    return ["--project-root", ".", target], root
