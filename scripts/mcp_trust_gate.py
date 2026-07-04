#!/usr/bin/env python3
"""PreToolUse hook: blocks unauthorized package installations and protects trust infrastructure.

Reads allowlist from ~/.config/fettle/mcp-allowlist.json (root-owned). Env override: MCP_ALLOWLIST_PATH.
"""

import json
import os
import re
import sys
from typing import NoReturn


def load_allowlist() -> dict[str, object]:
    path = os.environ.get("MCP_ALLOWLIST_PATH", "~/.config/fettle/mcp-allowlist.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"packages": {}, "registries_blocked": [], "protected_paths": []}


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


PKG_INSTALL_RE = re.compile(
    r"(?:^|&&|\|\||;|\$\()\s*(?:sudo\s+)?"
    r"(npm|npx|yarn|pnpm|pip|pip3|pipx|cargo|bun|bunx)\s+"
    r"(?:install|i|add|update|up|upgrade|exec|run|dlx)\b",
    re.IGNORECASE,
)

NPX_RE = re.compile(
    r"(?:^|&&|\|\||;|\$\()\s*(?:sudo\s+)?"
    r"(npx|bunx|pipx\s+run|yarn\s+dlx|pnpm\s+dlx)\s+",
    re.IGNORECASE,
)

BARE_PKG_INSTALL_RE = re.compile(
    r"(?:^|&&|\|\||;|\$\()\s*(?:sudo\s+)?"
    r"(npm|yarn|pnpm|pip|pip3|pipx|cargo|bun)\s+"
    r"(install|i|add)\s+(\S+)",
    re.IGNORECASE,
)

IPTABLES_MODIFY_RE = re.compile(
    r"(?:^|&&|\|\||;|\n|\$\()\s*(?:sudo\s+)?iptables\s+(-D|-F|-X|-Z|-P)",
    re.IGNORECASE | re.MULTILINE,
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


def _is_pip_command(command: str) -> bool:
    return bool(re.search(r"(?:^|&&|\|\||;|\$\()\s*(?:sudo\s+)?(?:pip|pip3)\s+", command, re.IGNORECASE))


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
    registries = allowlist.get("registries_blocked", [])
    protected = allowlist.get("protected_paths", [])

    if isinstance(protected, list):
        for path in protected:
            if isinstance(path, str) and path in command and WRITE_INDICATORS_RE.search(command):
                deny(f"Write to protected path blocked: {path}")

    if IPTABLES_MODIFY_RE.search(command):
        deny("Modification of iptables rules is blocked. These protect the supply chain gate.")

    if PKG_INSTALL_RE.search(command):
        reason = check_package_approved(command, allowlist)
        if reason:
            deny(reason)
        return

    if NPX_RE.search(command):
        reason = check_package_approved(command, allowlist)
        if reason is None:
            m = re.search(r"(?:npx|bunx|pipx\s+run|yarn\s+dlx|pnpm\s+dlx)\s+(\S+)", command, re.IGNORECASE)
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
                    deny(f"Package '{pkg}' is not in the allowlist.")
        else:
            deny(reason)
        return

    if isinstance(registries, list):
        for reg in registries:
            if isinstance(reg, str) and reg in command and re.search(r"(curl|wget|fetch|http)", command, re.IGNORECASE):
                deny(f"Direct download from blocked registry: {reg}")


def check_file_tool(file_path: str, allowlist: dict[str, object]) -> None:
    protected = allowlist.get("protected_paths", [])
    if file_path == "~/.config/fettle/mcp-allowlist.json":
        deny(f"Write to protected path blocked: {file_path}")
    if isinstance(protected, list):
        if file_path in protected:
            deny(f"Write to protected path blocked: {file_path}")
        for p in protected:
            if isinstance(p, str) and (file_path.startswith(p + "/") or file_path.startswith(p + os.sep)):
                deny(f"Write to protected path blocked: {file_path} (under {p})")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_name: str = data.get("tool_name", "")
    tool_input: dict[str, str] = data.get("tool_input", {})
    allowlist = load_allowlist()

    if tool_name == "Bash":
        command: str = tool_input.get("command", "")
        if command:
            check_bash(command, allowlist)

    elif tool_name in ("Write", "Edit"):
        file_path: str = tool_input.get("file_path", "")
        if file_path:
            check_file_tool(file_path, allowlist)

    sys.exit(0)


if __name__ == "__main__":
    main()
