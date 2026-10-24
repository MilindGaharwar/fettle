"""Fail-closed CI type and coverage ratchets shared by CI and release."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


_MYPY_SUMMARY = re.compile(r"Found (\d+) errors? in (\d+) files?")


class EvidenceError(ValueError):
    """Required ratchet evidence is unavailable or invalid."""


def _number(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvidenceError(f"{name} must be a non-negative integer")
    return value


def _percent(covered: int, total: int) -> float:
    return covered * 100.0 / total


def _reported_percent(totals: dict[str, Any], name: str, calculated: float) -> None:
    if name not in totals:
        return
    value = totals[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{name} must be numeric")
    reported = float(value)
    if not math.isfinite(reported) or not math.isclose(
        reported, calculated, rel_tol=0.0, abs_tol=1e-9,
    ):
        raise EvidenceError(
            f"{name} contradicts integer counts: reported {reported}, calculated {calculated}"
        )


def verify_coverage(
    report_path: Path,
    *,
    combined_floor: float,
    branch_floor: float,
) -> dict[str, Any]:
    """Validate coverage.py JSON and enforce independent combined/branch floors."""
    try:
        report = json.loads(report_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return {"passed": False, "status": "invalid", "errors": [f"coverage report unavailable: {exc}"]}
    try:
        if not isinstance(report, dict):
            raise EvidenceError("coverage report must be an object")
        meta = report.get("meta")
        if not isinstance(meta, dict) or meta.get("branch_coverage") is not True:
            raise EvidenceError("coverage report does not confirm branch measurement")
        files = report.get("files")
        if not isinstance(files, dict) or not files:
            raise EvidenceError("coverage file evidence is unexpectedly empty")
        totals = report.get("totals")
        if not isinstance(totals, dict):
            raise EvidenceError("coverage totals are missing or malformed")
        covered_lines = _number(totals.get("covered_lines"), "covered_lines")
        statements = _number(totals.get("num_statements"), "statement count")
        covered_branches = _number(totals.get("covered_branches"), "covered_branches")
        branches = _number(totals.get("num_branches"), "branch count")
        if statements == 0:
            raise EvidenceError("statement count must be greater than zero")
        if branches == 0:
            raise EvidenceError("branch count must be greater than zero")
        if covered_lines > statements:
            raise EvidenceError("covered_lines exceeds statement count")
        if covered_branches > branches:
            raise EvidenceError("covered_branches exceeds branch count")
        combined_covered = covered_lines + covered_branches
        combined_total = statements + branches
        combined_percent = _percent(combined_covered, combined_total)
        branch_percent = _percent(covered_branches, branches)
        _reported_percent(totals, "percent_covered", combined_percent)
        _reported_percent(totals, "percent_branches_covered", branch_percent)
    except EvidenceError as exc:
        return {"passed": False, "status": "invalid", "errors": [str(exc)]}

    errors = []
    if combined_percent < combined_floor:
        errors.append(
            f"combined coverage {combined_percent:.6f}% is below {combined_floor:.1f}%"
        )
    if branch_percent < branch_floor:
        errors.append(f"branch coverage {branch_percent:.6f}% is below {branch_floor:.1f}%")
    return {
        "passed": not errors,
        "status": "pass" if not errors else "failed",
        "combined": {
            "covered": combined_covered,
            "total": combined_total,
            "percent": combined_percent,
            "floor": combined_floor,
        },
        "branch": {
            "covered": covered_branches,
            "total": branches,
            "percent": branch_percent,
            "floor": branch_floor,
        },
        "subprocess_coverage": {
            "enabled": True,
            "limitation": (
                "Coverage captures Python subprocesses started through coverage.py; "
                "non-Python processes, exec patterns unsupported by coverage.py, and "
                "abruptly terminated children may remain unobserved."
            ),
        },
        "errors": errors,
    }


def _run_mypy(scope: list[str]) -> subprocess.CompletedProcess[str] | None:
    executable = shutil.which("mypy")
    if executable is None:
        return None
    try:
        return subprocess.run(
            [executable, "--follow-imports=silent", "--ignore-missing-imports", *scope],
            capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _mypy_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())


def verify_types(policy: dict[str, Any]) -> dict[str, Any]:
    """Enforce zero errors in critical files and retain whole-source debt as advisory."""
    config = policy["types"]
    critical_paths = config["critical_paths"]
    baseline = config["advisory_baseline"]
    critical_result = _run_mypy(critical_paths)
    if critical_result is None:
        critical: dict[str, Any] = {
            "status": "unavailable", "errors": None, "files": None,
        }
    elif critical_result.returncode == 0:
        critical = {"status": "pass", "errors": 0, "files": 0}
    else:
        match = _MYPY_SUMMARY.search(_mypy_output(critical_result))
        critical = {
            "status": "failed" if critical_result.returncode == 1 and match else "unavailable",
            "errors": int(match.group(1)) if match else None,
            "files": int(match.group(2)) if match else None,
            "detail": _mypy_output(critical_result),
        }

    whole_result = _run_mypy([config["whole_source"]])
    if whole_result is None:
        whole = {"status": "unavailable", "errors": None, "files": None, "baseline": baseline}
    elif whole_result.returncode == 0:
        whole = {"status": "advisory", "errors": 0, "files": 0, "baseline": baseline}
    elif whole_result.returncode == 1:
        match = _MYPY_SUMMARY.search(_mypy_output(whole_result))
        whole = (
            {
                "status": "advisory",
                "errors": int(match.group(1)),
                "files": int(match.group(2)),
                "baseline": baseline,
            }
            if match else
            {"status": "unavailable", "errors": None, "files": None, "baseline": baseline}
        )
    else:
        whole = {"status": "unavailable", "errors": None, "files": None, "baseline": baseline}
    return {
        "passed": critical["status"] == "pass",
        "critical": critical,
        "whole_source": whole,
    }


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        policy = json.loads(path.read_text())
        types = policy["types"]
        coverage = policy["coverage"]
        critical_paths = types["critical_paths"]
        baseline = types["advisory_baseline"]
        combined_floor = coverage["combined_floor"]
        branch_floor = coverage["branch_floor"]
        if (
            policy.get("schema_version") != 1
            or not isinstance(critical_paths, list)
            or not critical_paths
            or not all(isinstance(item, str) and item for item in critical_paths)
            or not isinstance(types["whole_source"], str)
            or not types["whole_source"]
            or not isinstance(baseline, dict)
            or any(
                isinstance(baseline.get(name), bool)
                or not isinstance(baseline.get(name), int)
                or baseline[name] < 0
                for name in ("errors", "files")
            )
            or isinstance(combined_floor, bool)
            or not isinstance(combined_floor, (int, float))
            or not math.isfinite(float(combined_floor))
            or not 0 < float(combined_floor) <= 100
            or isinstance(branch_floor, bool)
            or not isinstance(branch_floor, (int, float))
            or not math.isfinite(float(branch_floor))
            or not 0 < float(branch_floor) <= 100
        ):
            raise EvidenceError("policy shape is invalid")
        return policy
    except (OSError, json.JSONDecodeError, KeyError, TypeError, EvidenceError) as exc:
        raise EvidenceError(f"quality ratchet policy is invalid: {exc}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("types", "coverage"):
        command = subparsers.add_parser(name)
        command.add_argument("--policy", type=Path, required=True)
        if name == "coverage":
            command.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        policy = _load_policy(args.policy)
        if args.command == "types":
            result = verify_types(policy)
        else:
            result = verify_coverage(
                args.report,
                combined_floor=float(policy["coverage"]["combined_floor"]),
                branch_floor=float(policy["coverage"]["branch_floor"]),
            )
    except EvidenceError as exc:
        result = {"passed": False, "status": "invalid", "errors": [str(exc)]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("passed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
