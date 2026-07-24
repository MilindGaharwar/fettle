#!/usr/bin/env python3
"""Fettle UX spec gate — blocks frontend edits without a UX spec.

Off by default. Enable with:
    [gates.ux_spec]
    enabled = true

When enabled, Write/Edit to frontend paths (pages/, components/) requires
a matching UX spec file at docs/<feature>.ux-spec.md.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.config import load_config
from fettle.paths import find_repo_root, is_within_repo, relative_to_repo
from fettle.result import Finding, Severity, make_pass, make_violation
from fettle.trace import log_decision


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    cwd = data.get("cwd", ".")
    session_id = data.get("session_id", "unknown")

    cfg = load_config(cwd)
    gate_cfg = cfg["gates"].get("ux_spec", {})

    if not gate_cfg.get("enabled", False):
        sys.exit(0)

    repo_root = find_repo_root(cwd)
    if not repo_root:
        sys.exit(0)

    if not is_within_repo(file_path, repo_root):
        sys.exit(0)

    rel_path = relative_to_repo(file_path, repo_root)

    frontend_paths = gate_cfg.get("frontend_paths", [
        "frontend/src/pages/", "frontend/src/components/",
        "src/pages/", "src/components/",
    ])
    exempt_patterns = gate_cfg.get("exempt", [
        "components/ui/", "utils/", "hooks/", "stores/", "api/",
        "test", ".test.", ".spec.",
    ])

    is_frontend = any(rel_path.startswith(fp) for fp in frontend_paths)
    if not is_frontend:
        sys.exit(0)

    is_exempt = any(pat in rel_path for pat in exempt_patterns)
    if is_exempt:
        sys.exit(0)

    docs_dir = repo_root / "docs"
    has_ux_spec = any(docs_dir.glob("*.ux-spec.md")) if docs_dir.exists() else False

    if has_ux_spec:
        log_decision(hook="PreToolUse", status="pass", tool="ux_spec", file=rel_path, session_id=session_id)
        result = make_pass()
    else:
        log_decision(hook="PreToolUse", status="violation", tool="ux_spec", file=rel_path, session_id=session_id)
        result = make_violation([
            Finding(
                tool="ux_spec_gate",
                severity=Severity.WARNING,
                path=rel_path,
                message="Frontend file edited without UX spec. Create docs/<feature>.ux-spec.md first. Disable: [gates.ux_spec] enabled = false",
            )
        ])

    result.emit_and_exit(hook_event="PreToolUse", block=False)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError):
        sys.exit(0)
