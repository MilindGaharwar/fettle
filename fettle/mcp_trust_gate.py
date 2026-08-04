#!/usr/bin/env python3
"""PreToolUse hook: blocks unauthorized package installations and protects trust infrastructure.

Reads allowlist from ~/.config/fettle/mcp-allowlist.json (root-owned). Env override: MCP_ALLOWLIST_PATH.
"""

import json
import os
import re
import sys
from typing import NoReturn


DEFAULT_ALLOWLIST_PATH = "~/.config/fettle/mcp-allowlist.json"


def _allowlist_path(configured: str | None = None) -> str:
    """Absolute path to the allowlist file.

    Precedence: policy-pinned [gates.mcp_trust].allowlist_path > env
    override > default. When policy pins the path, MCP_ALLOWLIST_PATH is
    deliberately IGNORED — an env var writable by the agent must not
    redirect the trust root (audit B-1.2).
    """
    raw = configured or os.environ.get("MCP_ALLOWLIST_PATH", DEFAULT_ALLOWLIST_PATH)
    return os.path.abspath(os.path.expanduser(raw))


_EMPTY_ALLOWLIST: dict[str, object] = {"packages": {}, "registries_blocked": [], "protected_paths": []}


def load_allowlist(configured: str | None = None) -> tuple[dict[str, object], str | None]:
    """Load the allowlist. Returns (allowlist, error).

    error is None when the file loaded, or when it simply does not exist
    (gate enabled but not yet configured). error is a message when the file
    EXISTS but cannot be read or parsed — callers must fail closed then:
    a corrupt allowlist silently disabling path/registry protections is
    exactly the tampering this gate exists to stop.
    """
    path = _allowlist_path(configured)
    if not os.path.exists(path):
        return dict(_EMPTY_ALLOWLIST), None
    try:
        with open(path) as f:
            return json.load(f), None
    except (OSError, json.JSONDecodeError) as exc:
        return dict(_EMPTY_ALLOWLIST), f"{type(exc).__name__}: {exc}"


def deny(reason: str) -> NoReturn:
    out: dict[str, object] = {
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }
    print(json.dumps(out))
    sys.exit(2)


# Command-position boundary. Newline, single pipe and backtick are
# boundaries too (audit H-03: `true\npip install x`, `true | pip install x`
# and `` `pip install x` `` all bypassed the old class).
_BOUNDARY = r"(?:^|&&|\|\||\||;|\n|`|\$\()"

# Benign wrapper prefixes that still execute the wrapped command:
# sudo [-E ...], env [VAR=x ...], command, nohup, xargs [-n1 ...].
_WRAPPERS = (
    r"(?:(?:sudo(?:\s+-\S+)*|env(?:\s+[A-Za-z_][A-Za-z0-9_]*=\S*)*"
    r"|command|nohup|xargs(?:\s+-\S+)*)\s+)*"
)

_PKG_VERBS = r"(?:install|i|add|update|up|upgrade|exec|run|dlx)"

PKG_INSTALL_RE = re.compile(
    _BOUNDARY + r"\s*" + _WRAPPERS
    + r"(?:(?:npm|npx|yarn|pnpm|pip|pip3|pipx|cargo|bun|bunx)\s+" + _PKG_VERBS + r"\b"
    + r"|uv\s+(?:pip\s+|tool\s+)?" + _PKG_VERBS + r"\b"
    + r"|python3?(?:\.\d+)?\s+-m\s+pip\s+" + _PKG_VERBS + r"\b)",
    re.IGNORECASE,
)

NPX_RE = re.compile(
    _BOUNDARY + r"\s*" + _WRAPPERS
    + r"(npx|bunx|uvx|pipx\s+run|yarn\s+dlx|pnpm\s+dlx|uv\s+tool\s+run)\s+",
    re.IGNORECASE,
)

BARE_PKG_INSTALL_RE = re.compile(
    _BOUNDARY + r"\s*" + _WRAPPERS
    + r"(npm|yarn|pnpm|pip|pip3|pipx|cargo|bun"
    + r"|uv\s+pip|uv\s+tool|uv|python3?(?:\.\d+)?\s+-m\s+pip)\s+"
    + r"(install|i|add)\s+(\S+)",
    re.IGNORECASE,
)

IPTABLES_MODIFY_RE = re.compile(
    _BOUNDARY + r"\s*(?:sudo\s+)?iptables\s+(-D|-F|-X|-Z|-P)",
    re.IGNORECASE | re.MULTILINE,
)

# Loose detector for the ambiguity backstop: a package-manager install
# vocabulary ANYWHERE in the command (no boundary requirement).
_LOOSE_PKG_RE = re.compile(
    r"\b(?:npm|yarn|pnpm|pip3?|pipx|cargo|bun|uv)\s+(?:-\S+\s+)*(?:pip\s+|tool\s+)?"
    r"(?:install|i|add|upgrade|update|dlx)\b"
    r"|\b(?:npx|bunx|uvx)\s+\S"
    r"|python3?(?:\.\d+)?\s+-m\s+pip\s+(?:-\S+\s+)*(?:install|download)\b",
    re.IGNORECASE,
)

