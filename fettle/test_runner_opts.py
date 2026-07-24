"""Fettle v0.5.0 — WP-88+89: Last-failed + parallel test execution.

Build pytest arguments with failure-first and parallel support.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def has_xdist() -> bool:
    """Check if pytest-xdist is available."""
    return importlib.util.find_spec("xdist") is not None


def record_failures(history_path: str, failed_tests: list[str]) -> None:
    """Record failed test IDs to history file."""
    Path(history_path).write_text(json.dumps(failed_tests))


def get_last_failures(history_path: str) -> list[str]:
    """Load last failed test IDs from history."""
    p = Path(history_path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def build_pytest_args(
    mode: str = "full",
    files: list[str] | None = None,
    failure_history: str | None = None,
    parallel: bool = False,
) -> list[str]:
    """Build pytest command arguments based on mode and options."""
    args = ["-q", "--tb=short"]

    # Last-failed / failures-first
    if failure_history:
        failures = get_last_failures(failure_history)
        if failures:
            if mode == "changed":
                args.append("--lf")
            else:
                args.append("--ff")

    # Parallel execution
    if parallel and has_xdist():
        args.extend(["-n", "auto"])

    # File scoping
    if files:
        args.extend(files)

    return args
