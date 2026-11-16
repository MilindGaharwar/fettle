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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)

from fettle.import_graph import check_imports, check_contracts  # noqa: E402


_ROOT_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", ".git")


def _filter_ignored(files: list[str]) -> list[str]:
    """Remove files matching .fettle-ignore patterns from the list."""
    import fnmatch

    if not files:
        return files

    ignore_patterns: list[str] = []
    for f in files:
        project_root = _find_project_root(f)
        ignore_path = os.path.join(project_root, ".fettle-ignore")
        if os.path.isfile(ignore_path):
            with open(ignore_path) as fh:
                ignore_patterns = [
                    ln.strip() for ln in fh
                    if ln.strip() and not ln.startswith("#")
                ]
            break

    if not ignore_patterns:
        return files

    result = []
    for f in files:
        basename = os.path.basename(f)
        relpath = f
        skip = False
        for pat in ignore_patterns:
            if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(relpath, pat):
                skip = True
                break
            if pat.endswith("/") and f"/{pat[:-1]}/" in f:
                skip = True
                break
            if pat.rstrip("/") in f:
                skip = True
                break
        if not skip:
            result.append(f)
    return result


def _find_project_root(py_file: str) -> str:
    """Walk up from the file to the nearest project marker.

    Defaulting to the file's own directory made tests/ subdirectories their
    own import root — a flood of false import findings.
    """
    d = os.path.dirname(os.path.abspath(py_file))
    home = os.path.expanduser("~")
    while d not in ("/", home):
        if any(os.path.exists(os.path.join(d, m)) for m in _ROOT_MARKERS):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.dirname(os.path.abspath(py_file))


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

    import shutil

    cargo_bin = shutil.which("cargo") or os.path.expanduser("~/.cargo/bin/cargo")
    if not (os.path.isfile(cargo_bin) and os.access(cargo_bin, os.X_OK)):
        return []  # no Rust toolchain — skip cleanly

    manifest_dir = os.path.dirname(cargo_toml)
    try:
        proc = subprocess.run(
            [cargo_bin, "check", "--message-format=json"],
            cwd=manifest_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        # Toolchain exists but the check could not run — fail-open for the
        # session, but never silently: leave a tool_error on the audit trail.
        # (log_decision itself warns on stderr if the trace is unwritable.)
        import contextlib
        with contextlib.suppress(Exception):
            from fettle.trace import log_decision
            log_decision(hook="stop-gate", status="tool_error", tool="cargo",
                         file=rs_path,
                         findings=[{"detail": f"{type(exc).__name__}: {exc}"[:500]}])
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
    from fettle.hook_cli import run_main

    run_main(run_check)


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from fettle.dispatcher_types import CheckResult

    if ctx.input.raw.get("stop_hook_active") is True:
        return CheckResult.allow()

    from fettle.edit_journal import entries as journal_entries

    journal = journal_entries(ctx.session_id)
    if journal.malformed_lines:
        return CheckResult.unknown(
            "Cross-file quality edit evidence is malformed.",
            action="Repair the session edit journal and retry.",
        )
    entries = journal.entries
    if not entries:
        return CheckResult.allow()

    edited_files = list(dict.fromkeys(
        str(e.get("file", "")) for e in entries if e.get("file")
    ))

    py_files = _filter_ignored([f for f in edited_files if f.endswith(".py") and os.path.isfile(f)])
    rs_files = _filter_ignored([f for f in edited_files if f.endswith(".rs") and os.path.isfile(f)])

    if not py_files and not rs_files:
        return CheckResult.allow()

    all_findings: list[str] = []

    for py_file in py_files:
        project_root = os.environ.get("FETTLE_PROJECT_ROOT") or _find_project_root(py_file)
        for err in check_imports(py_file, project_root):
            all_findings.append(
                f"{os.path.basename(err['file'])}:{err['line']}: cannot resolve import '{err['module']}'"
            )
        for err in check_contracts(py_file, project_root):
            all_findings.append(
                f"{os.path.basename(err['file'])}:{err['line']}: '{err['name']}' not found in '{err['module']}'"
            )

    checked_workspaces: set[str] = set()
    for rs_file in rs_files:
        cargo_toml = _find_cargo_toml(rs_file)
        if not cargo_toml or cargo_toml in checked_workspaces:
            continue
        checked_workspaces.add(cargo_toml)
        all_findings.extend(_cargo_check(rs_file))

    if not all_findings:
        return CheckResult.allow()

    report = "\n".join(all_findings[:20])
    reason = (
        f"Cross-file quality issues found ({len(all_findings)} finding(s)):\n\n"
        f"{report}\n\n"
        f"Fix these issues before completing your response."
    )
    return CheckResult.block(reason, hook_specific_output={"additionalContext": reason})


if __name__ == "__main__":
    try:
        main()
    except (json.JSONDecodeError, OSError, ValueError):
        sys.exit(0)
