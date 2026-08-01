"""Worktree spine — WP7 (Stage 4, S4.2; design doc 09).

Isolation substrate for concurrent workstreams and UAT sessions: one git
worktree per work item under a configurable root (default
``.fettle/worktrees/``, inside the checkout so state travels with it;
scanners skip ``.fettle``). Branch naming: ``fettle/<item-id>``.

Fail-visible contract: functions return ``(value, error)`` — expected git
failures become error strings, never exceptions and never silent successes.
Removal refuses when the worktree is dirty; ``--force`` exists but is never
the default. Branches are left behind on removal (they may hold unmerged
work — deleting them is the operator's explicit call).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_GIT_TIMEOUT_S = 30
DEFAULT_ROOT = ".fettle/worktrees"


def _git(args: list[str], cwd: str) -> tuple[str, str]:
    """Run git, returning (stdout, error). Expected failures → error string."""
    try:
        proc = subprocess.run(
            ["git", *args], capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_S, cwd=cwd,
        )
    except FileNotFoundError:
        return "", "git not on PATH"
    except subprocess.TimeoutExpired:
        return "", f"git {args[0]} timed out after {_GIT_TIMEOUT_S}s"
    if proc.returncode != 0:
        return proc.stdout, (proc.stderr or "").strip() or f"git {args[0]} exited {proc.returncode}"
    return proc.stdout, ""


def git_common_dir(cwd: str) -> Path | None:
    """The shared .git dir — identical across all worktrees of a repo.

    State that must be visible to every worktree (claims, audit) lives
    here; per-worktree state stays local. None when not a git repo.
    """
    out, err = _git(["rev-parse", "--git-common-dir"], cwd)
    if err or not out.strip():
        return None
    p = Path(out.strip())
    return p if p.is_absolute() else (Path(cwd) / p).resolve()


def is_linked_worktree(cwd: str) -> bool:
    """True inside a linked (non-main) worktree — where .git is a file."""
    root = Path(cwd)
    for candidate in (root, *root.parents):
        dot_git = candidate / ".git"
        if dot_git.is_file():
            return True
        if dot_git.is_dir():
            return False
    return False


def worktrees_root(repo_root: str, config: dict) -> Path:
    rel = config.get("worktrees", {}).get("root", DEFAULT_ROOT)
    return Path(repo_root) / rel


def create_worktree(repo_root: str, item_id: str, config: dict) -> tuple[Path | None, str]:
    """Create ``<root>/<item-id>`` on new branch ``fettle/<item-id>``."""
    if not _ID_RE.match(item_id):
        return None, f"invalid item id '{item_id}' — use kebab-case (a-z, 0-9, hyphens)"
    path = worktrees_root(repo_root, config) / item_id
    if path.exists():
        return None, f"worktree path already exists: {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    _, err = _git(["worktree", "add", str(path), "-b", f"fettle/{item_id}"], repo_root)
    if err:
        return None, err
    return path, ""


def list_worktrees(repo_root: str, config: dict) -> tuple[list[dict], str]:
    """All worktrees of the repo, fettle-managed ones annotated with item/dirty."""
    out, err = _git(["worktree", "list", "--porcelain"], repo_root)
    if err:
        return [], err
    managed_root = worktrees_root(repo_root, config).resolve()
    rows: list[dict] = []
    current: dict = {}
    for line in [*out.splitlines(), ""]:
        if not line.strip():
            if current.get("path"):
                rows.append(current)
            current = {}
            continue
        if line.startswith("worktree "):
            current["path"] = line[len("worktree "):]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):].removeprefix("refs/heads/")
        elif line == "bare":
            current["bare"] = True
    for row in rows:
        p = Path(row["path"]).resolve()
        managed = managed_root in p.parents
        row["managed"] = managed
        row["item"] = p.name if managed else ""
        if managed:
            status_out, status_err = _git(["status", "--porcelain"], str(p))
            row["dirty"] = bool(status_out.strip()) if not status_err else None
    return rows, ""


def remove_worktree(repo_root: str, item_id: str, config: dict,
                    force: bool = False) -> str:
    """Remove a managed worktree. Refuses when dirty unless force. Returns error ('' = ok)."""
    path = worktrees_root(repo_root, config) / item_id
    if not path.exists():
        return f"no worktree at {path}"
    status_out, status_err = _git(["status", "--porcelain"], str(path))
    if status_err:
        return f"cannot determine worktree state: {status_err}"
    if status_out.strip() and not force:
        return (f"worktree {item_id} has uncommitted changes — commit or stash them, "
                f"or pass --force to discard")
    args = ["worktree", "remove", str(path)]
    if force:
        args.append("--force")
    _, err = _git(args, repo_root)
    if err:
        return err
    return ""
