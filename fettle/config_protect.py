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
_SHELL_SEPARATORS = frozenset({";", "&&", "||", "|", "&"})
_READ_ONLY_COMMANDS = frozenset({
    "cat", "head", "tail", "less", "grep", "rg", "wc", "ls", "stat", "diff", "cmp",
    "shasum", "sha256sum", "fettle",
})
_ALLOWED_GIT_SUBCOMMANDS = frozenset({
    "status", "diff", "log", "show", "blame", "ls-files", "add", "commit",
})

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


def _shell_tokens(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return []


def _simple_commands(tokens: list[str]) -> list[list[str]]:
    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _SHELL_SEPARATORS:
            if current:
                commands.append(current)
                current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def _argument_path(value: str, cwd: Path) -> Path:
    candidate = value.split("=", 1)[1] if "=" in value else value
    expanded = os.path.expanduser(os.path.expandvars(candidate))
    path = Path(expanded)
    return path if path.is_absolute() else cwd / path


def _raw_control_plane_name(command: str) -> str | None:
    from fettle.config import state_root

    folded = command.casefold()
    for name in sorted(CONTROL_PLANE_PATHS, key=len, reverse=True):
        if name.casefold() in folded:
            return Path(name).name
    state_spellings = {
        str(state_root()),
        "$XDG_STATE_HOME/fettle",
        "${XDG_STATE_HOME}/fettle",
        "~/.local/state/fettle",
    }
    if any(spelling.casefold() in folded for spelling in state_spellings):
        return "fettle state"
    if re.search(r"(?:^|[\s/])\.fettle(?:[/\s]|$)", command, flags=re.IGNORECASE):
        return ".fettle"
    return None


def _referenced_control_plane(command: list[str], cwd: Path) -> str | None:
    raw_name = _raw_control_plane_name(" ".join(command))
    if raw_name:
        return raw_name
    for token in command:
        if token.startswith("-") and "=" not in token:
            continue
        name = _control_plane_name(_argument_path(token, cwd), cwd)
        if name:
            return name
    return None


def _command_is_allowed(command: list[str]) -> bool:
    executable_index = next(
        (index for index, token in enumerate(command) if "=" not in token or token.startswith("/")),
        None,
    )
    if executable_index is None:
        return False
    executable = Path(command[executable_index]).name
    if executable in _READ_ONLY_COMMANDS:
        return True
    if executable != "git":
        return False
    subcommand = next(
        (token for token in command[executable_index + 1:] if not token.startswith("-")),
        "",
    )
    return subcommand in _ALLOWED_GIT_SUBCOMMANDS


def _write_redirects_to_control_plane(command: list[str], cwd: Path) -> bool:
    for index, token in enumerate(command[:-1]):
        if ">" in token and _control_plane_name(_argument_path(command[index + 1], cwd), cwd):
            return True
    return False


def _unsafe_shell_reference(command: str, invocation_cwd: Path) -> str | None:
    cwd = invocation_cwd
    for simple in _simple_commands(_shell_tokens(command)):
        name = _referenced_control_plane(simple, cwd)
        if name and (_write_redirects_to_control_plane(simple, cwd) or not _command_is_allowed(simple)):
            return name
        if len(simple) >= 2 and Path(simple[0]).name == "cd":
            cwd = _argument_path(simple[1], cwd)
    return None


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
        protected_name = _unsafe_shell_reference(
            str(ctx.tool_input.get("command", "")),
            ctx.input.invocation_cwd or ctx.cwd,
        )
        if protected_name:
            return _policy_result(protected_name, mode)
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
