#!/usr/bin/env python3
"""WP-109 — Config Protection Gate.

PreToolUse(Write|Edit) hook that warns/blocks when agent modifies linter/formatter
config files instead of fixing the code.

Fail-open on all errors. Never crashes the session.
"""

import fnmatch
import os
import re
import shlex
import sys
from pathlib import Path

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

CONTROL_PLANE_PATHS = frozenset({
    ".fettle.toml",
    ".fettle-ignore",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".codex/hooks.json",
    ".gemini/settings.json",
    ".opencode/plugins/fettle.ts",
    ".opencode/plugin/fettle.ts",
})
_SHELL_WRITERS = frozenset({"rm", "mv", "cp", "truncate", "chmod", "tee"})

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


def _normalise(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def _control_plane_name(path: Path, root: Path) -> str | None:
    resolved = Path(_normalise(path))
    root_resolved = Path(_normalise(root))
    try:
        relative = resolved.relative_to(root_resolved).as_posix().casefold()
    except ValueError:
        relative = ""
    if relative in {item.casefold() for item in CONTROL_PLANE_PATHS}:
        return path.name
    if relative == ".fettle" or relative.startswith(".fettle/"):
        return path.name
    if path.name.casefold() == ".fettle.toml" and root_resolved in resolved.parents:
        return path.name

    from fettle.config import state_root

    configured_state_root = state_root()
    try:
        resolved.relative_to(Path(_normalise(configured_state_root)))
    except ValueError:
        return None
    return path.name


def _shell_write_targets(command: str, root: Path) -> list[Path]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []
    targets: list[str] = []
    for index, token in enumerate(tokens):
        if token in {">", ">>"} and index + 1 < len(tokens):
            targets.append(tokens[index + 1])
        command_name = Path(token).name
        if command_name in _SHELL_WRITERS:
            for value in tokens[index + 1:]:
                if value in {";", "&&", "||", "|", "&"}:
                    break
                if not value.startswith("-"):
                    targets.append(value)
        if command_name == "sed" and "-i" in tokens[index + 1:]:
            for value in tokens[index + 1:]:
                if value in {";", "&&", "||", "|", "&"}:
                    break
                if not value.startswith("-") and not value.startswith("s/"):
                    targets.append(value)
    return [Path(value) if Path(value).is_absolute() else root / value for value in targets]


def _policy_result(name: str, mode: str):
    from fettle.dispatcher_types import CheckResult

    message = (
        f"Fettle policy modification blocked: {name}. "
        "Policy is changed by the repository owner outside the agent session."
    )
    if mode == "enforce":
        return CheckResult.block(
            message,
            hook_specific_output={
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "additionalContext": message,
            },
        )
    return CheckResult.advisory(
        message,
        hook_specific_output={
            "hookEventName": "PreToolUse",
            "additionalContext": message,
        },
    )


def main() -> None:
    from fettle.hook_cli import run_main

    run_main(run_check)


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from fettle.dispatcher_types import CheckResult

    gate_cfg = ctx.config.get("gates", {}).get("config_protect", {})
    if not gate_cfg.get("enabled", True):
        return CheckResult.allow()

    mode = gate_cfg.get("mode", "advisory")
    extra_patterns = gate_cfg.get("extra_patterns", [])
    allow_patterns = gate_cfg.get("allow_patterns", [])

    targets: list[Path] = []
    if ctx.target_path is not None:
        targets.append(ctx.target_path)
    if ctx.tool_name == "Bash":
        targets.extend(_shell_write_targets(str(ctx.tool_input.get("command", "")), ctx.cwd))
    if not targets:
        return CheckResult.allow()
    for target in targets:
        protected_name = _control_plane_name(target, ctx.cwd)
        if protected_name:
            return _policy_result(protected_name, mode)

    target = targets[0]
    file_path = str(target)

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

    if mode == "enforce":
        return CheckResult.block(
            f"Config modification blocked: `{basename}`.",
            hook_specific_output={
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "additionalContext": (
                    f"Config modification blocked: `{basename}`. "
                    "Fix the code instead of weakening the linter."
                ),
            },
        )

    return CheckResult.advisory(
        f"Fix the code, don't weaken the linter (`{basename}`).",
        hook_specific_output={
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"Fix the code, don't weaken the linter (`{basename}`). "
                "If you must change this config, ask the repository owner first."
            ),
        },
    )


if __name__ == "__main__":
    main()
