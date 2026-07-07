#!/usr/bin/env python3
"""Fettle install utilities — one-command setup for new projects.

Usage:
    python3 install.py hooks      # Generate Claude Code hook config snippet
    python3 install.py config     # Create default .fettle.toml
    python3 install.py ignore     # Create .fettle-ignore
    python3 install.py all        # All of the above
    python3 install.py status     # Check installation status
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import find_repo_root

DEFAULT_FETTLE_TOML = """# Fettle configuration
# See: https://github.com/MilindGaharwar/fettle/blob/main/docs/CONFIG.md

[gates.lint]
enabled = true
mode = "advisory"   # advisory | soft | enforce

[gates.plan]
enabled = false

[gates.ux_spec]
enabled = false

[gates.ui_colors]
enabled = false

[gates.mcp_trust]
enabled = false

[severity]
error_rules = ["BLE001", "S110", "S608", "S701"]
warning_prefixes = ["SIM", "UP"]

[paths]
ruff_config = ""    # empty = plugin's rules/.ruff.toml

[review]
provider = "ollama"
model = "sam860/LFM2:8b"
"""

DEFAULT_IGNORE = """# .fettle-ignore — glob patterns for files Fettle should skip
# One pattern per line. Lines starting with # are comments.

# Dependencies
node_modules/
.venv/
vendor/

# Generated
*_generated.py
*.min.js
dist/
build/

# Tests (if you don't want lint on tests)
# tests/
"""


def install_hooks(repo_root: Path) -> None:
    """Print hook config for Claude Code settings or project .claude/settings.json."""
    plugin_path = Path(__file__).parent.parent
    print("── Add to .claude/settings.json (project) or ~/.claude/settings.json (global) ──\n")
    print(json.dumps({
        "hooks": {
            "PostToolUse": [{
                "matcher": "Write|Edit",
                "hooks": [{
                    "type": "command",
                    "command": f"bash {plugin_path}/scripts/run.sh post_edit.py",
                    "timeout": 15000,
                }]
            }]
        }
    }, indent=2))
    print("\n  Or use authoritative hooks.json (auto-discovered from plugin dir).")


def install_config(repo_root: Path) -> None:
    """Create .fettle.toml in repo root."""
    config_path = repo_root / ".fettle.toml"
    if config_path.exists():
        print(f"  .fettle.toml already exists at {config_path}")
        return
    config_path.write_text(DEFAULT_FETTLE_TOML)
    print(f"  ✓ Created {config_path}")


def install_ignore(repo_root: Path) -> None:
    """Create .fettle-ignore in repo root."""
    ignore_path = repo_root / ".fettle-ignore"
    if ignore_path.exists():
        print(f"  .fettle-ignore already exists at {ignore_path}")
        return
    ignore_path.write_text(DEFAULT_IGNORE)
    print(f"  ✓ Created {ignore_path}")


def check_status(repo_root: Path) -> None:
    """Check installation status."""
    print("── Fettle Installation Status ──\n")

    config_exists = (repo_root / ".fettle.toml").exists()
    ignore_exists = (repo_root / ".fettle-ignore").exists()

    import shutil
    ruff_ok = shutil.which("ruff") is not None
    semgrep_ok = shutil.which("semgrep") is not None

    print(f"  Repo root: {repo_root}")
    print(f"  .fettle.toml: {'✓' if config_exists else '✗ (run: fettle install config)'}")
    print(f"  .fettle-ignore: {'✓' if ignore_exists else '✗ (optional)'}")
    print(f"  ruff: {'✓' if ruff_ok else '✗ (run: uv tool install ruff)'}")
    print(f"  semgrep: {'✓' if semgrep_ok else '✗ (optional: uv tool install semgrep)'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle installation utilities")
    parser.add_argument("action", choices=["hooks", "config", "ignore", "all", "status"])
    args = parser.parse_args()

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository.", file=sys.stderr)
        sys.exit(1)

    print("── Fettle Install ──\n")

    if args.action == "hooks":
        install_hooks(repo_root)
    elif args.action == "config":
        install_config(repo_root)
    elif args.action == "ignore":
        install_ignore(repo_root)
    elif args.action == "all":
        install_config(repo_root)
        install_ignore(repo_root)
        print()
        install_hooks(repo_root)
    elif args.action == "status":
        check_status(repo_root)


if __name__ == "__main__":
    main()
