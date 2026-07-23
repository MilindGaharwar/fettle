"""WP-V — Architecture Boundary Rules Gate.

PostToolUse(Write/Edit) check that enforces declared dependency direction
rules from .fettle.toml. Validates imports against allowed/denied paths.
"""

from __future__ import annotations

import ast
import fnmatch
import os


def _get_imports(file_path: str) -> list[str]:
    """Extract import module names from a Python file."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError):
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _module_to_path(module: str) -> str:
    """Convert dotted module name to a path-like string for matching."""
    return module.replace(".", "/")


def _matches_glob(path: str, pattern: str) -> bool:
    """Check if a path matches a glob pattern (with ** support)."""
    if fnmatch.fnmatch(path, pattern):
        return True
    if fnmatch.fnmatch(path + ".py", pattern):
        return True
    # Handle "module/**" matching "module" and "module/sub"
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def run_check(ctx):
    """PostToolUse(Write/Edit) — check imports against boundary rules."""
    from dispatcher_types import CheckResult

    cfg = ctx.config.get("gates", {}).get("architecture_boundaries", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    rules = cfg.get("rules", [])
    if not rules:
        return CheckResult.allow()

    file_path = ctx.tool_input.get("file_path", "")
    if not file_path or not file_path.endswith(".py"):
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    rel_path = os.path.relpath(file_path, cwd) if os.path.isabs(file_path) else file_path
    rel_path = rel_path.replace("\\", "/")

    if not os.path.isfile(file_path):
        return CheckResult.allow()

    imports = _get_imports(file_path)
    if not imports:
        return CheckResult.allow()

    violations: list[str] = []

    for imp in imports:
        imp_path = _module_to_path(imp)
        for rule in rules:
            from_pat = rule.get("from", "")
            to_pat = rule.get("to", "")
            allow = rule.get("allow", True)

            if not _matches_glob(rel_path, from_pat):
                continue
            if not _matches_glob(imp_path, to_pat):
                continue

            if not allow:
                violations.append(
                    rel_path + " imports " + imp + " — violates rule: "
                    + from_pat + " → " + to_pat + " (denied)"
                )

    if not violations:
        return CheckResult.allow()

    msg = "Architecture boundary violations:\n" + "\n".join("  " + v for v in violations[:5])
    return CheckResult.advisory(msg, hook_specific_output={
        "hookEventName": ctx.input.hook_event_name,
        "additionalContext": msg,
    })
