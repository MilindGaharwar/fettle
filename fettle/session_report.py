"""Child completion contract + orchestrator brief (v1.6 slice C).

At Stop, a session writes a small structured completion report to
``.fettle/reports/<session>.json`` — what was edited, what was claimed,
the last verify/CI stamps, planned-vs-done. A synergizer/integrator
merges structured reports instead of doing transcript archaeology.

D-C1: best-effort — never blocks, write failures are silent (the trace
already warns once on unwritable state). Read-only apart from that one
file.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

REPORTS_RELPATH = ".fettle/reports"

_MAX_FILES = 50


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _edited_files(session_id: str | None) -> list[str]:
    if not session_id:
        return []
    from fettle.config import state_dir
    edits_path = state_dir(session_id) / "edits.jsonl"
    if not edits_path.is_file():
        return []
    files: list[str] = []
    seen: set[str] = set()
    try:
        for line in edits_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            f = entry.get("file") or entry.get("path") or ""
            if f and f not in seen:
                seen.add(f)
                files.append(f)
    except OSError:
        return []
    return files


def _held_claims(cwd: str, session_id: str | None) -> list[str]:
    if not session_id:
        return []
    from fettle.work_items import load_claims
    try:
        claims = load_claims(cwd)
    except (OSError, json.JSONDecodeError):
        return []
    return sorted(item for item, c in claims.items()
                  if c.get("session_id") == session_id)


def compute_report(cwd: str, session_id: str | None) -> dict:
    """The completion report — every field tolerant of missing evidence."""
    from fettle.session_plan import active_plan

    root = Path(cwd)
    plan = active_plan(root, max_age_hours=24.0)
    verify = _read_json(root / ".fettle" / "verify.json")
    ci = _read_json(root / ".fettle" / "ci-status.json")
    files = _edited_files(session_id)
    return {
        "schema": 1,
        "session_id": session_id or "",
        "parent_session_id": os.environ.get("FETTLE_PARENT_SESSION", ""),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "repo": root.name,
        "files_edited": files[:_MAX_FILES],
        "files_edited_count": len(files),
        "claims_held": _held_claims(cwd, session_id),
        "plan": ({"title": plan["title"], "done": plan["done"],
                  "total": plan["total"]} if plan else None),
        "verify": verify,
        "ci": ci,
    }


def write_report(cwd: str, session_id: str | None) -> Path | None:
    """Write the report; None on any failure (D-C1: silent best-effort)."""
    report = compute_report(cwd, session_id)
    reports_dir = Path(cwd) / REPORTS_RELPATH
    safe = "".join(c for c in (session_id or "unknown")
                   if c.isalnum() or c in "-_") or "unknown"
    path = reports_dir / f"{safe}.json"
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return None
    return path


def load_reports(cwd: str) -> list[dict]:
    """All completion reports, newest first."""
    reports_dir = Path(cwd) / REPORTS_RELPATH
    if not reports_dir.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(reports_dir.glob("*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True):
        data = _read_json(path)
        if data:
            out.append(data)
    return out


def run_check(ctx):
    """Stop hook — record the completion report. Never blocks (D-C1)."""
    from fettle.dispatcher_types import CheckResult

    cfg = ctx.config.get("gates", {}).get("session_report", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()
    write_report(str(ctx.cwd), ctx.session_id)
    return CheckResult.allow()
