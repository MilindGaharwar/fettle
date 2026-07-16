"""Anchored semgrep invocation + offline-safe rule-pack validation.

Semgrep >= 1.136 resolves ``paths.include``/``paths.exclude`` rule filters
against the *project root* (the enclosing git root). When a scanned file is
not inside a git repo, path-scoped rules silently never match — or excludes
silently stop excluding. This module pins the project root explicitly so
path filters behave identically everywhere.

Validation: semgrep >= 1.168 makes ``--validate`` fetch the
``p/semgrep-rule-lints`` registry pack, which hard-fails offline or behind
TLS-intercepting proxies — and ``--experimental scan --validate`` silently
accepts corrupted configs (caught by the WP-116 mutation check).
``validate_rule_pack`` scans an empty target instead: config parsing runs
fully, no search happens, no network is touched.
"""

import json
import os
import shutil
import subprocess
import tempfile


def validate_rule_pack(config_path: str, timeout: int = 60) -> tuple[bool, str]:
    """Offline-safe rule-pack validation. Returns (valid, error_text)."""
    semgrep_bin = shutil.which("semgrep") or os.path.expanduser("~/.local/bin/semgrep")
    empty_dir = tempfile.mkdtemp(prefix="fettle-validate-")
    try:
        proc = subprocess.run(
            [semgrep_bin, "scan", "--config", str(config_path), "--json",
             "--quiet", "--metrics=off", "--project-root", ".", "."],
            capture_output=True, text=True, timeout=timeout, cwd=empty_dir,
        )
        try:
            errors = json.loads(proc.stdout).get("errors", [])
        except json.JSONDecodeError:
            return False, f"semgrep produced no parseable output: {proc.stderr[-500:]}"
        if errors:
            return False, "\n".join(str(e.get("message", e)) for e in errors)
        return True, ""
    finally:
        shutil.rmtree(empty_dir, ignore_errors=True)


def _find_git_root(start_dir: str) -> str | None:
    """Return the nearest ancestor of start_dir containing .git, else None."""
    current = start_dir
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def anchored_semgrep_args(file_path: str, cwd: str | None = None) -> tuple[list[str], str]:
    """Build anchored semgrep target args for scanning file_path.

    Returns (args, run_cwd): append ``args`` to the semgrep command line
    and run it with ``cwd=run_cwd``. The project root is the file's git
    root, else the session cwd (if it contains the file), else the file's
    own directory.
    """
    abs_path = os.path.abspath(file_path)
    file_dir = os.path.dirname(abs_path)
    root = _find_git_root(file_dir)
    if root is None and cwd:
        abs_cwd = os.path.abspath(cwd)
        if abs_path.startswith(abs_cwd + os.sep):
            root = abs_cwd
    if root is None:
        root = file_dir
    target = os.path.relpath(abs_path, root)
    return ["--project-root", ".", target], root
