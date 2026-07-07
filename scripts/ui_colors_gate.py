#!/usr/bin/env python3
"""Fettle UI colors gate — warns on hardcoded hex colors outside the palette.

Off by default. Enable with:
    [gates.ui_colors]
    enabled = true
    allowed_hex = ["#1a1a1a", "#ffffff", "#3b82f6"]

When enabled, Post-edit checks for hardcoded hex color literals that aren't
in the allowed palette.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config
from paths import find_repo_root, relative_to_repo
from result import Finding, Severity, make_pass, make_skipped, make_violation
from trace import log_decision

HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")


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
    gate_cfg = cfg["gates"].get("ui_colors", {})

    if not gate_cfg.get("enabled", False):
        sys.exit(0)

    if not file_path.endswith((".tsx", ".jsx", ".css", ".scss", ".ts", ".js")):
        sys.exit(0)

    content = tool_input.get("content", "") or tool_input.get("new_string", "")
    if not content:
        sys.exit(0)

    allowed_hex = set(h.lower() for h in gate_cfg.get("allowed_hex", []))
    found_colors = HEX_COLOR_RE.findall(content)

    violations = []
    for color in found_colors:
        if color.lower() not in allowed_hex:
            violations.append(color)

    if not violations:
        result = make_pass()
    else:
        repo_root = find_repo_root(cwd)
        rel_path = relative_to_repo(file_path, repo_root) if repo_root else file_path

        findings = [
            Finding(
                tool="ui_colors_gate",
                severity=Severity.WARNING,
                path=rel_path,
                message=f"Hardcoded color {color} not in allowed palette. Use design tokens. Disable: [gates.ui_colors] enabled = false",
            )
            for color in violations[:5]
        ]
        result = make_violation(findings)
        log_decision(
            hook="PostToolUse", status="violation", tool="ui_colors",
            file=rel_path, findings=[f.to_dict() for f in findings],
            session_id=session_id,
        )

    result.emit_and_exit(hook_event="PostToolUse", block=False)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError):
        sys.exit(0)
