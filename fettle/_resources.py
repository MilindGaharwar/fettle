"""Runtime resource location for fettle.

Resolves paths to bundled resources (rules/, templates/, etc.) that work in
both install modes:

1. Clone-into-plugins: rules/ lives at repo root (../rules relative to scripts/)
2. pip/uvx install: rules/ is copied into the wheel as fettle/_rules/
"""

from __future__ import annotations

import os
from pathlib import Path

_PACKAGE_DIR = Path(__file__).parent
_REPO_ROOT = _PACKAGE_DIR.parent  # Only valid in clone mode


def rules_dir() -> Path:
    """Return the path to the semgrep/ruff rules directory.

    Resolution order:
    1. CLAUDE_PLUGIN_ROOT env var (explicit override)
    2. Clone-mode: repo_root/rules/ (exists when running from git clone)
    3. Pip-installed: package/_rules/ (bundled inside the wheel)
    """
    # 1. Explicit env var
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        candidate = Path(env_root) / "rules"
        if candidate.is_dir():
            return candidate

    # 2. Clone mode — rules/ at repo root
    clone_rules = _REPO_ROOT / "rules"
    if clone_rules.is_dir():
        return clone_rules

    # 3. Pip-installed — _rules/ inside the package
    pkg_rules = _PACKAGE_DIR / "_rules"
    if pkg_rules.is_dir():
        return pkg_rules

    # Fallback to clone path (will fail gracefully downstream)
    return clone_rules
