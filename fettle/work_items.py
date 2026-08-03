"""Work items + claims — WP5 coordination substrate (Stage 4, S4.3; doc 09).

Adopts the Wayfinder model (04-wp6): **index-vs-store** separation (the
index is one line per item; detail lives in exactly one file) and **claim
semantics** (a worktree session claims an item before edits; unclaimed =
takeable; stale claims — worktree gone — are reclaimable).

Two kinds of state, two homes:
- Work items are *knowledge*, versioned with code: markdown files detected
  by a ``fettle-work-item`` frontmatter key (same philosophy as specs —
  never by filename or location).
- Claims are *runtime coordination state*: ``<git-common-dir>/fettle/
  claims.json``, shared across every worktree of the repo, never committed.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fettle.spec_model import _SKIP_DIRS, _parse_frontmatter
from fettle.worktrees import git_common_dir

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VALID_STATUSES = frozenset({"open", "claimed", "done"})


@dataclass
class WorkItem:
    path: str  # repo-relative
    item_id: str
    status: str
    scope: list[str] = field(default_factory=list)
    spec: str = ""  # optional spec-id link (Pillar 5 → Pillar 1)
    has_resolution: bool = False


def _finding(path: str, line: int, severity: str, message: str, fix: str) -> dict:
    return {
        "file": path, "line": line, "rule": "WORK_ITEM_LINT",
        "severity": severity, "tool": "work_items",
        "message": message, "fix": fix,
    }


def is_work_item_text(text: str) -> bool:
    data, end = _parse_frontmatter(text.splitlines()[:50])
    return end > 0 and "fettle-work-item" in data


def parse_work_item(text: str, path: str = "<item>") -> tuple[WorkItem | None, list[dict]]:
    """Parse one work-item file. Returns (item-or-None, findings)."""
    lines = text.splitlines()
    data, body_start = _parse_frontmatter(lines)
    if body_start == 0 or "fettle-work-item" not in data:
        return None, []
    findings: list[dict] = []

    item_id = str(data.get("id", ""))
    if not item_id:
        findings.append(_finding(path, 1, "ERROR", "missing 'id' in frontmatter",
                                 "add 'id: <kebab-case-id>' to the frontmatter"))
    elif not _ID_RE.match(item_id):
        findings.append(_finding(path, 1, "ERROR", f"invalid id '{item_id}'",
                                 "use kebab-case: lowercase letters, digits, hyphens"))

    status = str(data.get("status", ""))
    if status not in VALID_STATUSES:
        findings.append(_finding(
            path, 1, "ERROR", f"invalid status '{status}'",
            f"set status to one of: {', '.join(sorted(VALID_STATUSES))}"))

    scope = data.get("scope", [])
    if not isinstance(scope, list):
        scope = [str(scope)]

    has_resolution = any(re.match(r"^##\s+Resolution\b", ln) for ln in lines[body_start:])
    if status == "done" and not has_resolution:
        findings.append(_finding(
            path, 1, "WARNING", f"item '{item_id}' is done but records no resolution",
            "add a '## Resolution' section saying how it was resolved"))

    if any(f["severity"] == "ERROR" for f in findings):
        return None, findings
    return WorkItem(path=path, item_id=item_id, status=status, scope=list(scope),
                    spec=str(data.get("spec", "")), has_resolution=has_resolution), findings


def discover_work_items(root: str) -> list[tuple[WorkItem | None, list[dict]]]:
    """Find every work item in the repo (frontmatter-key detection)."""
    results = []
    root_path = Path(root)
    for md in sorted(root_path.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in md.parts):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not is_work_item_text(text):
            continue
        rel = str(md.relative_to(root_path))
        results.append(parse_work_item(text, rel))
    return results


def lint_work_items(root: str) -> list[dict]:
    """Per-file findings plus repo-wide duplicate-id detection."""
    findings: list[dict] = []
    seen: dict[str, str] = {}
    for item, file_findings in discover_work_items(root):
        findings.extend(file_findings)
        if item is None:
            continue
        if item.item_id in seen:
            findings.append(_finding(
                item.path, 1, "ERROR",
                f"duplicate item id '{item.item_id}' (also in {seen[item.item_id]})",
                "give each work item a unique id"))
        else:
            seen[item.item_id] = item.path
    return findings


# ---------------------------------------------------------------- claims

def _claims_path(root: str) -> Path | None:
    common = git_common_dir(root)
    if common is None:
        return None
    return common / "fettle" / "claims.json"


def load_claims(root: str) -> dict[str, dict]:
    """item_id → {session_id, worktree, claimed_at}. Corrupt file → {} + refetch on write."""
    path = _claims_path(root)
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_claims(root: str, claims: dict) -> str:
    path = _claims_path(root)
    if path is None:
        return "not a git repository — claims need a shared .git dir"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(claims, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as e:
        return f"cannot write claims file: {e}"
    return ""


@contextmanager
def _claims_lock(root: str):
    """Exclusive advisory lock serializing claim read-modify-write cycles.

    Without it, two sessions claiming concurrently both read the same
    snapshot and the second write silently drops the first claim — the
    exact split-brain the claims file exists to prevent (audit Opus C3).
    Yields an error string ('' on success) so callers surface lock
    failures the same way as write failures.
    """
    path = _claims_path(root)
    if path is None:
        yield "not a git repository — claims need a shared .git dir"
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path.with_name("claims.lock"), "w", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield ""
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except OSError as e:
        yield f"cannot lock claims file: {e}"


def claim_item(root: str, item_id: str, session_id: str, worktree: str) -> str:
    """Claim an item. Refuses when a *live* other session holds it.

    Live = the claiming worktree still exists. Stale claims are silently
    reclaimed (unclaimed = takeable — Wayfinder semantics).
    """
    with _claims_lock(root) as lock_err:
        if lock_err:
            return lock_err
        claims = load_claims(root)
        existing = claims.get(item_id)
        if existing:
            same_worktree = str(Path(existing.get("worktree", ""))) == str(Path(worktree))
            still_live = Path(existing.get("worktree", "/nonexistent")).exists()
            if still_live and not same_worktree:
                return (f"item '{item_id}' is claimed by session "
                        f"{existing.get('session_id', '?')} in {existing.get('worktree', '?')} — "
                        f"release it there or pick another item")
        claims[item_id] = {
            "session_id": session_id,
            "worktree": str(worktree),
            "claimed_at": int(time.time()),
        }
        return _save_claims(root, claims)


def release_item(root: str, item_id: str) -> str:
    with _claims_lock(root) as lock_err:
        if lock_err:
            return lock_err
        claims = load_claims(root)
        if item_id not in claims:
            return f"item '{item_id}' is not claimed"
        del claims[item_id]
        return _save_claims(root, claims)


def claim_for_worktree(root: str, worktree: str) -> str:
    """The item id claimed by this worktree, or ''."""
    for item_id, rec in load_claims(root).items():
        if str(Path(rec.get("worktree", ""))) == str(Path(worktree)):
            return item_id
    return ""
