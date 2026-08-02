"""Session plans — lightweight per-session checklists in .fettle/plans/.

v1.6 slice A (design: docs/engagement/14-v16-reliable-sessions.md).

A session plan is created before work starts (`fettle plan start`),
ticked as work proceeds (`fettle plan check`), and reconciled at Stop by
the worklog gate ("planned N, done M"). Deliberately lighter than
plan_validator's 5-phase WP format (D-A2): a frontmatter marker plus at
least one checkbox. Plans live in the state dir, not agent-private
memory, so every agent brand — and a resumed or compacted session —
reads the same artifact (D-A3).
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

PLANS_RELPATH = ".fettle/plans"

_CHECKBOX_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s+(.+)$")
_MARKER = "fettle-plan"


def _plans_dir(cwd: Path) -> Path:
    return Path(cwd) / PLANS_RELPATH


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40] or "plan"


def create_plan(
    cwd: Path,
    title: str,
    items: list[str],
    session_id: str | None = None,
) -> Path:
    """Write a new session plan; returns its path.

    Raises ValueError when there are no items — a plan without steps
    can never become active (active_plan requires >= 1 checkbox).
    """
    if not items:
        raise ValueError("a session plan needs at least one step (--item)")
    plans_dir = _plans_dir(cwd)
    plans_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now().strftime('%Y%m%d')}-{_slugify(title)}"
    path = plans_dir / f"{stem}.md"
    n = 2
    while path.exists():
        path = plans_dir / f"{stem}-{n}.md"
        n += 1
    lines = [
        "---",
        f"{_MARKER}: true",
        f"created: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}",
        f"session: {session_id or ''}",
        f"title: {title}",
        "---",
        "",
        f"# {title}",
        "",
    ]
    lines += [f"- [ ] {item}" for item in items]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def parse_plan(path: Path) -> dict | None:
    """Parse a session plan file; None when it isn't one (no marker)."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not content.startswith("---"):
        return None
    frontmatter = content.split("---", 2)[1]
    if _MARKER not in frontmatter:
        return None
    title = path.stem
    session = ""
    for line in content.splitlines():
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("session:"):
            session = line.split(":", 1)[1].strip()
    items: list[dict] = []
    for line in content.splitlines():
        m = _CHECKBOX_RE.match(line)
        if m:
            items.append({"done": m.group(1) in ("x", "X"), "text": m.group(2).strip()})
    done = sum(1 for i in items if i["done"])
    return {
        "path": str(path),
        "title": title,
        "session": session,
        "items": items,
        "done": done,
        "total": len(items),
    }


def find_plans(cwd: Path) -> list[Path]:
    """All session plan files, newest mtime first."""
    plans_dir = _plans_dir(cwd)
    if not plans_dir.is_dir():
        return []
    return sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)


def active_plan(cwd: Path, max_age_hours: float = 24.0) -> dict | None:
    """Newest parseable plan with >= 1 checkbox, touched within the window.

    The mtime window nudges plans to stay live: ticking an item
    (check_item) refreshes it.
    """
    cutoff = time.time() - max_age_hours * 3600
    for path in find_plans(cwd):
        try:
            if path.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        plan = parse_plan(path)
        if plan and plan["total"] >= 1:
            return plan
    return None


def check_item(cwd: Path, text: str) -> tuple[bool, str]:
    """Tick the first unchecked item containing `text` (case-insensitive)
    in the newest plan. Returns (ok, item-text-or-reason)."""
    plans = find_plans(cwd)
    if not plans:
        return False, "no session plan found (fettle plan start)"
    path = plans[0]
    plan = parse_plan(path)
    if not plan:
        return False, f"not a session plan: {path.name}"
    needle = text.lower()
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = _CHECKBOX_RE.match(line)
        if m and m.group(1) == " " and needle in m.group(2).lower():
            lines[i] = line.replace("- [ ]", "- [x]", 1)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True, m.group(2).strip()
    return False, f"no unchecked item matches {text!r} in {path.name}"


def render_status(plan: dict | None) -> str:
    if plan is None:
        return "No active session plan. Start one: fettle plan start --title <t> --item <step>"
    out = [f"Plan: {plan['title']} ({plan['done']}/{plan['total']} done) — {plan['path']}"]
    for item in plan["items"]:
        out.append(f"  [{'x' if item['done'] else ' '}] {item['text']}")
    return "\n".join(out)
