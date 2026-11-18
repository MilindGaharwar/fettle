"""Test-count evidence for truthful verification results."""

from __future__ import annotations

import shlex
import xml.etree.ElementTree as ET
from pathlib import Path

from fettle.evidence import ResultState


def invokes_pytest(argv: list[str]) -> bool:
    """Return whether an argument vector invokes pytest."""
    if not argv:
        return False
    if Path(argv[0]).name in {"pytest", "py.test"}:
        return True
    if any(
        argv[index:index + 2] == ["-m", "pytest"] for index in range(len(argv) - 1)
    ):
        return True
    return any(
        argv[index:index + 2] in (["run", "pytest"], ["run", "py.test"])
        for index in range(len(argv) - 1)
    )


def prepare_test_command(
    command: str,
    *,
    cwd: str,
    report: str = "",
) -> tuple[list[str], Path | None]:
    """Return argv and the JUnit report that will establish test counts."""
    argv = shlex.split(command)
    if invokes_pytest(argv):
        existing = next((arg.split("=", 1)[1] for arg in argv if arg.startswith("--junitxml=")), "")
        path = Path(existing) if existing else Path(cwd) / ".fettle" / "verify-junit.xml"
        if not existing:
            argv.append(f"--junitxml={path}")
        return argv, path if path.is_absolute() else Path(cwd) / path
    if report:
        path = Path(report)
        return argv, path if path.is_absolute() else Path(cwd) / path
    return argv, None


def read_junit_counts(path: Path | None) -> dict[str, int] | None:
    """Parse bounded JUnit summary counts. Missing or malformed reports are unknown."""
    if path is None or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        return None
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        return None
    try:
        collected = sum(int(suite.get("tests", "0")) for suite in suites)
        failed = sum(int(suite.get("failures", "0")) for suite in suites)
        errors = sum(int(suite.get("errors", "0")) for suite in suites)
        skipped = sum(int(suite.get("skipped", "0")) for suite in suites)
    except ValueError:
        return None
    if min(collected, failed, errors, skipped) < 0 or failed + errors + skipped > collected:
        return None
    executed = collected - skipped
    return {
        "collected": collected,
        "executed": executed,
        "passed": collected - failed - errors - skipped,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
    }


def report_identity(path: Path | None) -> tuple[int, int] | None:
    """Identify one report generation without reading or deleting user data."""
    if path is None:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def portable_argv(argv: list[str], *, cwd: str) -> list[str]:
    """Project an executed argv into portable, non-escaping evidence."""
    root = Path(cwd).resolve()
    projected: list[str] = []
    for index, arg in enumerate(argv):
        if arg.startswith("--junitxml="):
            projected.append("--junitxml=.fettle/verify-junit.xml")
            continue
        path = Path(arg)
        if not path.is_absolute():
            projected.append(arg)
            continue
        try:
            projected.append(path.resolve().relative_to(root).as_posix())
        except ValueError:
            projected.append(path.name if index == 0 else f"<external>/{path.name}")
    return projected


def classify_test_result(
    returncode: int,
    counts: dict[str, int] | None,
) -> tuple[ResultState, str]:
    """Classify one completed test command without inferring execution."""
    if returncode != 0:
        return ResultState.VIOLATION, ""
    if counts is None:
        return (
            ResultState.UNKNOWN,
            "the test command exited 0 but no test count is available. "
            "Set [gates.verify] report to a JUnit XML path.",
        )
    if counts["failed"] or counts["errors"]:
        return (
            ResultState.VIOLATION,
            f"test report records {counts['failed']} failure(s) and {counts['errors']} error(s)",
        )
    if counts["executed"] == 0:
        return (
            ResultState.VIOLATION,
            f"no tests executed (collected {counts['collected']}, skipped {counts['skipped']})",
        )
    return ResultState.PASS, ""
