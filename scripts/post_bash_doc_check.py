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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config, state_dir  # noqa: E402

_GIT_PUSH_RE = re.compile(r"\bgit\s+push\b")

_IMPL_EXTENSIONS = {".py", ".rs", ".sh", ".js", ".ts"}
_DOC_EXTENSIONS = {".md", ".rst", ".txt"}
_TEST_PATH_FRAGMENTS = ("/tests/", "/test/", "test_")


def _is_impl(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext not in _IMPL_EXTENSIONS:
        return False
    return not any(frag in path for frag in _TEST_PATH_FRAGMENTS)


def _is_doc(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in _DOC_EXTENSIONS


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    command: str = data.get("tool_input", {}).get("command", "")
    if not command or not _GIT_PUSH_RE.search(command):
        sys.exit(0)

    cfg = load_config(data.get("cwd"))
    if not cfg["gates"]["docs"]["enabled"]:
        sys.exit(0)
    mode: str = str(cfg["gates"]["docs"]["mode"])

    tracking_path: str = os.environ.get(
        "FETTLE_EDIT_TRACKING", str(state_dir(data.get("session_id", "unknown")) / "edits.jsonl")
    )

    try:
        with open(tracking_path) as fh:
            entries: list[dict] = [json.loads(line) for line in fh if line.strip()]
    except (FileNotFoundError, json.JSONDecodeError):
        sys.exit(0)

    if not entries:
        sys.exit(0)

    impl_edits = [e for e in entries if _is_impl(e.get("file", ""))]
    if not impl_edits:
        sys.exit(0)

    latest_impl_ts: float = max(e.get("ts", 0.0) for e in impl_edits)

    doc_edits_after_impl = [
        e for e in entries
        if _is_doc(e.get("file", "")) and e.get("ts", 0.0) >= latest_impl_ts
    ]

    if doc_edits_after_impl:
        sys.exit(0)

    impl_files = sorted({e["file"] for e in impl_edits})
    file_list = "\n".join(f"  - {f}" for f in impl_files[:10])
    if len(impl_files) > 10:
        file_list += f"\n  ... and {len(impl_files) - 10} more"

    reason = (
        "CRITICAL SYSTEM DIRECTIVE — DO NOT IGNORE\n\n"
        "git push blocked: implementation files were edited this session but no "
        "documentation (.md) was updated before the push.\n\n"
        f"Implementation files edited:\n{file_list}\n\n"
        "MANDATORY before pushing:\n"
        "  1. Update README to reflect all new features, changed behavior, and new APIs.\n"
        "  2. Update any other .md files affected by the changes.\n"
        "  3. Then re-run git push.\n\n"
        "Incident: 2026-05-01 — Fettle silent-failure hardening (3 WPs, 9 new "
        "rules/hooks/validators) pushed without updating README. README listed stale "
        "rule names, was missing two new semgrep rules, and had no Enforcement Hooks "
        "section. Required a separate corrective commit."
    )

    output = {
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "additionalContext": (
                f"impl_files_edited={len(impl_files)} "
                f"doc_files_updated=0 "
                f"latest_impl_ts={latest_impl_ts:.0f}"
            )
        },
    }

    if mode == "advisory":
        output["decision"] = "continue"
        output["reason"] = "[ADVISORY] " + reason
        print(json.dumps(output))
        sys.exit(0)

    print(json.dumps(output))
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except (json.JSONDecodeError, OSError, ValueError):
        sys.exit(0)