# Shell-eval constructs that can smuggle a command past positional matching.
_SHELL_EVAL_RE = re.compile(
    r"`|\$\(|\beval\b|\b(?:sh|bash|zsh|dash|ksh)\s+(?:-\S+\s+)*-c\b|\bbase64\b|\bxargs\b",
    re.IGNORECASE,
)


def _parse_pkg_spec(pkg_spec: str) -> tuple[str, str | None]:
    if "==" in pkg_spec:
        name, version = pkg_spec.split("==", 1)
        return name, version
    if "@" in pkg_spec and not pkg_spec.startswith("@"):
        name, version = pkg_spec.rsplit("@", 1)
        return name, version
    if pkg_spec.startswith("@"):
        parts = pkg_spec.split("@")
        if len(parts) >= 3:
            return "@" + parts[1], parts[2]
        return pkg_spec, None
    return pkg_spec, None


_PIP_CMD_RE = re.compile(
    _BOUNDARY + r"\s*" + _WRAPPERS
    + r"(?:(?:pip|pip3|pipx)\s+|python3?(?:\.\d+)?\s+-m\s+pip\s+|uv\s+pip\s+)",
    re.IGNORECASE,
)


def _is_pip_command(command: str) -> bool:
    return bool(_PIP_CMD_RE.search(command))


def check_package_approved(command: str, allowlist: dict[str, object]) -> str | None:
    packages = allowlist.get("packages", {})
    if not isinstance(packages, dict):
        return None

    m = BARE_PKG_INSTALL_RE.search(command)
    if m:
        pkg_spec = m.group(3)
        name, version = _parse_pkg_spec(pkg_spec)

        if version is None:
            return f"Unpinned package: '{pkg_spec}'. Pin an exact version (e.g., {name}@x.y.z or {name}==x.y.z)."

        entry = packages.get(name)
        if not isinstance(entry, dict) or entry.get("version") != version:
            return f"Package {name}@{version} is not in the allowlist. Run the Zero-Trust Validation Protocol first."

        if _is_pip_command(command):
            sha = entry.get("sha256_wheel") or entry.get("sha256_tarball")
            if sha and f"--hash=sha256:{sha}" not in command:
                return (
                    f"Package {name}=={version} requires hash verification. "
                    f"Use: pip install {name}=={version} "
                    f"--only-binary :all: --require-hashes --hash=sha256:{sha}"
                )

            if not entry.get("allow_source", False) and "--only-binary" not in command:
                return (
                    f"Package {name}=={version} requires binary-only install to prevent setup.py execution. "
                    f"Use: pip install {name}=={version} --only-binary :all:"
                )

        return None

    return None


WRITE_INDICATORS_RE = re.compile(
    r">|tee\s|cp\s|mv\s|install\s|rm\s|chmod\s|chown\s|ln\s|dd\s|rsync\s"
    r"|\.write\(|\.write_text\(|\.write_bytes\("
    r"|open\([^)]*['\"][wa]"
    r"|pathlib\.|shutil\."
    r"|cat\s*>|cat\s*<<",
    re.IGNORECASE,
)


def check_bash(command: str, allowlist: dict[str, object]) -> None:
    reason = _check_bash_result(command, allowlist)
    if reason:
        deny(reason)


def _file_denial_reason(
    file_path: str,
    allowlist: dict[str, object],
    configured: str | None = None,
) -> str | None:
    """Shared protected-path check with full resolution (audit H-04).

    expanduser + abspath + realpath so `~`-spelled, absolute and
    symlinked spellings of the same target are all caught, and the
    ACTIVE allowlist path (env/config override) is always protected.
    """
    protected = allowlist.get("protected_paths", [])
    resolved = os.path.realpath(os.path.abspath(os.path.expanduser(file_path)))
    if file_path == DEFAULT_ALLOWLIST_PATH or resolved == os.path.realpath(_allowlist_path(configured)):
        return f"Write to protected path blocked: {file_path}"
    if isinstance(protected, list):
        if file_path in protected:
            return f"Write to protected path blocked: {file_path}"
        for p in protected:
            if not isinstance(p, str):
                continue
            p_resolved = os.path.realpath(os.path.abspath(os.path.expanduser(p)))
            if resolved == p_resolved or resolved.startswith(p_resolved + os.sep):
                return f"Write to protected path blocked: {file_path} (under {p})"
            if file_path.startswith(p + "/") or file_path.startswith(p + os.sep):
                return f"Write to protected path blocked: {file_path} (under {p})"
    return None


