from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fettle.quality_ratchet import verify_coverage


def _coverage(*, covered_lines=31, statements=40, covered_branches=69, branches=100):
    combined_total = statements + branches
    combined = 100 * (covered_lines + covered_branches) / combined_total if combined_total else 0
    branch = 100 * covered_branches / branches if branches else 0
    return {
        "meta": {"branch_coverage": True, "format": 3},
        "files": {"fettle/example.py": {}},
        "totals": {
            "covered_lines": covered_lines,
            "num_statements": statements,
            "covered_branches": covered_branches,
            "num_branches": branches,
            "percent_covered": combined,
            "percent_branches_covered": branch,
        },
    }


def _policy(tmp_path: Path) -> Path:
    path = tmp_path / "quality-ratchet.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "types": {
            "critical_paths": ["critical.py"],
            "whole_source": "whole",
            "advisory_baseline": {"errors": 214, "files": 36},
        },
        "coverage": {"combined_floor": 65.0, "branch_floor": 69.0},
    }))
    return path


def _run_cli(tmp_path: Path, *args: str, path: str | None = None):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [sys.executable, "-m", "fettle.quality_ratchet", *args],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )


def _fake_mypy(tmp_path: Path, body: str) -> str:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    executable = bindir / "mypy"
    executable.write_text("#!/bin/sh\n" + body)
    executable.chmod(0o755)
    return f"{bindir}:{os.environ.get('PATH', '')}"


def test_coverage_accepts_exact_branch_threshold(tmp_path: Path):
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps(_coverage()))

    result = verify_coverage(report, combined_floor=65.0, branch_floor=69.0)

    assert result["passed"] is True
    assert result["combined"]["covered"] == 100
    assert result["combined"]["total"] == 140
    assert result["combined"]["percent"] == pytest.approx(71.42857)
    assert result["branch"]["covered"] == 69
    assert result["branch"]["total"] == 100
    assert result["branch"]["percent"] == 69.0


def test_coverage_rejects_unrounded_value_below_branch_threshold(tmp_path: Path):
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps(_coverage(covered_branches=6899, branches=10000)))

    result = verify_coverage(report, combined_floor=65.0, branch_floor=69.0)

    assert result["passed"] is False
    assert result["branch"]["percent"] == pytest.approx(68.99)
    assert "branch coverage" in result["errors"][0]


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"meta": {"branch_coverage": True}, "files": {"x.py": {}}}, "totals"),
        ({"meta": {"branch_coverage": True}, "files": {}, "totals": {}}, "unexpectedly empty"),
        (_coverage(statements=0, covered_lines=0), "statement count"),
        (_coverage(branches=0, covered_branches=0), "branch count"),
        (_coverage(covered_branches=101), "covered_branches"),
    ],
)
def test_coverage_rejects_missing_malformed_or_empty_evidence(tmp_path: Path, payload, message):
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps(payload))

    result = verify_coverage(report, combined_floor=65.0, branch_floor=69.0)

    assert result["passed"] is False
    assert message in " ".join(result["errors"])


def test_coverage_rejects_combined_and_branch_floors_independently(tmp_path: Path):
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps(_coverage(covered_lines=0, statements=100, covered_branches=69)))
    combined_failure = verify_coverage(report, combined_floor=65.0, branch_floor=69.0)

    report.write_text(json.dumps(_coverage(covered_lines=100, statements=100, covered_branches=68)))
    branch_failure = verify_coverage(report, combined_floor=65.0, branch_floor=69.0)

    assert combined_failure["passed"] is False
    assert combined_failure["branch"]["percent"] == 69.0
    assert "combined coverage" in combined_failure["errors"][0]
    assert branch_failure["passed"] is False
    assert branch_failure["combined"]["percent"] > 65.0
    assert "branch coverage" in branch_failure["errors"][0]


@pytest.mark.parametrize("field", ["percent_covered", "percent_branches_covered"])
def test_coverage_cli_rejects_contradictory_percentages(tmp_path: Path, field: str):
    policy = _policy(tmp_path)
    payload = _coverage()
    payload["totals"][field] = 99.0
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps(payload))

    result = _run_cli(tmp_path, "coverage", "--policy", str(policy), "--report", str(report))

    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "invalid"


def test_type_cli_blocks_critical_error_but_keeps_whole_source_debt_advisory(tmp_path: Path):
    policy = _policy(tmp_path)
    path = _fake_mypy(tmp_path, "case \"$*\" in *critical.py*) echo 'critical.py:1: error: seeded'; echo 'Found 1 error in 1 file'; exit 1;; *) echo 'Found 214 errors in 36 files'; exit 1;; esac\n")

    result = _run_cli(tmp_path, "types", "--policy", str(policy), path=path)

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["critical"]["status"] == "failed"
    assert payload["critical"]["errors"] == 1
    assert payload["whole_source"]["status"] == "advisory"
    assert payload["whole_source"]["errors"] == 214
    assert payload["whole_source"]["files"] == 36


def test_type_cli_passes_clean_critical_scope_with_advisory_debt(tmp_path: Path):
    policy = _policy(tmp_path)
    path = _fake_mypy(tmp_path, "case \"$*\" in *critical.py*) echo 'Success: no issues found in 1 source file'; exit 0;; *) echo 'Found 214 errors in 36 files'; exit 1;; esac\n")

    result = _run_cli(tmp_path, "types", "--policy", str(policy), path=path)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["passed"] is True
    assert payload["whole_source"]["status"] == "advisory"
    assert payload["whole_source"]["baseline"] == {"errors": 214, "files": 36}


def test_type_cli_reports_unavailable_whole_source_measurement_without_zeroing_it(tmp_path: Path):
    policy = _policy(tmp_path)
    path = _fake_mypy(tmp_path, "case \"$*\" in *critical.py*) echo 'Success: no issues found in 1 source file'; exit 0;; *) echo 'checker crashed' >&2; exit 2;; esac\n")

    result = _run_cli(tmp_path, "types", "--policy", str(policy), path=path)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["whole_source"]["status"] == "unavailable"
    assert payload["whole_source"]["errors"] is None
    assert payload["whole_source"]["files"] is None


def test_critical_type_failure_blocks_when_whole_source_measurement_is_unavailable(
    tmp_path: Path,
):
    policy = _policy(tmp_path)
    counter = tmp_path / "counter"
    path = _fake_mypy(tmp_path, f"if [ ! -f '{counter}' ]; then touch '{counter}'; echo 'critical.py:1: error: seeded'; echo 'Found 1 error in 1 file'; exit 1; fi; echo 'checker crashed' >&2; exit 2\n")

    result = _run_cli(tmp_path, "types", "--policy", str(policy), path=path)

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["passed"] is False
    assert payload["critical"]["status"] == "failed"
    assert payload["whole_source"]["status"] == "unavailable"


def test_type_cli_rejects_missing_checker(tmp_path: Path):
    policy = _policy(tmp_path)

    result = _run_cli(tmp_path, "types", "--policy", str(policy), path=str(tmp_path / "empty"))

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["critical"]["status"] == "unavailable"
    assert payload["passed"] is False


@pytest.mark.parametrize("floor", ["69", 0])
def test_cli_rejects_malformed_policy(tmp_path: Path, floor):
    policy = _policy(tmp_path)
    payload = json.loads(policy.read_text())
    payload["coverage"]["branch_floor"] = floor
    policy.write_text(json.dumps(payload))

    result = _run_cli(tmp_path, "types", "--policy", str(policy))

    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "invalid"
