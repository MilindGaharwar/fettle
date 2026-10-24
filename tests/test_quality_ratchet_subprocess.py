from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_coverage_ratchet_accepts_and_rejects_in_instrumented_python_subprocess(
    tmp_path: Path,
):
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({
        "schema_version": 1,
        "types": {
            "critical_paths": ["fettle/config.py"],
            "whole_source": "fettle",
            "advisory_baseline": {"errors": 214, "files": 36},
        },
        "coverage": {"combined_floor": 65.0, "branch_floor": 69.0},
    }))
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps({
        "meta": {"branch_coverage": True, "format": 3},
        "files": {"fettle/config.py": {}},
        "totals": {
            "covered_lines": 65,
            "num_statements": 100,
            "covered_branches": 69,
            "num_branches": 100,
            "percent_covered": 67.0,
            "percent_branches_covered": 69.0,
        },
    }))

    accepted = subprocess.run(
        [
            sys.executable, "-m", "fettle.quality_ratchet", "coverage",
            "--policy", str(policy), "--report", str(report),
        ],
        env=os.environ.copy(), capture_output=True, text=True,
    )

    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout)["passed"] is True

    payload = json.loads(report.read_text())
    payload["totals"]["covered_branches"] = 68
    payload["totals"]["percent_covered"] = 66.5
    payload["totals"]["percent_branches_covered"] = 68.0
    report.write_text(json.dumps(payload))
    rejected = subprocess.run(
        [
            sys.executable, "-m", "fettle.quality_ratchet", "coverage",
            "--policy", str(policy), "--report", str(report),
        ],
        env=os.environ.copy(), capture_output=True, text=True,
    )

    assert rejected.returncode == 2, rejected.stderr
    assert json.loads(rejected.stdout)["branch"]["percent"] == 68.0
