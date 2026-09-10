"""Fail-closed secret protection for agent tool boundaries."""

from __future__ import annotations

import base64
import binascii
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from fettle.dispatcher_types import CheckResult, HookContext


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub PAT", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("GitHub OAuth Token", re.compile(r"gho_[A-Za-z0-9]{36}")),
    ("GitHub App Token", re.compile(r"ghu_[A-Za-z0-9]{36}")),
    ("OpenAI/Anthropic Key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("GCP API Key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("Private Key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    (
        "Bearer Token",
        re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"),
    ),
    (
        "Credential",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|token|api[_-]?key|auth[_-]?token|access[_-]?token)"
            r"\b\s*[=:]\s*['\"]?[^\s'\",;}]{8,}"
        ),
    ),
)
_BASE64 = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9+/=])")
_ENV_DUMP = re.compile(r"(?<![\w-])(?:[\w./-]*/)?(?:env|printenv)(?![\w-])", re.IGNORECASE)
_READ_COMMANDS = frozenset({"cat", "head", "tail", "less", "more", "strings"})


@dataclass(frozen=True)
class SecretLocation:
    source: str
    line: int
    credential_type: str


def _matches(text: str) -> list[tuple[str, int, int, int]]:
    matches: list[tuple[str, int, int, int]] = []
    for credential_type, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            matches.append((credential_type, line, match.start(), match.end()))

    for encoded in _BASE64.finditer(text):
        try:
            decoded = base64.b64decode(encoded.group(0), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        decoded_matches = _matches_without_base64(decoded)
        if decoded_matches:
            credential_type = f"Base64-encoded {decoded_matches[0][0]}"
            line = text.count("\n", 0, encoded.start()) + 1
            matches.append((credential_type, line, encoded.start(), encoded.end()))
    return sorted(matches, key=lambda item: (item[2], item[0]))


def _matches_without_base64(text: str) -> list[tuple[str, int, int, int]]:
    matches: list[tuple[str, int, int, int]] = []
    for credential_type, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            matches.append((credential_type, line, match.start(), match.end()))
    return matches


def find_secret_locations(text: str, source: str) -> list[SecretLocation]:
    """Return value-free locations for credentials found in text."""
    return [
        SecretLocation(source=source, line=line, credential_type=credential_type)
        for credential_type, line, _start, _end in _matches(text)
    ]


def redact_secrets(text: str) -> str:
    """Replace detected credential spans, including encoded credentials."""
    redacted = text
    for _kind, _line, start, end in reversed(_matches(text)):
        redacted = redacted[:start] + "***REDACTED***" + redacted[end:]
    return redacted


def _scan_file(path: Path) -> list[SecretLocation]:
    if path.is_dir():
        return []
    return find_secret_locations(path.read_text(encoding="utf-8", errors="replace"), str(path))


def _block(location: SecretLocation) -> CheckResult:
    message = (
        f"Blocked secret access: {location.credential_type} at "
        f"{location.source}:{location.line}. Use a scoped non-secret source."
    )
    return CheckResult.block(message)


def _shell_paths(command: str, cwd: Path) -> list[Path]:
    try:
        words = shlex.split(command)
    except ValueError as exc:
        raise ValueError("malformed shell command") from exc
    paths: list[Path] = []
    for index, word in enumerate(words[:-1]):
        if Path(word).name in {"bash", "sh", "zsh"} and words[index + 1] == "-c":
            if index + 2 < len(words):
                paths.extend(_shell_paths(words[index + 2], cwd))
    if not any(Path(word).name in _READ_COMMANDS for word in words):
        return paths
    for word in words:
        candidate = Path(word)
        if word.startswith("-"):
            continue
        candidate = candidate if candidate.is_absolute() else cwd / candidate
        if candidate.is_file():
            paths.append(candidate)
    return paths


def _input_paths(ctx: HookContext) -> list[Path]:
    paths: list[Path] = []
    for key in ("file_path", "path", "notebook_path"):
        value = ctx.tool_input.get(key)
        if not isinstance(value, str) or not value:
            continue
        path = Path(value)
        paths.append(path if path.is_absolute() else ctx.cwd / path)
    return paths


def run_check(ctx: HookContext) -> CheckResult:
    """Deny tool requests that could expose a detected credential."""
    try:
        tool_name = ctx.tool_name or ""
        if tool_name == "Read" or "read" in tool_name.lower():
            targets = _input_paths(ctx)
            if not targets:
                raise ValueError("read request has no path")
            for target in targets:
                findings = _scan_file(target)
                if findings:
                    return _block(findings[0])
            return CheckResult.allow()

        if ctx.tool_name == "Bash":
            command = ctx.tool_input.get("command")
            if not isinstance(command, str):
                raise ValueError("shell request has no command")
            if _ENV_DUMP.search(command):
                return _block(SecretLocation("<environment>", 1, "Environment credential dump"))
            inline = find_secret_locations(command, "<command>")
            if inline:
                return _block(inline[0])
            for path in _shell_paths(command, ctx.cwd):
                findings = _scan_file(path)
                if findings:
                    return _block(findings[0])
        elif tool_name.startswith("mcp__"):
            inline = find_secret_locations(str(ctx.tool_input), "<tool-input>")
            if inline:
                return _block(inline[0])
            for path in _input_paths(ctx):
                findings = _scan_file(path)
                if findings:
                    return _block(findings[0])
        return CheckResult.allow()
    except Exception:  # noqa: BLE001 - this security boundary must fail closed
        return CheckResult.block(
            "Secret protection failed closed; the tool was not run. Run `fettle doctor` and retry."
        )