def check_file_tool(
    file_path: str,
    allowlist: dict[str, object],
    configured: str | None = None,
) -> None:
    reason = _file_denial_reason(file_path, allowlist, configured)
    if reason:
        deny(reason)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_name: str = data.get("tool_name", "")
    tool_input: dict[str, str] = data.get("tool_input", {})

    # Opt-in gate: with an empty default allowlist this gate would block ALL
    # package installs — it must never run unless explicitly enabled.
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # repo root
    from fettle.config import load_config
    cfg = load_config(data.get("cwd", "."))
    if not cfg["gates"]["mcp_trust"]["enabled"]:
        sys.exit(0)
    configured = cfg["gates"]["mcp_trust"].get("allowlist_path") or None

    allowlist, allowlist_error = load_allowlist(configured)
    if allowlist_error:
        deny(
            "MCP trust gate is enabled but its allowlist could not be read "
            f"({allowlist_error}). Failing closed. Fix or restore {_allowlist_path(configured)}."
        )

    if tool_name == "Bash":
        command: str = tool_input.get("command", "")
        if command:
            check_bash(command, allowlist)

    elif tool_name in ("Write", "Edit"):
        file_path: str = tool_input.get("file_path", "")
        if file_path:
            check_file_tool(file_path, allowlist, configured)

    sys.exit(0)


def _check_bash_result(command: str, allowlist: dict) -> str | None:
    """Single source of bash-denial logic; check_bash denies on its result."""
    registries = allowlist.get("registries_blocked", [])
    protected = allowlist.get("protected_paths", [])

    if isinstance(protected, list):
        for path in protected:
            if isinstance(path, str) and path in command and WRITE_INDICATORS_RE.search(command):
                return f"Write to protected path blocked: {path}"

    if IPTABLES_MODIFY_RE.search(command):
        return "Modification of iptables rules is blocked. These protect the supply chain gate."

    if PKG_INSTALL_RE.search(command):
        reason = check_package_approved(command, allowlist)
        if reason:
            return reason
        # approved or unparseable spec — still subject to the registry
        # check and the ambiguity backstop below
    elif NPX_RE.search(command):
        reason = check_package_approved(command, allowlist)
        if reason:
            return reason
        m = re.search(
            r"(?:npx|bunx|uvx|pipx\s+run|yarn\s+dlx|pnpm\s+dlx|uv\s+tool\s+run)\s+(\S+)",
            command, re.IGNORECASE,
        )
        if m:
            pkg = m.group(1)
            packages = allowlist.get("packages", {})
            found = False
            if isinstance(packages, dict):
                for name, entry in packages.items():
                    if isinstance(entry, dict):
                        versioned = f"{name}@{entry['version']}"
                        if pkg in (versioned, name):
                            found = True
                            break
            if not found:
                return f"Package '{pkg}' is not in the allowlist."

    if isinstance(registries, list):
        for reg in registries:
            if isinstance(reg, str) and reg in command and re.search(r"(curl|wget|fetch|http)", command, re.IGNORECASE):
                return f"Direct download from blocked registry: {reg}"

    # Ambiguity backstop (audit H-03): install vocabulary present but in a
    # position the anchored matchers cannot classify (quoted inside sh -c,
    # eval, backticks…). Regex mediation cannot prove it safe — deny.
    if _LOOSE_PKG_RE.search(command) and _SHELL_EVAL_RE.search(command):
        return (
            "Ambiguous package-manager invocation inside a shell-eval "
            "construct (sh -c/eval/backticks/xargs). The trust gate cannot "
            "classify it — run the install as a direct top-level command."
        )

    return None


def _check_file_result(
    file_path: str, allowlist: dict, configured: str | None = None
) -> str | None:
    """Same logic as check_file_tool but returns denial reason."""
    return _file_denial_reason(file_path, allowlist, configured)


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from fettle.dispatcher_types import CheckResult

    if not ctx.config.get("gates", {}).get("mcp_trust", {}).get("enabled", False):
        return CheckResult.allow()

    configured = ctx.config.get("gates", {}).get("mcp_trust", {}).get("allowlist_path") or None
    allowlist, allowlist_error = load_allowlist(configured)
    if allowlist_error:
        reason = (
            "MCP trust gate is enabled but its allowlist could not be read "
            f"({allowlist_error}). Failing closed. Fix or restore {_allowlist_path(configured)}."
        )
        return CheckResult.block(
            reason,
            hook_specific_output={
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            },
        )
    tool_name = ctx.tool_name or ""

    if tool_name == "Bash":
        command = ctx.tool_input.get("command", "")
        if command:
            reason = _check_bash_result(command, allowlist)
            if reason:
                return CheckResult.block(
                    reason,
                    hook_specific_output={
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    },
                )
    elif tool_name in ("Write", "Edit"):
        file_path = ctx.tool_input.get("file_path", "")
        if file_path:
            reason = _check_file_result(file_path, allowlist, configured)
            if reason:
                return CheckResult.block(
                    reason,
                    hook_specific_output={
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    },
                )

    return CheckResult.allow()


if __name__ == "__main__":
    main()
