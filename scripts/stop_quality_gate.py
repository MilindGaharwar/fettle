#!/usr/bin/env python3
"""Fettle Stop hook — cross-file quality analysis before response delivery.

Reads the edit tracking file, runs import graph checks on edited .py files,
and optionally runs cargo check on edited .rs files. Blocks response if
cross-file issues are found.
"""

import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from import_graph import check_imports, check_contracts


def _find_cargo_toml(rs_path: str) -> str | None:
    d = os.path.dirname(os.path.abspath(rs_path))
    while d != "/":
        if os.path.isfile(os.path.join(d, "Cargo.toml")):
            return os.path.join(d, "Cargo.toml")
        d = os.path.dirname(d)
    return None


def _cargo_check(rs_path: str) -> list[str]:
    cargo_toml = _find_cargo_toml(rs_path)
    if not cargo_toml:
        return []

    cargo_bin = os.path.expanduser(
        "~/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/cargo"
    )
    if not os.path.isfile(cargo_bin):
        return []

    manifest_dir = os.path.dirname(cargo_toml)
    try:
        proc = subprocess.run(
            [cargo_bin, "check", "--message-format=json"],
            cwd=manifest_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    errors: list[str] = []
    for line in proc.stdout.splitlines():
        try:
            msg: dict[str, object] = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("reason") == "compiler-message":
            inner = msg.get("message", {})
            if isinstance(inner, dict) and inner.get("level") == "error":
                rendered = str(inner.get("rendered", "")).strip()
                if rendered:
                    errors.append(rendered)
    return errors


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    if data.get("stop_hook_active") is True:
        sys.exit(0)

    tracking_path: str = os.environ.get("FETTLE_EDIT_TRACKING", "/tmp/fettle-edits.jsonl")  # shared with post_edit.py and quality_gate.py

    entries: list[dict[str, object]] = []
    try:
        with open(tracking_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except (FileNotFoundError, json.JSONDecodeError):
        sys.exit(0)

    if not entries:
        sys.exit(0)

    edited_files: list[str] = list(dict.fromkeys(
        str(e.get("file", "")) for e in entries if e.get("file")
    ))

    py_files = [f for f in edited_files if f.endswith(".py") and os.path.isfile(f)]
    rs_files = [f for f in edited_files if f.endswith(".rs") and os.path.isfile(f)]

    if not py_files and not rs_files:
        sys.exit(0)

    all_findings: list[str] = []

    for py_file in py_files:
        project_root: str = os.environ.get("FETTLE_PROJECT_ROOT", os.path.dirname(py_file))
        import_errors: list[dict[str, str]] = check_imports(py_file, project_root)
        for err in import_errors:
            all_findings.append(
                f"{os.path.basename(err['file'])}:{err['line']}: "
                f"cannot resolve import '{err['module']}'"
            )
        contract_errors: list[dict[str, str]] = check_contracts(py_file, project_root)
        for err in contract_errors:
            all_findings.append(
                f"{os.path.basename(err['file'])}:{err['line']}: "
                f"'{err['name']}' not found in '{err['module']}'"
            )

    checked_workspaces: set[str] = set()
    for rs_file in rs_files:
        cargo_toml = _find_cargo_toml(rs_file)
        if not cargo_toml or cargo_toml in checked_workspaces:
            continue
        checked_workspaces.add(cargo_toml)
        errors = _cargo_check(rs_file)
        for err in errors:
            all_findings.append(err)

    if not all_findings:
        sys.exit(0)

    report = "\n".join(all_findings[:20])
    reason = (
        f"Cross-file quality issues found ({len(all_findings)} finding(s)):\n\n"
        f"{report}\n\n"
        f"Fix these issues before completing your response."
    )

    output: dict[str, object] = {"decision": "block", "reason": reason}
    print(json.dumps(output))
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except (json.JSONDecodeError, OSError, ValueError):
        sys.exit(0)
