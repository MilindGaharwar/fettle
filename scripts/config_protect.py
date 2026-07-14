#!/usr/bin/env python3
"""WP-109 — Config Protection Gate.

PreToolUse(Write|Edit) hook that warns/blocks when agent modifies linter/formatter
config files instead of fixing the code.

Fail-open on all errors. Never crashes the session.
"""

import fnmatch
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config  # noqa: E402

PROTECTED_PATTERNS = [
    ".eslintrc*",
    "eslint.config.*",
    ".prettierrc*",
    "prettier.config.*",
    "biome.json",
    "biome.jsonc",
    ".ruff.toml",
    "ruff.toml",
    ".shellcheckrc",
    "rustfmt.toml",
    "clippy.toml",
    ".editorconfig",
    "tsconfig.json",
]

PYPROJECT_TOOL_SECTIONS = re.compile(
    r"\[tool\.(ruff|mypy|pyright|pylint|isort|black|flake8)\b"
)


def _is_protected(basename: str, extra_patterns: list[str]) -> bool:
    all_patterns = PROTECTED_PATTERNS + extra_patterns
    return any(fnmatch.fnmatch(basename, pat) for pat in all_patterns)


def _is_allowed(basename: str, allow_patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(basename, pat) for pat in allow_patterns)


def _pyproject_has_tool_sections(file_path: str) -> bool:
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        return bool(PYPROJECT_TOOL_SECTIONS.search(content))
    except OSError:
        return False


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    cwd = data.get("cwd", ".")
    cfg = load_config(cwd)

    gate_cfg = cfg.get("gates", {}).get("config_protect", {})
    if not gate_cfg.get("enabled", True):
        sys.exit(0)

    mode = gate_cfg.get("mode", "advisory")
    extra_patterns = gate_cfg.get("extra_patterns", [])
    allow_patterns = gate_cfg.get("allow_patterns", [])

    basename = os.path.basename(file_path)

    # Check allow list first
    if _is_allowed(basename, allow_patterns):
        sys.exit(0)

    # Check if this is a protected file
    is_pyproject = basename == "pyproject.toml"
    if not _is_protected(basename, extra_patterns) and not is_pyproject:
        sys.exit(0)

    # For pyproject.toml, only protect if it has tool sections
    if is_pyproject:
        if not os.path.isfile(file_path):
            sys.exit(0)
        if not _pyproject_has_tool_sections(file_path):
            sys.exit(0)

    # Allow creation (file doesn't exist yet)
    if not os.path.isfile(file_path):
        sys.exit(0)

    # File exists and is protected → warn or block
    if mode == "enforce":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "additionalContext": (
                    f"Config modification blocked: `{basename}`. "
                    f"Fix the code, don't weaken the linter. "
                    f'Disable: [gates.config_protect].mode = "advisory"'
                ),
            }
        }
        print(json.dumps(output))
        sys.exit(2)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"Fix the code, don't weaken the linter (`{basename}`). "
                f"If you must change this config, ask the user first. "
                f"Disable: [gates.config_protect].enabled = false"
            ),
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from dispatcher_types import CheckResult

    file_path = ctx.tool_input.get("file_path", "")
    if not file_path:
        return CheckResult.allow()

    gate_cfg = ctx.config.get("gates", {}).get("config_protect", {})
    if not gate_cfg.get("enabled", True):
        return CheckResult.allow()

    mode = gate_cfg.get("mode", "advisory")
    extra_patterns = gate_cfg.get("extra_patterns", [])
    allow_patterns = gate_cfg.get("allow_patterns", [])

    basename = os.path.basename(file_path)

    if _is_allowed(basename, allow_patterns):
        return CheckResult.allow()

    is_pyproject = basename == "pyproject.toml"
    if not _is_protected(basename, extra_patterns) and not is_pyproject:
        return CheckResult.allow()

    if is_pyproject:
        if not os.path.isfile(file_path):
            return CheckResult.allow()
        if not _pyproject_has_tool_sections(file_path):
            return CheckResult.allow()

    if not os.path.isfile(file_path):
        return CheckResult.allow()

    if mode == "enforce":
        return CheckResult.block(
            f"Config modification blocked: `{basename}`.",
            hook_specific_output={
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "additionalContext": (
                    f"Config modification blocked: `{basename}`. "
                    f"Fix the code, don't weaken the linter. "
                    f'Disable: [gates.config_protect].mode = "advisory"'
                ),
            },
        )

    return CheckResult.advisory(
        f"Fix the code, don't weaken the linter (`{basename}`).",
        hook_specific_output={
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"Fix the code, don't weaken the linter (`{basename}`). "
                f"If you must change this config, ask the user first. "
                f"Disable: [gates.config_protect].enabled = false"
            ),
        },
    )


if __name__ == "__main__":
    main()
