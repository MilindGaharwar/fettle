"""WP-F — Diff Coverage Gate.

Stop hook check that reads pre-existing coverage.json and measures
coverage of edited lines. Does NOT generate coverage data in the hook.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_edited_py_files(edits_path: Path) -> dict[str, set[int]]:
    """Load edited .py files from edits.jsonl. Lines determined via git diff."""
    files: dict[str, str] = {}
    try:
        with open(edits_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                fpath = str(entry.get("file", ""))
                if fpath.endswith(".py") and os.path.isfile(fpath):
                    files[fpath] = fpath
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

    result: dict[str, set[int]] = {}
    for fpath in files:
        lines = _get_changed_lines(fpath)
        if lines:
            result[fpath] = lines
    return result


def _get_changed_lines(file_path: str) -> set[int]:
    """Determine edited lines via git diff (same approach as lean_sniffers)."""
    try:
        cwd = os.path.dirname(os.path.abspath(file_path))
        proc = subprocess.run(
            ["git", "-C", cwd, "diff", "--no-ext-diff", "--unified=0", "--", file_path],
            capture_output=True, text=True, timeout=0.5,
        )
        if proc.returncode != 0:
            return set()
        lines: set[int] = set()
        for match in re.finditer(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", proc.stdout):
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) else 1
            for i in range(start, start + count):
                lines.add(i)
        return lines
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return set()


def _parse_coverage_json(coverage_path: Path) -> dict[str, set[int]]:
    """Parse coverage.py JSON format, return {abs_path: set_of_covered_lines}."""
    try:
        data = json.loads(coverage_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    result: dict[str, set[int]] = {}
    files_data = data.get("files", {})
    for name, entry in files_data.items():
        abs_path = os.path.abspath(name)
        executed = entry.get("executed_lines", [])
        if isinstance(executed, list):
            result[abs_path] = set(executed)
    return result


def _parse_branch_data(coverage_path: Path) -> tuple[dict[str, set[tuple]], dict[str, set[tuple]]]:
    """Parse branch arcs from coverage.json.

    Returns (executed_branches, missing_branches) as {abs_path: set_of_(from,to)_tuples}.
    """
    try:
        data = json.loads(coverage_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}, {}

    executed: dict[str, set[tuple]] = {}
    missing: dict[str, set[tuple]] = {}
    files_data = data.get("files", {})

    for name, entry in files_data.items():
        abs_path = os.path.abspath(name)
        exec_arcs = entry.get("executed_branches", [])
        miss_arcs = entry.get("missing_branches", [])

        if isinstance(exec_arcs, list) and exec_arcs:
            executed[abs_path] = {
                (arc[0], arc[1]) for arc in exec_arcs
                if isinstance(arc, list) and len(arc) >= 2
            }
        if isinstance(miss_arcs, list) and miss_arcs:
            missing[abs_path] = {
                (arc[0], arc[1]) for arc in miss_arcs
                if isinstance(arc, list) and len(arc) >= 2
            }

    return executed, missing


def _check_branch_coverage(
    edited_files: dict[str, set[int]],
    coverage_path: Path,
    threshold: float,
) -> list[str]:
    """Check branch coverage for edited lines. Returns failure messages."""
    executed_branches, missing_branches = _parse_branch_data(coverage_path)

    if not executed_branches and not missing_branches:
        logger.debug("fettle: branch_data_unavailable")
        return []

    total_covered = 0
    total_missing = 0

    for filepath, edited_lines in edited_files.items():
        abs_path = os.path.abspath(filepath)
        file_exec = executed_branches.get(abs_path, set())
        file_miss = missing_branches.get(abs_path, set())

        if not file_exec and not file_miss:
            continue

        for arc in file_exec:
            if arc[0] in edited_lines:
                total_covered += 1
        for arc in file_miss:
            if arc[0] in edited_lines:
                total_missing += 1

    total = total_covered + total_missing
    if total == 0:
        return []

    pct = (total_covered / total) * 100
    if pct >= threshold:
        return []

    return [f"Branch coverage: {pct:.0f}% ({total_covered}/{total} branches from edited lines)"]


def run_check(ctx):
    """Stop hook — check diff coverage of edited files."""
    from fettle.dispatcher_types import CheckResult

    cfg = ctx.config.get("gates", {}).get("coverage", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    cwd = ctx.cwd
    coverage_path = cwd / "coverage.json"
    if not coverage_path.is_file():
        return CheckResult.allow()

    # Staleness guard
    max_staleness = float(cfg.get("max_staleness_seconds", 0))
    from fettle.config import state_dir
    session_id = ctx.session_id or "unknown"
    edits_path = state_dir(session_id) / "edits.jsonl"
    if not edits_path.is_file():
        return CheckResult.allow()

    try:
        coverage_mtime = coverage_path.stat().st_mtime
        edits_mtime = edits_path.stat().st_mtime
        if coverage_mtime < edits_mtime - max_staleness:
            return CheckResult.advisory(
                "Coverage data is stale — re-run tests to enable the coverage gate",
                hook_specific_output={
                    "hookEventName": ctx.input.hook_event_name,
                    "additionalContext": "Coverage data is stale — re-run tests to enable the coverage gate",
                },
            )
    except OSError:
        return CheckResult.allow()

    edited_files = _get_edited_py_files(edits_path)
    if not edited_files:
        return CheckResult.allow()

    covered_lines = _parse_coverage_json(coverage_path)
    threshold = float(cfg.get("threshold", 80))
    failures: list[str] = []

    for filepath, edited_lines in sorted(edited_files.items()):
        if not edited_lines:
            continue
        abs_path = os.path.abspath(filepath)
        file_covered = covered_lines.get(abs_path, set())
        hit = len(edited_lines & file_covered)
        pct = (hit / len(edited_lines)) * 100
        if pct < threshold:
            basename = os.path.basename(filepath)
            failures.append(f"{basename}: {pct:.0f}% ({hit}/{len(edited_lines)} lines)")

    # WP-K: Branch coverage check
    branch_threshold = float(cfg.get("minimum_branch_percent", 0))
    if branch_threshold > 0:
        branch_failures = _check_branch_coverage(edited_files, coverage_path, branch_threshold)
        failures.extend(branch_failures)

    if not failures:
        return CheckResult.allow()

    msg = "Diff coverage below threshold:\n" + "\n".join(failures[:5])
    mode = cfg.get("mode", "advisory")
    if mode == "enforce":
        return CheckResult.block(msg, hook_specific_output={
            "hookEventName": ctx.input.hook_event_name,
            "additionalContext": msg,
        })
    return CheckResult.advisory(msg, hook_specific_output={
        "hookEventName": ctx.input.hook_event_name,
        "additionalContext": msg,
    })
