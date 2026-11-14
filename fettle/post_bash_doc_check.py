#!/usr/bin/env python3
"""Fettle PostToolUse hook (Bash) — blocks git push if no documentation was updated.

Fires on every Bash tool use. When a `git push` command is detected:
  1. Reads the edit tracking file to find implementation files edited this session.
  2. Checks whether any .md file was edited after the most recent implementation edit.
  3. If no doc update preceded the push, blocks with a CRITICAL directive.

Opt-in: enable with `[gates.docs] enabled = true` in .fettle.toml (default off).
`mode = "advisory"` always exits 0 but emits warning JSON; soft/enforce exit 2
to block on a missing doc update.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.paths import classify_file  # noqa: E402

_GIT_PUSH_RE = re.compile(r"\bgit\s+push\b")

_DOC_EXTENSIONS = {".md", ".rst", ".txt"}


def _is_impl(path: str) -> bool:
    return classify_file(path) == "implementation"


def _is_doc(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in _DOC_EXTENSIONS


def main() -> None:
    from fettle.hook_cli import run_main

    run_main(run_check)


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from fettle.dispatcher_types import CheckResult

    command = ctx.tool_input.get("command", "")
    if not command or not _GIT_PUSH_RE.search(command):
        return CheckResult.allow()

    if not ctx.config.get("gates", {}).get("docs", {}).get("enabled", False):
        return CheckResult.allow()
    mode = str(ctx.config.get("gates", {}).get("docs", {}).get("mode", "advisory"))

    from fettle.edit_journal import entries as journal_entries

    journal = journal_entries(ctx.session_id)
    if journal.malformed_lines:
        return CheckResult.unknown(
            "Documentation edit evidence is malformed.",
            action="Repair the session edit journal and retry the push.",
        )
    entries = journal.entries
    if not entries:
        return CheckResult.allow()

    impl_edits = [e for e in entries if _is_impl(e.get("file", ""))]
    if not impl_edits:
        return CheckResult.allow()

    latest_impl_ts = max(e.get("ts", 0.0) for e in impl_edits)
    doc_edits_after = [
        e for e in entries
        if _is_doc(e.get("file", "")) and e.get("ts", 0.0) >= latest_impl_ts
    ]

    if doc_edits_after:
        return CheckResult.allow()

    impl_files = sorted({e["file"] for e in impl_edits})
    file_list = "\n".join(f"  - {f}" for f in impl_files[:10])
    if len(impl_files) > 10:
        file_list += f"\n  ... and {len(impl_files) - 10} more"

    reason = (
        "CRITICAL SYSTEM DIRECTIVE — DO NOT IGNORE\n\n"
        "git push blocked: implementation files were edited this session but no "
        "documentation (.md) was updated before the push.\n\n"
        f"Implementation files edited:\n{file_list}"
    )
    metadata = (
        f"impl_files_edited={len(impl_files)} "
        f"doc_files_updated=0 latest_impl_ts={latest_impl_ts:.0f}"
    )

    if mode == "advisory":
        return CheckResult.advisory(
            reason,
            hook_specific_output={
                "hookEventName": "PostToolUse",
                "additionalContext": metadata,
            },
        )

    return CheckResult.block(
        reason,
        hook_specific_output={
            "hookEventName": "PostToolUse",
            "additionalContext": metadata,
        },
    )


if __name__ == "__main__":
    try:
        main()
    except (json.JSONDecodeError, OSError, ValueError):
        sys.exit(0)
