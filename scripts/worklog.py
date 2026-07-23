"""Fettle Worklog — daily work journal enforcement.

Stop hook check that ensures a worklog entry exists for today before
allowing work to be declared complete. Also provides CLI for viewing
and creating entries.

Worklog format (one file per day):
  .fettle/worklog/YYYY-MM-DD.md

Minimum viable entry (enforced):
  - Date header
  - At least one "## Completed" or "## Done" item
  - At least one line of content (not just headers)

Best-practice entry (advisory):
  - Completed items (what shipped)
  - Decisions made (and why)
  - Blockers/risks identified
  - Next actions (carries forward)
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _worklog_dir(cwd: str) -> Path:
    return Path(cwd) / ".fettle" / "worklog"


def _today_file(cwd: str) -> Path:
    return _worklog_dir(cwd) / f"{_today()}.md"


def _has_valid_entry(worklog_path: Path) -> tuple[bool, str]:
    """Check if today's worklog has minimum viable content.

    Returns (valid, reason).
    """
    if not worklog_path.is_file():
        return False, "no worklog entry for today"

    try:
        content = worklog_path.read_text(encoding="utf-8")
    except OSError:
        return False, "worklog file unreadable"

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) < 3:
        return False, "worklog entry too short (need at least date + section + 1 item)"

    completed_idx = -1
    for i, line in enumerate(lines):
        if (line.lower().startswith("## completed") or
                line.lower().startswith("## done") or
                line.lower().startswith("## shipped") or
                line.lower().startswith("## accomplished")):
            completed_idx = i
            break

    if completed_idx < 0:
        return False, "worklog missing '## Completed' section"

    completed_items = []
    for line in lines[completed_idx + 1:]:
        if line.startswith("## "):
            break
        if line.startswith("- ") and len(line) > 2:
            completed_items.append(line)

    if not completed_items:
        return False, "worklog '## Completed' section has no items (add at least one '- item')"

    return True, "valid"


def create_template(cwd: str) -> str:
    """Create today's worklog template. Returns the file path."""
    worklog_dir = _worklog_dir(cwd)
    worklog_dir.mkdir(parents=True, exist_ok=True)
    filepath = _today_file(cwd)

    if filepath.exists():
        return str(filepath)

    today = _today()
    template = (
        "# Worklog: " + today + "\n\n"
        "## Completed\n-\n\n"
        "## Decisions\n-\n\n"
        "## Blockers / Risks\n- None\n\n"
        "## Next Actions\n-\n"
    )
    filepath.write_text(template, encoding="utf-8")
    return str(filepath)


def run_check(ctx):
    """Stop hook — advisory if no worklog entry for today."""
    from dispatcher_types import CheckResult

    cfg = ctx.config.get("gates", {}).get("worklog", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    worklog_path = _today_file(cwd)
    valid, reason = _has_valid_entry(worklog_path)

    if valid:
        return CheckResult.allow()

    mode = cfg.get("mode", "advisory")
    expected_path = os.path.relpath(str(worklog_path), cwd)
    msg = "Worklog: " + reason + ". Create entry at " + expected_path + " (use /fettle:worklog)."

    if mode == "enforce":
        return CheckResult.block(msg, hook_specific_output={
            "hookEventName": ctx.input.hook_event_name,
            "additionalContext": msg,
        })
    return CheckResult.advisory(msg, hook_specific_output={
        "hookEventName": ctx.input.hook_event_name,
        "additionalContext": msg,
    })


def cmd_worklog_view(cwd: str, days: int = 7) -> str:
    """View recent worklog entries."""
    worklog_dir = _worklog_dir(cwd)
    if not worklog_dir.is_dir():
        return "No worklog directory found. Run /fettle:worklog to create one."

    entries = sorted(worklog_dir.glob("*.md"), reverse=True)[:days]
    if not entries:
        return "No worklog entries found."

    output = []
    for entry in entries:
        output.append(f"### {entry.stem}")
        content = entry.read_text(encoding="utf-8")
        completed = []
        in_completed = False
        for line in content.splitlines():
            if line.strip().lower().startswith("## completed") or \
               line.strip().lower().startswith("## done"):
                in_completed = True
                continue
            elif line.strip().startswith("## "):
                in_completed = False
            elif in_completed and line.strip().startswith("- ") and line.strip() != "- ":
                completed.append(line.strip())
        if completed:
            output.extend(completed)
        else:
            output.append("  (no items)")
        output.append("")

    return "\n".join(output)
