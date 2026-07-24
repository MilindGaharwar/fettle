#!/usr/bin/env python3
"""WP-108 — Lean Debt Report.

Greps for `fettle:lean:` markers across the project, parses what/trigger,
and reports summary. Used by /fettle:lean-debt command.

Usage: python lean_debt.py [cwd]
"""

import os
import re
import sys

MARKER_RE = re.compile(r"fettle:lean:\s*(.+)")
TRIGGER_RE = re.compile(r",\s*upgrade when:\s*(.+)", re.IGNORECASE)

EXCLUDED_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".claude",
}

IMPL_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go",
    ".rb", ".java", ".kt", ".swift", ".c", ".cpp", ".h",
    ".sh", ".bash", ".zsh",
}


def _should_skip_dir(name: str) -> bool:
    return name in EXCLUDED_DIRS or name.startswith(".")


def _scan_file(path: str, relative: str) -> list[dict]:
    """Scan a file for fettle:lean: markers."""
    markers = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                m = MARKER_RE.search(line)
                if not m:
                    continue
                content = m.group(1).strip()
                trigger_match = TRIGGER_RE.search(content)
                if trigger_match:
                    what = content[:trigger_match.start()].strip().rstrip(",")
                    trigger = trigger_match.group(1).strip()
                else:
                    what = content
                    trigger = None
                markers.append({
                    "file": relative,
                    "line": i,
                    "what": what,
                    "trigger": trigger,
                })
    except OSError:
        pass
    return markers


def _walk_project(cwd: str) -> list[dict]:
    """Walk project tree and collect all lean markers."""
    all_markers = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if not _should_skip_dir(d)]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in IMPL_EXTENSIONS:
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, cwd)
            all_markers.extend(_scan_file(full, rel))
    return all_markers


def main() -> None:
    cwd = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    markers = _walk_project(cwd)

    if not markers:
        print("No fettle:lean: markers found.")
        sys.exit(0)

    no_trigger = [m for m in markers if m["trigger"] is None]

    for m in markers:
        trigger_str = f" upgrade: {m['trigger']}." if m["trigger"] else " [NO-TRIGGER]"
        print(f"{m['file']}:{m['line']} — {m['what']}.{trigger_str}")

    print()
    print(f"{len(markers)} markers, {len(no_trigger)} with no trigger.")
    sys.exit(0)


if __name__ == "__main__":
    main()
