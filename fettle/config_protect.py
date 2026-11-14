#!/usr/bin/env python3
"""WP-109 — Config Protection Gate.

PreToolUse(Write|Edit) hook that warns/blocks when agent modifies linter/formatter
config files instead of fixing the code.

Fail-open on all errors. Never crashes the session.
"""

import fnmatch
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)

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
    from fettle.hook_cli import run_main

    run_main(run_check)


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from fettle.dispatcher_types import CheckResult

    target = ctx.target_path
    if target is None:
        return CheckResult.allow()
    file_path = str(target)

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
