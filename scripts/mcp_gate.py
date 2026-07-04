#!/usr/bin/env python3
"""Fettle PreToolUse hook — blocks direct MCP package installation/execution."""

import json
import re
import sys
from typing import NoReturn


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_name: str = data.get("tool_name", "")
    tool_input: dict[str, str] = data.get("tool_input", {})

    if tool_name == "Bash":
        command: str = tool_input.get("command", "")

        if re.search(r'(npm|yarn|pip|pip3|pnpm|pipx)\s+(install|i|update|up|upgrade|add)\s+.*mcp', command, re.IGNORECASE):
            _block()

        if re.search(r'(npx|uvx|pipx|dlx)\s+.*mcp', command, re.IGNORECASE):
            _block()

    sys.exit(0)


def _block() -> NoReturn:
    output: dict[str, object] = {
        "decision": "block",
        "reason": "Fettle MCP Gate: Direct installation, execution, or update of MCP packages via CLI is blocked. You must execute the Zero-Trust MCP Validation Protocol.",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Fettle policy violation: MCP packages must be audited via Zero-Trust Validation Protocol before execution or upgrade."
        }
    }
    print(json.dumps(output))
    sys.exit(2)


if __name__ == "__main__":
    main()
