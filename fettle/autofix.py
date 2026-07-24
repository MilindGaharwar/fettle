#!/usr/bin/env python3
"""Fettle autofix — apply safe ruff fixes automatically.

Only applies fixes classified as "safe" by ruff. Never applies unsafe fixes
without explicit --unsafe flag.

Usage:
    python3 autofix.py --file path/to/file.py
    python3 autofix.py --root . [--unsafe]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.config import load_config
from fettle.paths import find_repo_root
from fettle.trace import log_decision


def _resolve_ruff() -> str | None:
    local = os.path.expanduser("~/.local/bin/ruff")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return shutil.which("ruff")


def fix_file(file_path: str, cfg: dict, unsafe: bool = False) -> dict:
    """Run ruff fix on a single file. Returns result dict."""
    ruff_bin = _resolve_ruff()
    if not ruff_bin:
        return {"file": file_path, "status": "error", "message": "ruff not found"}

    if not os.path.isfile(file_path):
        return {"file": file_path, "status": "error", "message": "file not found"}

    PLUGIN_ROOT = os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    ruff_config = str(cfg["paths"].get("ruff_config", "")) or os.path.join(PLUGIN_ROOT, "rules", ".ruff.toml")

    cmd = [ruff_bin, "check", "--fix", "--config", ruff_config, file_path]
    if unsafe:
        cmd.insert(3, "--unsafe-fixes")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        fixed = "Fixed" in result.stdout or result.returncode == 0

        log_decision(
            hook="autofix",
            status="fixed" if fixed else "no_change",
            tool="ruff",
            file=file_path,
        )

        return {
            "file": file_path,
            "status": "fixed" if fixed else "no_change",
            "stdout": result.stdout[:200],
        }
    except subprocess.TimeoutExpired:
        return {"file": file_path, "status": "error", "message": "ruff timed out"}
    except OSError as e:
        return {"file": file_path, "status": "error", "message": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle autofix")
    parser.add_argument("--file", help="Fix a single file")
    parser.add_argument("--root", help="Fix all Python files in directory")
    parser.add_argument("--unsafe", action="store_true", help="Allow unsafe fixes")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = find_repo_root()
    cfg = load_config(str(repo_root) if repo_root else None)

    results = []

    if args.file:
        results.append(fix_file(args.file, cfg, unsafe=args.unsafe))
    elif args.root:
        root = Path(args.root)
        for py_file in root.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                continue
            results.append(fix_file(str(py_file), cfg, unsafe=args.unsafe))
    else:
        print("Usage: fettle fix --file path.py or --root .")
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        fixed = [r for r in results if r["status"] == "fixed"]
        errors = [r for r in results if r["status"] == "error"]
        print("── Fettle Autofix ──\n")
        print(f"  Fixed: {len(fixed)} file(s)")
        if errors:
            print(f"  Errors: {len(errors)}")
            for e in errors:
                print(f"    • {e['file']}: {e.get('message', '?')}")
        if fixed:
            for f in fixed[:10]:
                print(f"    ✓ {f['file']}")


if __name__ == "__main__":
    main()
