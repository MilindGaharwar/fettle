"""`fettle ci` — composed gate + generated workflow (CI enforcement WP-2)."""

import os
import hashlib
import shutil
import subprocess
import sys
import tempfile
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import yaml
import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PLUGIN_DIR))

from fettle import ci  # noqa: E402
from fettle.quality_scan import ToolScanResult  # noqa: E402
from fettle.result import ResultStatus  # noqa: E402
from scripts.staged_preflight import (  # noqa: E402
    WAVES,
    calibration_observer_contract,
    calibration_stage_3_observer_contract,
    combine_accounting,
)

SYNTH_AWS = "AKIAZ7Q3M5N8P2K4R6T9"


def _run_actions_bash(script, *, cwd, env):
    env = {key: value for key, value in env.items() if value is not None}
    return subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


def _python_heredoc(script):
    marker = "python - <<'PY'\n"
    return script.split(marker, 1)[1].split("\nPY", 1)[0]


def _first_python_heredoc(script):
    return script.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]


def _python_heredoc_containing(script, needle):
    heredocs = script.split("<<'PY'\n")[1:]
    matches = [heredoc.split("\nPY", 1)[0] for heredoc in heredocs if needle in heredoc]
    assert len(matches) == 1
    return matches[0]


def _workflow_step_script(job_name, step_name):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    return next(
        step["run"] for step in workflow["jobs"][job_name]["steps"]
        if step.get("name") == step_name
    )


def _workflow_step(job_name, step_name):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    return next(
        step for step in workflow["jobs"][job_name]["steps"]
        if step.get("name") == step_name
    )


def test_capacity_validation_route_is_registered_dormant_and_isolated():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    dispatch = workflow[True]["workflow_dispatch"]["inputs"]
    jobs = workflow["jobs"]

    assert "capacity-validation" in dispatch["mode"]["options"]
    assert dispatch["capacity_stage"]["options"] == ["prepare", "execute", "readback"]
    capacity_jobs = {name: job for name, job in jobs.items() if name.startswith("capacity-")}
    assert capacity_jobs
    for job in capacity_jobs.values():
        assert "capacity-validation" in job["if"]
    for name in ("prepare", "calibration-launch-gate", "full-shard", "aggregate"):
        assert "mode != 'capacity-validation'" in jobs[name]["if"]
    assert "mode != 'capacity-validation'" in jobs["evidence-readback"]["if"]


def test_capacity_validation_measurement_batches_are_exact_once_and_bounded():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    jobs = workflow["jobs"]
    expected = {
        "capacity-batch-1": [0, 1, 2, 3],
        "capacity-batch-2": [4, 5, 6, 7],
        "capacity-batch-3": [8, 9, 10, 11],
    }
    selected = []
    for name, indexes in expected.items():
        job = jobs[name]
        assert job["strategy"]["fail-fast"] is False
        assert job["strategy"]["max-parallel"] == 4
        assert job["strategy"]["matrix"]["unit"] == indexes
        assert job["uses"] == "./.github/workflows/mutation-capacity-validation-unit.yml"
        assert job["with"]["unit"] == "${{ matrix.unit }}"
        selected.extend(indexes)
    assert selected == list(range(12))
    assert jobs["capacity-batch-1"]["needs"] == "capacity-execute-admission"
    assert jobs["capacity-batch-2"]["needs"] == "capacity-admit-2"
    assert jobs["capacity-batch-3"]["needs"] == "capacity-admit-3"
    assert jobs["capacity-readback"]["needs"] == [
        "capacity-batch-1", "capacity-batch-2", "capacity-batch-3",
        "capacity-measurement-monitor",
    ]
    assert jobs["capacity-measurement-monitor"]["needs"] == "capacity-execute-admission"
    assert jobs["capacity-measurement-monitor"]["uses"] == (
        "./.github/workflows/mutation-capacity-measurement-monitor.yml"
    )
    assert jobs["capacity-measurement-monitor"]["permissions"] == {
        "actions": "write", "contents": "read",
    }


def test_capacity_preparation_batches_are_sequential_exact_once_and_reserved():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    jobs = workflow["jobs"]
    selected = []
    for batch in range(1, 17):
        worker = jobs[f"capacity-enumerate-{batch}"]
        gate = jobs[f"capacity-preparation-admit-{batch}"]
        indexes = list(range((batch - 1) * 16, batch * 16))
        selected.extend(worker["strategy"]["matrix"]["shard"])
        assert worker["strategy"]["matrix"]["shard"] == indexes
        assert worker["strategy"]["max-parallel"] == 16
        assert worker["uses"] == "./.github/workflows/mutation-capacity-preparation-unit.yml"
        assert worker["needs"] == (
            "capacity-preparation-admit-0" if batch == 1
            else f"capacity-preparation-admit-{batch - 1}"
        )
        assert gate["needs"] == f"capacity-enumerate-{batch}"
        assert gate["uses"] == "./.github/workflows/mutation-capacity-preparation-gate.yml"
        assert gate["with"]["authorization_id"] == "AH-UNTIMED-DIAGNOSTIC-20261018-A"
        assert worker["with"]["authorization_id"] == "AH-UNTIMED-DIAGNOSTIC-20261018-A"
        assert json.loads(gate["with"]["admitted_shards"]) == list(range(batch * 16))
        assert json.loads(gate["with"]["next_shards"]) == (
            list(range(batch * 16, min(256, (batch + 1) * 16)))
        )
    assert selected == list(range(256))
    initial = jobs["capacity-preparation-admit-0"]
    assert initial["needs"] == "capacity-prepare"
    assert json.loads(initial["with"]["admitted_shards"]) == []
    assert json.loads(initial["with"]["next_shards"]) == list(range(16))
    assert jobs["capacity-freeze-plan"]["needs"] == [
        "capacity-prepare", "capacity-preparation-admit-16",
        "capacity-preparation-monitor",
    ]
    assert jobs["capacity-preparation-monitor"]["needs"] == "capacity-preparation-admit-0"
    assert jobs["capacity-preparation-monitor"]["uses"] == (
        "./.github/workflows/mutation-capacity-preparation-monitor.yml"
    )
    assert jobs["capacity-preparation-monitor"]["permissions"] == {
        "actions": "write", "contents": "read",
    }
    assert jobs["capacity-preparation-monitor"]["with"]["authorization_id"] == (
        "AH-UNTIMED-DIAGNOSTIC-20261018-A"
    )


def test_capacity_preparation_reusable_workflows_enforce_deadlines_and_provider_accounting():
    root = Path(PLUGIN_DIR) / ".github/workflows"
    worker = yaml.safe_load((root / "mutation-capacity-preparation-unit.yml").read_text())
    gate = yaml.safe_load((root / "mutation-capacity-preparation-gate.yml").read_text())
    monitor = yaml.safe_load((root / "mutation-capacity-preparation-monitor.yml").read_text())
    worker_job = worker["jobs"]["enumerate"]
    gate_job = gate["jobs"]["gate"]
    gate_scripts = "\n".join(step.get("run", "") for step in gate_job["steps"])

    assert worker["permissions"] == {"actions": "read", "contents": "read"}
    assert worker_job["timeout-minutes"] == 35
    assert gate["permissions"] == {"actions": "read", "contents": "read"}
    assert gate_job["timeout-minutes"] == 5
    assert "collect-stable-jobs" in gate_scripts
    assert "attempts/$GITHUB_RUN_ATTEMPT/jobs" in gate_scripts
    assert "account_runner_minutes" in gate_scripts
    assert "evaluate_capacity_preparation_admission" in gate_scripts
    assert "datetime.now(UTC)" in gate_scripts
    assert "AH-CAPACITY-BOUNDED-20261016-A" not in gate_scripts
    monitor_job = monitor["jobs"]["monitor"]
    monitor_scripts = "\n".join(step.get("run", "") for step in monitor_job["steps"])
    assert monitor["permissions"] == {"actions": "write", "contents": "read"}
    assert monitor_job["timeout-minutes"] == 100
    assert "evaluate_capacity_preparation_admission" in monitor_scripts
    assert "enumeration worker appeared before admission" in monitor_scripts
    assert "actions/runs/$GITHUB_RUN_ID/cancel" in monitor_scripts
    assert "all 256 enumeration workers are terminal-success" in monitor_scripts
    assert "collect-stable-jobs" in monitor_scripts
    assert "AH-CAPACITY-BOUNDED-20261016-A" not in monitor_scripts


def test_capacity_measurement_monitor_is_bounded_exact_once_and_cancels_after_retention():
    path = Path(PLUGIN_DIR) / ".github/workflows/mutation-capacity-measurement-monitor.yml"
    workflow = yaml.safe_load(path.read_text())
    job = workflow["jobs"]["monitor"]
    scripts = "\n".join(step.get("run", "") for step in job["steps"])
    artifact_index = next(
        index for index, step in enumerate(job["steps"])
        if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    cancel_index = next(
        index for index, step in enumerate(job["steps"])
        if "actions/runs/$GITHUB_RUN_ID/cancel" in step.get("run", "")
    )

    assert workflow["permissions"] == {"actions": "write", "contents": "read"}
    assert job["timeout-minutes"] == 30
    assert "collect-stable-jobs" in scripts
    assert "validate_capacity_authorization" in scripts
    assert "AH-CAPACITY-BOUNDED-20261016-A" not in scripts
    assert "measurement worker appeared before admission" in scripts
    assert "len(observed) != len(set(observed))" in scripts
    assert "all 12 measurement workers are terminal-success" in scripts
    assert artifact_index < cancel_index


def test_capacity_validation_worker_has_containment_and_non_authoritative_namespace():
    path = Path(PLUGIN_DIR) / ".github/workflows/mutation-capacity-validation-unit.yml"
    workflow = yaml.safe_load(path.read_text())
    job = workflow["jobs"]["execute"]
    steps = {step.get("name", step.get("uses")): step for step in job["steps"]}

    assert workflow["permissions"] == {"actions": "read", "contents": "read"}
    assert job["timeout-minutes"] == 20
    assert steps["Execute bounded capacity unit"]["timeout-minutes"] == 14
    command = steps["Execute bounded capacity unit"]["run"]
    assert "--timeout 720" in command
    assert "--capacity-unit ${{ inputs.unit }}" in command
    assert "--capacity-checkpoint capacity-validation-checkpoint.json" in command
    admission = steps["Reject reruns and bind candidate"]["run"]
    assert 'os.environ["RUN_ATTEMPT"]=="1"' in admission
    upload = steps["Retain non-authoritative capacity result"]
    assert upload["with"]["name"].startswith("capacity-validation-unit-")
    assert "mutation-checkpoint" not in path.read_text()
    assert "mutation-report" not in path.read_text()
    assert "calibration" not in upload["with"]["name"]
    isolate = steps["Isolate partial checkpoint from authoritative consumers"]["run"]
    assert '"kind": "capacity_validation_partial_checkpoint"' in isolate
    assert '"qualification_eligible": False' in isolate
    assert '"calibration_id"' not in isolate
    route = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    capacity_section = route.split("\n  capacity-prepare:", 1)[1].split(
        "\n  preflight-aggregate:", 1,
    )[0]
    assert "mutation-preflight.json" not in capacity_section
    assert "capacity-validation-corpus.json" in capacity_section
    assert '"qualification_eligible": False' in capacity_section


def test_capacity_validation_admission_scripts_reject_invalid_identity(tmp_path):
    script = _workflow_step_script(
        "capacity-execute-admission", "Validate immutable execution inputs",
    )
    valid = {
        "PATH": os.environ["PATH"],
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40,
        "CANDIDATE_SHA": "a" * 40, "EXPERIMENT_ID": "capval-local",
        "PREPARATION_RUN_ID": "123", "PLAN_SHA256": "b" * 64,
        "AUTHORIZATION_ID": "AH-UNTIMED-DIAGNOSTIC-20261018-A",
    }
    assert _run_actions_bash(script, cwd=tmp_path, env=valid).returncode == 0
    assert _run_actions_bash(
        script, cwd=tmp_path, env={**valid, "GITHUB_RUN_ATTEMPT": "2"},
    ).returncode == 2
    assert _run_actions_bash(
        script, cwd=tmp_path, env={**valid, "PLAN_SHA256": "bad"},
    ).returncode == 2
    assert _run_actions_bash(
        script, cwd=tmp_path,
        env={**valid, "AUTHORIZATION_ID": "AH-CAPACITY-BOUNDED-20261016-A"},
    ).returncode != 0


def test_capacity_validation_readback_keeps_ledgers_separate_and_non_passing():
    script = _workflow_step_script(
        "capacity-readback", "Preserve exact visible state and separate accounting authorities",
    )
    assert '"passed": False' in script
    assert '"qualification_eligible": False' in script
    assert '"worker"' in script and '"routine_support"' in script
    assert '"cancellation_controller"' in script
    assert script.count('"authority": "not_granted"') == 4
    assert script.count('"transferable": False') == 4


def test_capacity_validation_provider_readback_uses_terminal_exact_attempt_records():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    job = workflow["jobs"]["capacity-provider-readback"]
    scripts = "\n".join(step.get("run", "") for step in job["steps"])

    assert "capacity_stage == 'readback'" in job["if"]
    assert job["steps"][0]["uses"].startswith("actions/checkout@")
    assert "validate_capacity_authorization" in scripts
    assert "attempts/1/jobs" in scripts
    assert "collect-stable-jobs" in scripts
    upload = next(
        step for step in job["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    assert "capacity-execution-collection.json" in upload["with"]["path"]
    assert "capacity-execution-collection-attempts" in upload["with"]["path"]
    assert "capacity-validation-execution-source-$EXECUTION_RUN_ID" in scripts
    assert "capacity-validation-unit-$EXECUTION_RUN_ID-*" in scripts
    assert "capacity-validation-preparation-${{ github.event.inputs.capacity_preparation_run_id }}" in scripts
    assert "reconcile_capacity_provider_accounting" in scripts
    assert "evaluate_capacity_validation_decision" in scripts
    assert "load_capacity_validation_plan" in scripts
    assert "validate_capacity_validation_results" in scripts
    assert '"outcome": "inconclusive"' in scripts
    assert "capacity-validation-model-decision.json" in scripts
    assert 'ledger["status"] != "completed"' in scripts


def _retention_probe_step_script(job_name, step_name):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/calibration-retention-probe.yml").read_text()
    )
    return next(
        step["run"] for step in workflow["jobs"][job_name]["steps"]
        if step.get("name") == step_name
    )


def _calibration_jobs(run_id="700", attempt="1", shards=(8, 27, 28, 37, 48, 50, 51, 53)):
    started = "2026-10-10T01:00:00Z"
    completed = "2026-10-10T01:01:00Z"
    jobs = []
    for job_id, shard in enumerate(shards, 1):
        jobs.append({
            "id": job_id,
            "run_id": int(run_id),
            "run_attempt": int(attempt),
            "name": f"mutation (full shard {shard}, advisory)",
            "status": "completed",
            "conclusion": "success",
            "created_at": started,
            "started_at": started,
            "completed_at": completed,
            "runner_id": 1000 + job_id,
            "runner_name": f"runner-{job_id}",
            "runner_group_id": 1,
            "runner_group_name": "GitHub Actions",
            "steps": [{"name": "worker", "status": "completed", "conclusion": "success"}],
        })
    return [{"total_count": len(jobs), "jobs": jobs}]


def _write_gh_jobs_stub(workspace, jobs, predecessor=None):
    workspace.mkdir(parents=True, exist_ok=True)
    jobs_path = workspace / "provider-jobs.json"
    jobs_path.write_text(json.dumps(jobs))
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    predecessor_path = workspace / "provider-accounting.json"
    if predecessor is not None:
        predecessor_path.write_text(json.dumps(predecessor))
    gh.write_text(
        "#!/bin/sh\n"
        f"jobs={jobs_path}\n"
        f"accounting={predecessor_path}\n"
        "if [ \"$1\" = api ]; then cat \"$jobs\"; exit 0; fi\n"
        "if [ \"$1 $2\" = 'run download' ]; then\n"
        "  shift 2; dest=\n"
        "  while [ $# -gt 0 ]; do\n"
        "    if [ \"$1\" = --dir ]; then dest=$2; shift 2; else shift; fi\n"
        "  done\n"
        "  test -n \"$dest\" && test -f \"$accounting\" || exit 1\n"
        "  mkdir -p \"$dest\"\n"
        "  cp \"$accounting\" \"$dest/calibration-accounting.json\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n"
    )
    gh.chmod(0o755)
    return bin_dir


def _operational_source(run_id, minutes):
    return {
        "schema_version": "1",
        "kind": "operational_runner_time_estimate",
        "billing_authority": False,
        "expected_run_id": str(run_id),
        "expected_run_attempt": "1",
        "estimated_runner_minutes": minutes,
        "charged_runner_minutes": minutes,
        "included_jobs": [],
    }


def _complete_calibration_lifecycle(stage, expected_shards):
    contract = (
        __import__("fettle.staged_preflight", fromlist=["calibration_stage_3_observer_contract"])
        .calibration_stage_3_observer_contract(expected_shards)
        if str(stage) == "3"
        else calibration_observer_contract(
            len(expected_shards), 8 if str(stage) == "1" else 16,
            expected_shards=expected_shards,
        )
    )
    return {
        "schema_version": "1", "kind": "calibration_observer_sample",
        "passed": True, "billing_authority": False, "completion_guaranteed": False,
        "elapsed_seconds": 1, "expected_workers": len(expected_shards),
        "expected_shards": list(expected_shards), "admitted_shards": list(expected_shards),
        "observed_worker_jobs": len(expected_shards),
        "terminal_workers": len(expected_shards), "terminal_shards": list(expected_shards),
        "missing_terminal_shards": [], "pending_admission_shards": [],
        "completed_admissions": contract["admission_dependencies"],
        "expected_admissions": contract["admission_dependencies"],
        "route_complete": True, "action": "complete",
        "reason": "all admitted workers are terminal", "contract": contract,
    }


def _cumulative_accounting(*, stage, run_ids, estimated, charged=None):
    charged = estimated if charged is None else charged
    support_bounds = {
        "mutation (calibration accounting)": 15,
        "mutation (assemble evidence)": 30,
        "mutation evidence": 10,
    }
    expected_shards = [WAVES.get(f"wave-{stage}", [8])[0]]
    included_jobs = [
        *[
            {"name": name, "status": "completed", "minutes": bound}
            for name, bound in support_bounds.items()
        ],
        *([{
        "name": "worker", "status": "in_progress", "minutes": 1,
        "basis": "elapsed through observation time", "execution_evidence": "confirmed",
    }] if charged > estimated else []),
    ]
    sources = [_operational_source(run_id, estimated / len(run_ids)) for run_id in run_ids]
    sources[-1]["included_jobs"] = included_jobs
    lifecycle = _complete_calibration_lifecycle(stage, expected_shards)
    return {
        "schema_version": "1",
        "kind": "calibration_budget_decision",
        "billing_authority": False,
        "stage": str(stage),
        "calibration_id": "cal-test",
        "ceiling": 12000,
        "estimated_runner_minutes": estimated,
        "charged_runner_minutes": charged,
        "sources": sources,
        "included_jobs": included_jobs,
        "source_lineage": [
            {"run_id": str(run_id), "run_attempt": "1"} for run_id in run_ids
        ],
        "monitor_floor_runner_minutes": estimated,
        "bounded_support_reserve_minutes": 0,
        "bounded_support_reservations": [
            {"name": name, "bound_minutes": bound,
             "already_observed_minutes": float(bound), "reserved_minutes": 0.0}
            for name, bound in support_bounds.items()
        ],
        "cancellation_reserve": 1200,
        "launch_cutoff": 10800,
        "active_jobs": int((charged - estimated) / 5),
        "cancellation_lag_minutes_per_active_job": 5,
        "cancellation_lag_charge": charged - estimated,
        "observer_evidence": {"lifecycle": lifecycle},
        "passed": True,
    }


def _git_repo(files: dict) -> str:
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    for name, content in files.items():
        path = os.path.join(d, name)
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(name) else None
        with open(path, "w") as f:
            f.write(content)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    return d


def test_run_ci_clean_repo_passes():
    d = _git_repo({"a.py": "x = 1\n"})
    result = ci.run_ci(d)
    assert result["ok"] is True
    assert any(g["name"] == "boundary" and g["ok"] for g in result["gates"])


def test_run_ci_planted_secret_fails():
    d = _git_repo({"leak.py": f'k = "{SYNTH_AWS}"\n'})
    result = ci.run_ci(d)
    assert result["ok"] is False
    boundary = next(g for g in result["gates"] if g["name"] == "boundary")
    assert boundary["ok"] is False
    assert boundary["findings"]  # the secret is surfaced


def test_run_ci_changed_spec_without_audit_fails():
    d = _git_repo({
        ".fettle.toml": "[gates.spec_audit]\nenabled = true\n",
        "docs/PRODUCT-STRATEGY.md": "# Strategy\n",
    })
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@fettle.invalid", "commit", "-qm", "base"],
        cwd=d,
        check=True,
    )
    with open(os.path.join(d, "docs", "PRODUCT-STRATEGY.md"), "a") as f:
        f.write("Changed.\n")

    result = ci.run_ci(d)
    quality = next(g for g in result["gates"] if g["name"] == "quality")
    assert quality["ok"] is False
    assert any("SPEC_AUDIT" in finding for finding in quality["findings"])


def test_run_ci_baseline_cannot_suppress_spec_audit():
    d = _git_repo({
        ".fettle.toml": "[gates.spec_audit]\nenabled = true\n",
        ".fettle-baseline.json": (
            '{"fingerprints":["spec_audit:docs/spec-audit.md:1:"]}'
        ),
        "docs/PRODUCT-STRATEGY.md": "# Strategy\n",
    })
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@fettle.invalid", "commit", "-qam", "base"],
        cwd=d,
        check=True,
    )
    with open(os.path.join(d, "docs", "PRODUCT-STRATEGY.md"), "a") as f:
        f.write("Changed.\n")

    quality = next(g for g in ci.run_ci(d)["gates"] if g["name"] == "quality")
    assert quality["ok"] is False
    assert any("SPEC_AUDIT" in finding for finding in quality["findings"])


def test_run_ci_committed_spec_and_audit_pass_on_clean_branch():
    sections = (
        "Requirements Matrix",
        "Fixture And Live Separation",
        "Adversarial Pass Review",
        "Non-Goals And Failure Paths",
        "Residual Risks",
    )
    d = _git_repo({
        ".fettle.toml": "[gates.spec_audit]\nenabled = true\n",
        "docs/PRODUCT-STRATEGY.md": "# Strategy\n",
    })
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@fettle.invalid", "commit", "-qm", "base"],
        cwd=d,
        check=True,
    )
    subprocess.run(["git", "branch", "-M", "main"], cwd=d, check=True)
    subprocess.run(["git", "switch", "-qc", "feature"], cwd=d, check=True)
    with open(os.path.join(d, "docs", "PRODUCT-STRATEGY.md"), "a") as f:
        f.write("Changed.\n")
    with open(os.path.join(d, "docs", "spec-audit.md"), "w") as f:
        f.write("# Audit\n" + "".join(f"\n## {section}\nChecked.\n" for section in sections))
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@fettle.invalid", "commit", "-qm", "audited"],
        cwd=d,
        check=True,
    )

    assert ci.run_ci(d)["ok"] is True


def test_regression_fails_closed_when_scanner_raises(monkeypatch):
    """Regression — CI must fail closed, never silently skip a gate: if the
    boundary scanner raises, run_ci reports failure, not pass."""
    d = _git_repo({"a.py": "x = 1\n"})

    def boom(root, cfg):
        raise RuntimeError("scanner crashed")

    monkeypatch.setattr(ci, "scan_repo", boom)
    result = ci.run_ci(d)
    assert result["ok"] is False
    boundary = next(g for g in result["gates"] if g["name"] == "boundary")
    assert boundary["ok"] is False
    assert "error" in boundary


def test_quality_gate_fails_closed_when_required_scanner_fails(monkeypatch):
    d = _git_repo({"a.py": "x = 1\n"})

    monkeypatch.setattr(
        "fettle.quality_scan.execute_ruff",
        lambda targets: ToolScanResult(
            tool="ruff",
            status=ResultStatus.TOOL_ERROR,
            message="ruff timed out",
        ),
    )

    result = ci.run_ci(d)

    quality = next(g for g in result["gates"] if g["name"] == "quality")
    assert result["ok"] is False
    assert quality["ok"] is False
    assert quality["status"] == ResultStatus.TOOL_ERROR.value
    assert "timed out" in quality["error"]


def test_quality_gate_preserves_scanner_config_error(monkeypatch):
    d = _git_repo({"a.py": "x = 1\n"})
    monkeypatch.setattr(
        "fettle.quality_scan.execute_semgrep",
        lambda targets: ToolScanResult(
            tool="semgrep",
            status=ResultStatus.CONFIG_ERROR,
            message="rules file not found",
        ),
    )

    quality = next(g for g in ci.run_ci(d)["gates"] if g["name"] == "quality")

    assert quality["ok"] is False
    assert quality["status"] == ResultStatus.CONFIG_ERROR.value


def test_plan_gate_honors_explicit_exclusions_without_hiding_other_plans():
    d = _git_repo({
        ".fettle.toml": (
            "[gates.plan]\n"
            'exclude = ["docs/activity-plan.md"]\n'
        ),
        "docs/activity-plan.md": "# Activity Plan\n\nNo WP task format.\n",
        "docs/invalid-plan.md": "# Invalid Plan\n\nNo work packages.\n",
    })

    plans = next(g for g in ci.run_ci(d)["gates"] if g["name"] == "plans")

    assert plans["ok"] is False
    assert plans["findings"] == ["docs/invalid-plan.md"]


def test_generated_workflow_parses_and_runs_fettle_ci():
    yaml_text = ci.generate_workflow()
    import yaml
    doc = yaml.safe_load(yaml_text)
    assert "jobs" in doc
    flat = yaml_text.lower()
    assert "fettle ci" in flat or "cli.py ci" in flat


def test_regression_generated_workflow_always_has_boundary_step():
    """Regression — a generated CI must never omit the boundary scan (the
    root cause: a hand-rolled CI missing the scrub audit let a leak ship)."""
    yaml_text = ci.generate_workflow()
    assert "boundar" in yaml_text.lower()


def test_init_seeds_config_and_workflow():
    d = _git_repo({"a.py": "x = 1\n"})
    ci.init_ci(d, dry_run=False)
    assert os.path.isfile(os.path.join(d, ".github", "workflows", "fettle.yml"))
    toml = os.path.join(d, ".fettle.toml")
    assert os.path.isfile(toml)
    with open(toml) as f:
        assert "boundary" in f.read()


def test_init_dry_run_writes_nothing():
    d = _git_repo({"a.py": "x = 1\n"})
    out = ci.init_ci(d, dry_run=True)
    assert not os.path.exists(os.path.join(d, ".github"))
    assert "boundar" in out.lower()


def test_integration_run_ci_end_to_end():
    clean = _git_repo({"ok.py": "y = 2\n"})
    assert ci.run_ci(clean)["ok"] is True
    leaky = _git_repo({"bad.py": f'p = "/Users/someone/other/x.py"\nk = "{SYNTH_AWS}"\n'})
    assert ci.run_ci(leaky)["ok"] is False


def test_mutation_workflow_uses_dynamic_blocking_evidence_authority():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "timeout-minutes: 35" in workflow
    assert "prepare:" in workflow
    assert "fromJSON(needs.prepare.outputs.matrix)" in workflow
    assert "--resume-manifest" in workflow
    assert "shard: [0, 1," not in workflow
    assert "--paths fettle/" not in workflow
    assert "--shard-count 240" not in workflow
    assert "if: always()" in workflow


def test_pr_containment_is_separate_from_authoritative_check_producer():
    authoritative = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    containment = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()

    assert "pull_request:" not in authoritative
    assert "pull_request:" in containment
    assert "name: mutation evidence" not in containment
    assert containment.count("name: mutation qualification pending") == 1


def test_changed_mutation_workflow_prepares_scope_without_pr_execution_fanout():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()

    assert "--prepare-changed-manifests mutation-changed-manifests" in workflow
    assert "fromJSON(needs.changed-prepare.outputs.matrix)" not in workflow
    assert "mutmut run" not in workflow
    assert "needs: changed-prepare" in workflow
    assert "Mutation execution requires explicit maintainer dispatch" in workflow
    assert '\"status\":\"unknown\"' in workflow
    assert '\"passed\":false' in workflow
    assert "if: needs.changed-prepare.result != 'success'" in workflow
    assert "needs.changed-prepare.outputs.shard_count != '0'" in workflow


def test_changed_mutation_workflow_retains_truthful_nonpass_summary():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()

    assert '\"qualification_executed\":false' in workflow
    assert '\"status\":\"not_applicable\"' in workflow
    assert '\"status\":\"unknown\"' in workflow
    assert "--github-summary mutation-report.json" in workflow
    assert "mutation-pr-containment-${{ github.run_id }}" in workflow
    assert "if-no-files-found: error" in workflow


def test_changed_mutation_workflow_keeps_replay_behind_explicit_dispatch():
    containment = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "changed-replay" not in containment
    assert "--resume-manifest" not in containment
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "--resume-manifest" in workflow
    assert "--timeout 1740" in workflow


def test_mutation_workflows_have_one_authoritative_check_producer():
    workflows = [
        yaml.safe_load(path.read_text())
        for path in (Path(PLUGIN_DIR) / ".github/workflows").glob("*.yml")
    ]

    assert sum(
        job.get("name") == "mutation evidence"
        for workflow in workflows
        for job in workflow.get("jobs", {}).values()
    ) == 1


def test_mutation_workflows_pin_supported_node24_setup_uv():
    workflows = [
        Path(PLUGIN_DIR) / ".github/workflows/mutation.yml",
        Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml",
        Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml",
        Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-aggregation-recovery.yml",
    ]
    pin = "astral-sh/setup-uv@eb1897b8dc4b5d5bfe39a428a8f2304605e0983c # v7.0.0"

    assert all(pin in path.read_text() for path in workflows)
    assert all("setup-uv@d0cc045d" not in path.read_text() for path in workflows)


def test_final_candidate_mutation_path_uses_exact_runtime_and_stages():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert 'python-version: "3.12"' not in workflow
    assert 'python-version: "3.12.13"' in workflow
    assert 'platform.python_version()=="3.12.13"' in workflow
    assert 'report.get("shard_count")==256' in workflow
    assert "- finalize" in workflow
    assert 'WAVES["wave-"+stage]' in workflow
    assert '"1":8,"2":16,"3":32' in workflow
    assert "name: mutation-calibration-stage-${{ github.event.inputs.stage_1_run_id }}" in workflow
    assert "name: mutation-calibration-stage-${{ github.event.inputs.stage_2_run_id }}" in workflow
    assert "Validate prior calibration stages before fan-out" in workflow
    assert "len(identities) != 1" in workflow
    assert "identity != prior_identity" in workflow
    assert 'report.get("calibration_id") != os.environ["CALIBRATION_ID"]' in workflow
    assert "Download prior calibration accounting" in workflow
    assert 'accounting.get("ceiling") != int(os.environ["RUNNER_MINUTE_CEILING"])' in workflow
    assert "name: mutation (assemble evidence)" in workflow
    assert "name: mutation evidence" in workflow
    assert "Independently read back authoritative evidence" in workflow
    assert "name: mutation (read back detail corpus)" in workflow
    assert "name: mutation (calibration accounting)" in workflow
    assert "runner_minute_ceiling:" in workflow
    assert 'os.environ["RUNNER_MINUTE_CEILING"]=="12000"' in workflow
    assert '"continuation_of": os.environ["RESUME_RUN_ID"] or None' in workflow
    parsed = yaml.safe_load(workflow)
    provenance = next(
        step for step in parsed["jobs"]["prepare"]["steps"]
        if step.get("name") == "Record calibration source provenance"
    )
    assert provenance["env"]["RESUME_RUN_ID"] == "${{ github.event.inputs.resume_run_id }}"
    assert "fail-fast: false" in workflow
    readback = workflow.split("\n  evidence-readback:", 1)[1]
    assert "github.event.inputs.calibration_stage != '3'" in readback


def test_finalization_rejects_non_allowlisted_or_mode_changes():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    finalization = workflow.split("Prove evidence-only finalization head", 1)[1].split(
        "Download stage 1 mutation evidence", 1,
    )[0]

    assert '"docs/completion/audit-hardening.json"' in finalization
    assert '"docs/final-candidate-readiness.md"' in finalization
    assert '"docs/completion/evidence/external/audit-hardening/run-05-locator.json"' in finalization
    assert '"docs/completion/evidence/external/audit-hardening"' not in finalization
    assert '["git", "diff", "--raw", "--no-abbrev", executable, head]' in finalization
    assert 'fields[0] != ":100644" or fields[1] != "100644"' in finalization
    assert "set(changed) - allowed" in finalization
    aggregate = workflow.split("\n  aggregate:", 1)[1].split("\n  evidence-readback:", 1)[0]
    assert "fetch-depth: 0" in aggregate
    assert 'report.get("calibration_id")==os.environ["CALIBRATION_ID"]' in workflow
    assert 'hashlib.sha256(path.read_bytes()).hexdigest()==checksum' in workflow
    assert 'accounting.get("stage")=="3" and accounting.get("passed") is True' in workflow


def test_full_mutation_workflow_gates_fanout_on_retained_preflight():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "preflight:" in workflow
    assert "--preflight-manifest" in workflow
    assert "name: mutation-preflight-${{ github.run_id }}-${{ matrix.shard }}" in workflow
    assert "needs: [prepare, preflight]" in workflow
    assert workflow.index("Prepare digest-bound partitions") < workflow.index("Bounded mutation-detail preflight")
    assert "type: choice" in workflow
    assert "- preflight" in workflow and "- replay" in workflow and "- calibration" in workflow


def test_mutation_workflow_has_bounded_non_qualifying_diagnostic_canary():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    prepare_job = workflow.split("\n  prepare:", 1)[1].split("\n  preflight:", 1)[0]
    preflight_job = workflow.split("\n  preflight:", 1)[1].split("\n  diagnostic-canary:", 1)[0]
    canary_job = workflow.split("\n  diagnostic-canary:", 1)[1].split(
        "\n  retention-provider-probe:", 1,
    )[0]
    preflight_aggregate_job = workflow.split("\n  preflight-aggregate:", 1)[1].split(
        "\n  full-shard:", 1,
    )[0]
    full_shard_job = workflow.split("\n  full-shard:", 1)[1].split("\n  aggregate:", 1)[0]
    aggregate_job = workflow.split("\n  aggregate:", 1)[1]

    assert "- diagnostic-canary" in workflow
    assert "diagnostic_shard:" in workflow
    assert "Bind dispatch to exact candidate" in prepare_job
    assert "Validate diagnostic canary scope" in prepare_job
    assert "name: mutation (diagnostic preflight shard)" in canary_job
    assert "matrix:" not in canary_job
    assert '--preflight-manifest "mutation-manifests/partition-${DIAGNOSTIC_SHARD}.json"' in canary_job
    assert "if: always()" in canary_job
    assert "name: mutation-preflight-diagnostic-${{ github.run_id }}" in canary_job
    assert "github.event.inputs.mode == 'preflight'" in preflight_job
    assert "github.event.inputs.mode == 'preflight'" in preflight_aggregate_job
    assert "github.event.inputs.mode != 'diagnostic-canary'" in full_shard_job
    assert "github.event.inputs.mode != 'calibration'" in aggregate_job
    assert '"qualification_executed":False' in aggregate_job
    assert "report.get('passed') is True" in aggregate_job
    assert "[46,62,63,239]" not in workflow
    assert 'archived=(("fettle/mutation_test.py",121,180)' in workflow
    assert 'item["start"] <= end and item["end"] >= start' in workflow
    assert "python -m pip install" not in workflow
    assert "uv run --no-sync" in workflow
    assert "merge-multiple: true" not in workflow


def test_staged_preflight_first_run_is_frozen_bounded_and_fail_closed():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    staged = workflow.split("\n  staged-prepare:", 1)[1].split("\n  full-shard:", 1)[0]

    assert "- staged-preflight" in workflow
    assert 'run: test "$RUN_ATTEMPT" = "1"' in staged
    assert staged.count("ref: ${{ github.event.inputs.candidate_sha }}") >= 3
    assert "max-parallel: 2" in staged
    assert "max-parallel: 4" in staged
    assert "max-parallel: 8" not in staged
    assert staged.count("fail-fast: true") == 2
    assert "needs: [staged-prepare, staged-wave-1-gate]" in staged
    assert staged.count("validate-wave") == 2
    assert "mutation (monitor staged preflight budget)" in staged
    assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' in staged
    assert "if: always()\n        uses: actions/upload-artifact@" in staged
    assert "monitor-final-status.txt" in staged
    assert "cancellation-attempt.json" in staged
    assert "gh workflow run staged-preflight-continuation.yml" in staged
    assert '--repo "$GITHUB_REPOSITORY" --ref "$GITHUB_REF_NAME"' in staged
    assert "source_plan_sha256" in staged
    assert "merge-multiple: true" not in staged


def test_staged_handoff_commands_bind_repo_ref_and_unified_successor(tmp_path):
    mutation = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    continuation = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )
    sender_steps = mutation["jobs"]["staged-dispatch-continuation"]["steps"]
    dispatch = next(
        step["run"] for step in sender_steps
        if step.get("name") == "Dispatch immutable continuation"
    )
    receiver_steps = continuation["jobs"]["prepare"]["steps"]
    bind = next(
        step["run"] for step in receiver_steps
        if step.get("name") == "Bind unified candidate and orchestration identity"
    )

    workspace = tmp_path / "workspace"
    control = workspace / "control"
    control.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=control, check=True)
    (control / "identity.txt").write_text("successor")
    subprocess.run(["git", "add", "identity.txt"], cwd=control, check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
         "commit", "-qm", "successor"], cwd=control, check=True,
    )
    candidate = workspace / "candidate"
    subprocess.run(["git", "clone", "-q", str(control), str(candidate)], check=True)
    control_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=control, text=True,
    ).strip()
    candidate_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=candidate, text=True,
    ).strip()
    assert control_sha == candidate_sha

    (workspace / "source-plan").mkdir()
    (workspace / "source-plan/staged-preflight-plan.json").write_text("{}\n")
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    capture = workspace / "gh-args.txt"
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$GH_CAPTURE\"\n")
    gh.chmod(0o755)
    (bin_dir / "python").symlink_to(sys.executable)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GH_CAPTURE": str(capture),
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_REF_NAME": "repair-branch",
        "GITHUB_SHA": candidate_sha,
        "GITHUB_RUN_ID": "37",
        "GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/mutation.yml@refs/heads/repair-branch",
    }

    subprocess.run(dispatch, cwd=workspace, env=env, shell=True, check=True)

    args = capture.read_text().splitlines()
    assert args[:7] == [
        "workflow", "run", "staged-preflight-continuation.yml",
        "--repo", "owner/repo", "--ref", "repair-branch",
    ]
    fields = {
        key: value
        for flag, assignment in zip(args[7::2], args[8::2])
        for key, value in [assignment.split("=", 1)]
        if flag == "-f"
    }
    assert fields == {
        "candidate_sha": candidate_sha,
        "source_run_id": "37",
        "source_orchestration_sha": candidate_sha,
        "source_plan_sha256": __import__("hashlib").sha256(b"{}\n").hexdigest(),
        "source_workflow_ref": env["GITHUB_WORKFLOW_REF"],
    }

    expanded_bind = bind.replace(
        '${{ github.event.inputs.candidate_sha }}', candidate_sha
    )
    subprocess.run(
        expanded_bind, cwd=workspace,
        env={**env, "GITHUB_SHA": control_sha, "CANDIDATE_SHA": candidate_sha},
        shell=True, check=True,
    )

    rejected = subprocess.run(
        expanded_bind, cwd=workspace,
        env={**env, "GITHUB_SHA": "f" * 40, "CANDIDATE_SHA": candidate_sha},
        shell=True,
    )
    assert rejected.returncode != 0


def test_staged_preflight_keeps_authoritative_check_non_qualifying():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    aggregate = workflow.split("\n  aggregate:", 1)[1]

    assert "name: mutation staged preflight evidence" not in workflow
    assert "name: mutation (dispatch staged preflight continuation)" in workflow
    assert "github.event.inputs.mode != 'staged-preflight'" in aggregate
    assert 'candidate == os.environ["GITHUB_SHA"]' in aggregate


def test_staged_continuation_has_only_remaining_matrix_and_bounded_topology():
    workflow_path = Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml"
    workflow = workflow_path.read_text()
    jobs = yaml.safe_load(workflow)["jobs"]

    batches = [f"wave-3-batch-{index}" for index in range(1, 8)]
    admissions = [f"wave-3-admission-{index}" for index in range(1, 7)]
    assert set(jobs) == {
        "prepare", "launch-gate", *batches, *admissions, "monitor", "validate",
        "aggregate", "readback", "terminal-accounting",
    }
    assert sum("strategy" in job for job in jobs.values()) == 7
    assert len(jobs) == 20
    assert workflow.count("strategy:") == 7
    assert workflow.count("max-parallel: 8") == 7
    assert jobs["wave-3-batch-1"]["needs"] == ["prepare", "launch-gate"]
    for index in range(1, 7):
        assert jobs[f"wave-3-admission-{index}"]["needs"] == [
            "prepare", "launch-gate" if index == 1 else f"wave-3-admission-{index - 1}",
        ]
        assert jobs[f"wave-3-batch-{index + 1}"]["needs"] == [
            "prepare", f"wave-3-admission-{index}",
        ]
        matrix = jobs[f"wave-3-batch-{index + 1}"]["strategy"]["matrix"]
        assert matrix == f"${{{{ fromJSON(needs.wave-3-admission-{index}.outputs.matrix) }}}}"
    assert jobs["validate"]["needs"] == ["prepare", "wave-3-batch-7", "monitor"]
    assert jobs["monitor"]["needs"] == "wave-3-admission-6"
    monitor_steps = jobs["monitor"]["steps"]
    prior = next(
        step for step in monitor_steps
        if step.get("name") == "Download preceding admission accounting"
    )
    assert prior["with"]["name"] == (
        "mutation-continuation-admission-6-${{ github.run_id }}-${{ github.run_attempt }}"
    )
    monitor = next(
        step["run"] for step in monitor_steps
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    assert "historical_args=(--historical-accounting prior-admission/admission-budget.json)" in monitor
    for index in range(1, 7):
        steps = jobs[f"wave-3-admission-{index}"]["steps"]
        names = [step.get("name") for step in steps]
        assert names.index("Observe batch and enforce cumulative global budget") < names.index(
            "Wait for admitted artifact inventory"
        ) < names.index("Download admitted reports") < names.index(
            "Validate terminal evidence and emit next matrix"
        )
        observe = next(
            step["run"] for step in steps
            if step.get("name") == "Observe batch and enforce cumulative global budget"
        )
        assert "admission-budget-non-pass" in observe
        assert "admission-shard-failure" in observe
        assert "admission-observer-error" in observe
        assert "admission-observer-deadline" in observe
        assert "observer_deadline=" in observe
        assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' not in observe
        assert names[0] == "Arm fail-closed admission containment"
        arm = steps[0]["run"]
        assert "armed-through-diagnostics-retention" in arm
        assert "admission-containment-armed.txt" in arm
        assert "admission-observer-started-at.txt" in arm
        disarm_index = names.index("Disarm admission containment after retained success")
        retain_index = names.index("Retain admission evidence")
        assert disarm_index > names.index("Validate terminal evidence and emit next matrix")
        assert disarm_index > retain_index
        cancel_index = names.index("Request cancellation after retaining admission diagnostics")
        assert cancel_index > retain_index
        cancel = steps[cancel_index]
        assert cancel["if"] == "always()"
        assert "admission-containment-armed.txt" in cancel["run"]
        assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' in cancel["run"]
    assert "workflow_dispatch:" in workflow
    assert "candidate_sha:" in workflow
    assert "source_plan_sha256:" in workflow
    assert "fresh-continuation-plan" in workflow
    assert "--prior-run-id ${{ github.event.inputs.source_run_id }}" in workflow
    assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' in workflow
    assert "if: always()\n        uses: actions/upload-artifact@" in workflow
    assert "monitor-final-status.txt" in workflow
    assert "cancellation-attempt.json" in workflow
    assert 'source_uncertainty=api' in workflow
    assert 'source_uncertainty=accounting' in workflow
    assert 'reason="persistent-source-${source_uncertainty}-uncertainty"' in workflow
    assert '"status == \\"completed\\"' not in workflow
    assert '.status == "completed" and .conclusion == "success"' in workflow
    assert "--aggregate-preflight staged-reports --shard-count 256" in workflow
    assert "staged-wave-1" not in workflow
    assert "staged-wave-2" not in workflow


def test_staged_admission_production_shell_fragments_parse():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )

    for index in range(1, 7):
        steps = workflow["jobs"][f"wave-3-admission-{index}"]["steps"]
        for step in steps:
            if "run" not in step:
                continue
            result = subprocess.run(
                ["bash", "-n"], input=step["run"], text=True,
                capture_output=True,
            )
            assert result.returncode == 0, f"batch {index} {step.get('name')}: {result.stderr}"


def test_staged_preflight_budget_gates_are_cumulative_across_both_runs():
    first = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    continuation = (
        Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml"
    ).read_text()

    assert "--next-wave wave-2 --output wave-1-budget.json" in first
    assert "--next-wave wave-3 --output wave-2-budget.json" in first
    assert '--next-wave complete --output "$budget_snapshot"' in first
    assert '--observed-at "$observed_at" --job-timeout-minutes 35' in first
    assert 'historical_args+=(--historical-accounting "$prior_budget")' in first
    assert "--prior-jobs source-jobs.json" in continuation
    assert "--prior-run-id ${{ github.event.inputs.source_run_id }}" in continuation
    assert continuation.count("--next-wave complete") == 9
    assert continuation.count('cp "$budget" admission-budget.json') == 6
    assert continuation.count("--job-timeout-minutes 35") == 7
    assert '--observed-at "$observed_at" --job-timeout-minutes 35' in continuation
    assert 'historical_args+=(--historical-accounting "$prior_budget")' in continuation
    assert first.count("--historical-accounting monitor-accounting/monitor-budget.json") == 1
    assert continuation.count("--historical-accounting monitor-accounting/monitor-budget.json") == 2
    assert 'assert result["billing_authority"] is False' in first
    assert "Operational ceiling, not a guaranteed provider billing cap." not in first


def test_staged_monitor_cancellation_is_repo_bound_from_workspace_root(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    steps = workflow["jobs"]["staged-monitor"]["steps"]
    cancel = next(
        step["run"] for step in steps
        if step.get("name") == "Request cancellation after retaining diagnostics"
    )
    workspace = tmp_path / "workspace"
    (workspace / "control").mkdir(parents=True)
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    capture = workspace / "gh-args.txt"
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$GH_CAPTURE\"\n")
    gh.chmod(0o755)
    (workspace / "cancellation-requested.txt").write_text("operational-cutoff\n")
    result = _run_actions_bash(
        cancel, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GH_CAPTURE": str(capture),
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "37",
        },
    )

    assert result.returncode == 2
    assert capture.read_text().splitlines() == [
        "api", "--method", "POST", "repos/owner/repo/actions/runs/37/cancel",
    ]
    assert (workspace / "cancellation-final-status.txt").read_text() == "accepted\n"


def test_staged_monitor_surfaces_cancellation_api_failure(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )
    steps = workflow["jobs"]["monitor"]["steps"]
    cancel = next(
        step["run"] for step in steps
        if step.get("name") == "Request cancellation after retaining diagnostics"
    )
    workspace = tmp_path / "workspace"
    (workspace / "control").mkdir(parents=True)
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nexit 23\n")
    gh.chmod(0o755)
    (workspace / "cancellation-requested.txt").write_text("persistent-accounting-uncertainty\n")
    result = _run_actions_bash(
        cancel, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "37",
        },
    )

    assert result.returncode == 23
    assert (workspace / "cancellation-final-status.txt").read_text() == "api-failure-23\n"


def test_staged_monitor_lifecycle_resamples_and_retains_each_snapshot(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    steps = workflow["jobs"]["staged-monitor"]["steps"]
    monitor = next(
        step["run"] for step in steps
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    fixtures = workspace / "fixtures"
    fixtures.mkdir()
    fixture = json.loads(
        (Path(PLUGIN_DIR) / "tests/fixtures/staged_preflight_runner_acquisition.json").read_text()
    )
    assert fixture["provenance"]["kind"] == "reconstructed_runner_acquisition_sequence"
    assert "precise original trigger is uncertain" in fixture["provenance"]["limitation"]
    states = fixture["states"]
    started = datetime.now(UTC) - timedelta(seconds=2)
    completed = started + timedelta(seconds=1)
    for state in states:
        if state["started_at"] is not None:
            state["started_at"] = started.isoformat().replace("+00:00", "Z")
        if state["completed_at"] is not None:
            state["completed_at"] = completed.isoformat().replace("+00:00", "Z")
    for sample, state in enumerate(states, 1):
        jobs = [
            {
                    "id": index + 1, "run_id": 37, "run_attempt": 1,
                "name": f"mutation (staged preflight wave 2 shard {index})",
                **state,
            }
            for index in range(32)
        ]
        (fixtures / f"{sample}.json").write_text(json.dumps([{
            "total_count": len(jobs), "jobs": jobs,
        }]))
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        "n=$(cat \"$GH_COUNTER\" 2>/dev/null || echo 0)\n"
        "n=$((n + 1)); [ \"$n\" -gt 5 ] && n=5\n"
        "printf '%s' \"$n\" > \"$GH_COUNTER\"\n"
        "cat \"$GH_FIXTURES/$n.json\"\n"
    )
    gh.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "GH_COUNTER": str(workspace / "counter"),
            "GH_FIXTURES": str(fixtures),
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
            "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0, result.stderr
    assert (workspace / "monitor-final-status.txt").read_text() == "completed\n"
    assert not (workspace / "cancellation-requested.txt").exists()
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json"))) == 5
    assert json.loads((workspace / "monitor-budget.json").read_text())["passed"] is True
    assert len(list((workspace / "monitor-snapshots").glob("budget-*.json"))) == 4
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json.observed-at"))) == 5


def test_staged_monitor_replays_exact_retained_timestamp_revision_lifecycle(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    monitor = next(
        step["run"] for step in workflow["jobs"]["staged-monitor"]["steps"]
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    source = Path(PLUGIN_DIR) / "tests/fixtures/staged_preflight_accounting_revision"
    fixtures = workspace / "fixtures"
    fixtures.mkdir()
    for index in range(1, 4):
        shutil.copy2(source / f"jobs-{index}.json", fixtures / f"{index}.json")
    shutil.copy2(source / "jobs-terminal.json", fixtures / "4.json")
    observations = [
        item["observed_at"] for item in json.loads(
            (Path(PLUGIN_DIR) / "tests/fixtures/staged_preflight_accounting_revision.json").read_text()
        )["observations"]
    ] + ["2026-10-08T15:13:16.532084+00:00"]
    (workspace / "observations.txt").write_text("\n".join(observations) + "\n")
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        "n=$(cat \"$GH_COUNTER\" 2>/dev/null || echo 0)\n"
        "n=$((n + 1)); [ \"$n\" -gt 4 ] && n=4\n"
        "printf '%s' \"$n\" > \"$GH_COUNTER\"\n"
        "cat \"$GH_FIXTURES/$n.json\"\n"
    )
    gh.chmod(0o755)
    python = bin_dir / "python"
    python.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = -c ] && printf '%s' \"$2\" | grep -q 'datetime.now'; then\n"
        "  sed -n \"$(cat \"$GH_COUNTER\")p\" \"$OBSERVATIONS\"\n"
        "else\n"
        f"  exec {sys.executable} \"$@\"\n"
        "fi\n"
    )
    python.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GH_COUNTER": str(workspace / "counter"),
            "GH_FIXTURES": str(fixtures),
            "OBSERVATIONS": str(workspace / "observations.txt"),
            "GITHUB_REPOSITORY": "MilindGaharwar/fettle",
            "GITHUB_RUN_ID": "37795579761", "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0, result.stderr
    assert (workspace / "monitor-final-status.txt").read_text() == "completed\n"
    budgets = [
        json.loads(path.read_text())
        for path in sorted((workspace / "monitor-snapshots").glob("budget-*.json"))
    ]
    assert len(budgets) == 4
    assert [
        next(job for job in report.get("included_jobs", []) if job["id"] == 113377920861)["minutes"]
        for report in budgets[:3]
    ] == [0.12, 0.38, 0.65]
    assert all(report["passed"] is True for report in budgets)
    assert budgets[-1]["estimated_runner_minutes"] >= max(
        report["estimated_runner_minutes"] for report in budgets[:-1]
    )
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json"))) == 4
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json.observed-at"))) == 4
    assert not (workspace / "cancellation-requested.txt").exists()


def test_staged_monitor_persistent_malformed_metadata_requests_cancellation(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    steps = workflow["jobs"]["staged-monitor"]["steps"]
    monitor = next(
        step["run"] for step in steps
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    malformed = workspace / "malformed.json"
    malformed.write_text(json.dumps([{"total_count": 1, "jobs": [{
        "id": 1, "run_id": 37, "run_attempt": 1,
        "name": "mutation (staged preflight wave 2 shard 0)",
        "status": "queued", "conclusion": None,
        "started_at": None, "completed_at": None,
        "runner_id": 10, "runner_name": None,
        "runner_group_id": None, "runner_group_name": None, "steps": [],
    }]}]))
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\ncat \"$GH_FIXTURE\"\n")
    gh.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "GH_FIXTURE": str(malformed),
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
            "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0
    assert (workspace / "monitor-final-status.txt").read_text() == (
        "persistent-accounting-uncertainty\n"
    )
    assert (workspace / "cancellation-requested.txt").is_file()
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json"))) == 3
    assert not list((workspace / "monitor-snapshots").glob("budget-*.json"))
    attempt = json.loads((workspace / "cancellation-attempt.json").read_text())
    assert attempt == {
        "repository": "owner/repo", "run_id": "37",
        "reason": "persistent-accounting-uncertainty", "status": "pending",
    }


def test_staged_monitor_malformed_json_is_resampled_then_requests_cancellation(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    monitor = next(
        step["run"] for step in workflow["jobs"]["staged-monitor"]["steps"]
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nprintf '%s\\n' '{not-json'\n")
    gh.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
            "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0
    assert (workspace / "monitor-final-status.txt").read_text() == (
        "persistent-accounting-uncertainty\n"
    )
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json"))) == 3


def test_staged_monitor_budget_crossing_requests_cancellation(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    monitor = next(
        step["run"] for step in workflow["jobs"]["staged-monitor"]["steps"]
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    started = (datetime.now(UTC) - timedelta(minutes=36)).isoformat().replace("+00:00", "Z")
    jobs = [{
            "id": index + 1, "run_id": 37, "run_attempt": 1,
        "name": f"mutation (staged preflight wave 2 shard {index})",
        "status": "in_progress", "conclusion": None,
        "started_at": started, "completed_at": None,
        "runner_id": index + 1, "runner_name": f"runner-{index}",
        "runner_group_id": 0, "runner_group_name": "GitHub Actions",
        "steps": [{"name": "work", "status": "in_progress", "conclusion": None}],
    } for index in range(32)]
    fixture = workspace / "jobs.json"
    fixture.write_text(json.dumps([{"total_count": 32, "jobs": jobs}]))
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\ncat \"$GH_FIXTURE\"\n")
    gh.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "GH_FIXTURE": str(fixture),
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
            "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0
    assert (workspace / "monitor-final-status.txt").read_text() == "operational-cutoff\n"
    budget = json.loads((workspace / "monitor-budget.json").read_text())
    assert budget["launch_ceiling"] == 1120
    assert budget["passed"] is False
    assert (workspace / "cancellation-requested.txt").is_file()


def test_continuation_monitor_reuses_validated_source_snapshot(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )
    monitor = next(
        step["run"] for step in workflow["jobs"]["monitor"]["steps"]
        if step.get("name") == "Stop on failure or exhausted execution budget"
    ).replace("${{ github.event.inputs.source_run_id }}", "36")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    completed = datetime.now(UTC)
    started = completed - timedelta(seconds=1)

    def job(index, run_id, name):
        return {
            "id": index, "run_id": run_id, "run_attempt": 1, "name": name,
            "status": "completed", "conclusion": "success",
            "started_at": started.isoformat().replace("+00:00", "Z"),
            "completed_at": completed.isoformat().replace("+00:00", "Z"),
            "runner_id": index + 1, "runner_name": f"runner-{index}",
            "runner_group_id": 0, "runner_group_name": "GitHub Actions",
            "steps": [{"name": "work", "status": "completed", "conclusion": "success"}],
        }

    source = workspace / "source.json"
    source.write_text(json.dumps([{"total_count": 1, "jobs": [job(1, 36, "source support")]}]))
    current_jobs = [
        job(index + 100, 37, f"mutation (continuation shard {index})")
        for index in range(216)
    ]
    current = workspace / "current.json"
    current.write_text(json.dumps([{"total_count": 216, "jobs": current_jobs}]))
    (workspace / "prior-admission").mkdir()
    prior_accounting = {
        **combine_accounting(
            source, current,
            expected_prior_run_id="36", expected_prior_run_attempt="1",
            expected_current_run_id="37", expected_current_run_attempt="1",
        ),
        "launch_ceiling": 1120,
        "next_wave": "complete",
        "passed": True,
    }
    (workspace / "prior-admission/admission-budget.json").write_text(
        json.dumps(prior_accounting)
    )
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  */runs/36/*) printf x >> \"$SOURCE_CALLS\"; cat \"$SOURCE_FIXTURE\" ;;\n"
        "  *) cat \"$CURRENT_FIXTURE\" ;;\n"
        "esac\n"
    )
    gh.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "SOURCE_CALLS": str(workspace / "source-calls"),
            "SOURCE_FIXTURE": str(source), "CURRENT_FIXTURE": str(current),
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
        },
    )

    assert result.returncode == 0, result.stderr
    assert (workspace / "source-calls").read_text() == "x"
    assert (workspace / "source-jobs.json").read_bytes() == source.read_bytes()
    assert (workspace / "monitor-final-status.txt").read_text() == "completed\n"
    assert not (workspace / "cancellation-requested.txt").exists()
    assert len(list((workspace / "monitor-snapshots").glob("current-budget-*.json"))) == 1
    assert len(list((workspace / "monitor-snapshots").glob("current-jobs-*.json.observed-at"))) == 1


def test_aggregation_recovery_cannot_execute_mutations_and_retains_failure_evidence():
    workflow_path = Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-aggregation-recovery.yml"
    workflow = workflow_path.read_text()
    jobs = yaml.safe_load(workflow)["jobs"]

    assert set(jobs) == {"aggregate", "readback", "terminal-accounting"}
    assert all("strategy" not in job for job in jobs.values())
    assert "matrix:" not in workflow
    assert "--preflight-manifest" not in workflow
    assert "--prepare-manifests" not in workflow
    assert "mutation run" not in workflow
    assert "--aggregate-preflight corpus --shard-count 256" in workflow
    assert "github.event.head_commit.message == 'Execute preflight aggregation recovery'" in workflow
    assert workflow.count("run-id: 37464324954") == 1
    assert workflow.count("run-id: 37476889333") == 1
    assert workflow.count("run-id: 37550308775") == 2
    assert "if: always()\n    needs: aggregate" in workflow
    assert "if: always()\n    needs: [aggregate, readback]" in workflow
    assert "--source jobs-37550308775.json 37550308775 1" in workflow
    assert "generated\"] == aggregate[\"canonicalized\"] == 45432" in workflow
    assert "155a02b863d6b440211e09eef8daf189098554ca5871c5a484e7b65a3b005be2" in workflow


def test_continuation_support_jobs_install_every_invoked_tool():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    validation = workflow.split("\n  validate:", 1)[1].split("\n  aggregate:", 1)[0]
    aggregate = workflow.split("\n  aggregate:", 1)[1].split("\n  readback:", 1)[0]

    assert "astral-sh/setup-uv@" in validation
    assert "uv venv --python 3.12.13" in validation
    assert "astral-sh/setup-uv@" in aggregate
    assert "uv venv --python 3.12.13" in aggregate


def test_mutation_execution_reuses_explicit_sha_bound_preflight():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "preflight_run_id:" in workflow
    assert workflow.count("run-id: ${{ github.event.inputs.preflight_run_id }}") == 4
    assert workflow.count("github-token: ${{ secrets.GITHUB_TOKEN }}") == 13
    assert "permissions:\n  actions: read\n  contents: read" in workflow
    assert "candidate_sha:" in workflow
    assert 'candidate == os.environ["GITHUB_SHA"]' in workflow
    assert 'aggregate["revision"]==os.environ["GITHUB_SHA"]' in workflow
    assert 'item["revision"]==os.environ["GITHUB_SHA"]' in workflow
    assert 'aggregate["shard_count"]==shard_count' in workflow
    assert 'aggregate["generated"]==aggregate["canonicalized"]' in workflow
    assert 'aggregate["collisions"]==0' in workflow
    assert "--aggregate-scope mutation-manifests" in workflow
    assert "--aggregate-preflight-evidence retained-preflight/mutation-preflight.json" in workflow
    assert '--calibration-id "$CALIBRATION_ID"' in workflow


def test_authoritative_check_binds_candidate_and_probe_cannot_qualify():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    prepare_job = workflow.split("\n  prepare:", 1)[1].split("\n  preflight:", 1)[0]
    aggregate_job = workflow.split("\n  aggregate:", 1)[1]

    assert "github.event.inputs.mode != 'binding-probe'" in prepare_job
    assert "Bind authoritative check to exact candidate" in aggregate_job
    assert 'candidate == os.environ["GITHUB_SHA"]' in aggregate_job
    assert "github.event.inputs.mode != 'calibration'" in aggregate_job
    assert '"passed":False' in aggregate_job
    assert "report.get('passed') is True" in aggregate_job


def test_mutation_execution_skips_redundant_preflight_and_schedule_is_preflight_only():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "github.event.inputs.mode == 'preflight'" in workflow
    assert "github.event_name == 'schedule' || github.event.inputs.mode != 'preflight'" not in workflow
    assert "needs: [prepare, preflight-aggregate]" not in workflow
    assert (
        "full-shard:\n    if: github.event_name == 'workflow_dispatch'"
        " && github.event.inputs.mode != 'preflight'"
            " && github.event.inputs.mode != 'diagnostic-canary'"
            " && github.event.inputs.mode != 'retention-probe'"
            " && github.event.inputs.mode != 'readback-probe'"
            " && github.event.inputs.mode != 'staged-preflight'"
            " && github.event.inputs.mode != 'finalize'"
            " && github.event.inputs.mode != 'capacity-validation'"
            " && !(github.event.inputs.mode == 'calibration' && github.event.inputs.calibration_stage == '3')"
        "\n    needs: [prepare, calibration-launch-gate]"
    ) in workflow
    assert workflow.index("Verify retained SHA-bound preflight") < workflow.index("full-shard:")
    assert "MODE='${{ github.event.inputs.mode || 'preflight' }}'" in workflow
    assert "github.event_name == 'workflow_dispatch' && github.event.inputs.mode == 'calibration'" in workflow


def test_mutation_hotspot_chunks_preserve_authoritative_worker_bound():
    config = (Path(PLUGIN_DIR) / ".fettle.toml").read_text()

    assert "full_timeout_s = 1800" in config
    assert "full_shards = 256" in config
    assert '"fettle/ci.py" = 20' in config
    assert '"fettle/coverage_gate.py" = 20' in config
    assert '"fettle/doctor.py" = 20' in config
    assert '"fettle/init_cmd.py" = 20' in config
    assert '"fettle/mutation_test.py" = 5' in config
    assert '"fettle/post_edit.py" = 20' in config
    assert '"fettle/project_rules.py" = 10' in config
    assert '"fettle/quality_scan.py" = 2' in config
    assert '"fettle/ratchet.py" = 20' in config
    assert '"fettle/result.py" = 20' in config
    assert '"fettle/security_review.py" = 20' in config
    assert '"fettle/semgrep_util.py" = 1' in config
    assert '"fettle/tool_runner.py" = 10' in config


def test_pr_mutation_runs_cancel_stale_work_but_authoritative_runs_remain_durable():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    containment = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()

    assert "concurrency:" in workflow
    assert "mutation-authoritative" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "cancel-in-progress: true" in containment


def test_mutation_calibration_checkpoints_are_explicit_and_isolated():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "calibration_id:" in workflow
    assert "resume_run_id:" in workflow
    assert 'CALIBRATION_ID: ${{ github.event.inputs.calibration_id }}' in workflow
    assert '--calibration-id "$CALIBRATION_ID"' in workflow
    assert 're.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value)' in workflow
    assert "--checkpoint-output mutation-checkpoint.json" in workflow
    assert "github.event.inputs.mode == 'replay'" in workflow
    assert "|| github.event.inputs.calibration_id }}-${{ matrix.shard }}" in workflow
    assert "if: always()" in workflow
    assert "github.event.inputs.resume_run_id != ''" in workflow
    assert "if: github.event_name == 'workflow_dispatch' && github.event.inputs.mode == 'calibration'" in workflow


def test_calibration_has_sparse_provenance_budget_monitor_and_terminal_accounting():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "plan-calibration-continuation" in workflow
    assert 'actions/runs/$RESUME_RUN_ID/artifacts?per_page=100' in workflow
    assert "--artifacts resume-artifacts.json" in workflow
    assert "--source-run resume-run.json" in workflow
    assert "calibration-source-provenance.json" in workflow
    assert "calibration-resume-bundle-${{ github.run_id }}" in workflow
    assert "name: mutation (calibration launch gate)" in workflow
    assert "name: mutation (monitor calibration budget)" in workflow
    assert "--cancellation-reserve 1200" in workflow
    assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' in workflow
    assert "needs: [prepare, calibration-launch-gate]" in workflow
    assert "EXPECTED_SHARDS: ${{ needs.prepare.outputs.execution_matrix }}" in workflow
    assert '[[ "$action" == "complete" ]] && break' in workflow
    assert "Retain monitor accounting before cancellation" in workflow
    assert "steps.monitor.outcome" in workflow
    assert "steps.retain-monitor.outcome" in workflow
    assert "job_timeout_minutes=35" in workflow
    assert '"calibration_id": os.environ["CALIBRATION_ID"]' in workflow
    assert "cp prior-accounting/calibration-monitor-budget.json prior-accounting/calibration-accounting.json" not in workflow
    assert "cp resume-accounting/calibration-monitor-budget.json resume-accounting/calibration-accounting.json" not in workflow
    assert "build_calibration_launch_accounting" in workflow
    assert "combine_calibration_monitor_accounting" in workflow
    assert "build_calibration_terminal_accounting" in workflow
    accounting_contract = (
        Path(PLUGIN_DIR) / "fettle/staged_preflight.py"
    ).read_text()
    assert 'identities[-1] == (predecessor_run_id, "1")' in accounting_contract
    assert 'accounting.get("calibration_id")==os.environ["CALIBRATION_ID"]' in workflow
    assert "needs: [prepare, calibration-launch-gate]" in workflow
    assert "fail-fast: false" in workflow
    accounting = workflow.split("\n  calibration-accounting:", 1)[1].split("\n  aggregate:", 1)[0]
    assert "if: always()" in accounting
    assert "billing_authority" in accounting
    assert "from datetime import datetime, timezone" in accounting
    assert "job_timeout_minutes=35" in accounting
    assert "Download stage 3 admission accounting floors" in accounting
    assert "retain_historical_accounting_floor(current, admission_floors)" in accounting


def test_fresh_stage_1_launch_output_is_consumed_by_actual_monitor_script(tmp_path):
    launch = _workflow_step_script(
        "calibration-launch-gate", "Reconcile usage before shard launch",
    )
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )
    bin_dir = _write_gh_jobs_stub(tmp_path, _calibration_jobs())
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle",
        "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1",
        "RESUME_RUN_ID": "",
        "PRIOR_RUN_ID": "",
        "CALIBRATION_ID": "cal-test",
        "CALIBRATION_STAGE": "1",
        "RUNNER_MINUTE_CEILING": "12000",
        "EXPECTED_SHARDS": json.dumps({"shard": [8, 27, 28, 37, 48, 50, 51, 53]}),
    }

    produced = _run_actions_bash(launch, cwd=tmp_path, env=env)
    assert produced.returncode == 0, produced.stderr
    launch_accounting = json.loads((tmp_path / "launch-accounting.json").read_text())
    assert launch_accounting["prior_runner_minutes"] == 0
    calibration_launch = tmp_path / "calibration-launch"
    calibration_launch.mkdir()
    shutil.copy(tmp_path / "launch-accounting.json", calibration_launch)

    consumed = _run_actions_bash(monitor, cwd=tmp_path, env=env)

    assert consumed.returncode == 0, consumed.stderr
    budget = json.loads((tmp_path / "calibration-monitor-budget.json").read_text())
    assert budget["prior_runner_minutes"] == 0
    assert budget["passed"] is True
    lifecycle = json.loads((tmp_path / "calibration-monitor-lifecycle.json").read_text())
    assert lifecycle["action"] == "complete"


def _run_launch_script(tmp_path, *, stage, resume="", prior="", predecessor=None):
    launch = _workflow_step_script(
        "calibration-launch-gate", "Reconcile usage before shard launch",
    )
    bin_dir = _write_gh_jobs_stub(tmp_path, _calibration_jobs(), predecessor)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle",
        "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1",
        "RESUME_RUN_ID": resume,
        "PRIOR_RUN_ID": prior,
        "CALIBRATION_ID": "cal-test",
        "CALIBRATION_STAGE": str(stage),
        "RUNNER_MINUTE_CEILING": "12000",
    }
    return _run_actions_bash(launch, cwd=tmp_path, env=env)


def _consume_launch_with_monitor_script(tmp_path, *, stage, jobs=None):
    calibration_launch = tmp_path / "calibration-launch"
    calibration_launch.mkdir(exist_ok=True)
    shutil.copy(tmp_path / "launch-accounting.json", calibration_launch)
    (tmp_path / "monitor-history").mkdir(exist_ok=True)
    (tmp_path / "admission-accounting").mkdir(exist_ok=True)
    (tmp_path / "jobs-monitor.json").write_text(json.dumps(
        jobs or _calibration_jobs(shards=(WAVES[f"wave-{stage}"][0],))
    ))
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )
    env = {
        **os.environ, "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_RUN_ID": "700", "GITHUB_RUN_ATTEMPT": "1",
        "CALIBRATION_ID": "cal-test", "CALIBRATION_STAGE": str(stage),
        "RUNNER_MINUTE_CEILING": "12000", "OBSERVED_AT": "2026-10-10T01:02:00Z",
        "SAMPLE_DIR": str(tmp_path),
    }
    return subprocess.run(
        [
            sys.executable,
            "-c",
            _python_heredoc_containing(monitor, "account_runner_minutes("),
        ],
        cwd=tmp_path, env=env,
        capture_output=True, text=True,
    )


def test_actual_launch_producer_carries_same_stage_resume_floor_once(tmp_path):
    predecessor = _cumulative_accounting(
        stage=1, run_ids=("381",), estimated=120, charged=125,
    )

    result = _run_launch_script(
        tmp_path, stage=1, resume="381", predecessor=predecessor,
    )

    assert result.returncode == 0, result.stderr
    launch = json.loads((tmp_path / "launch-accounting.json").read_text())
    assert launch["prior_runner_minutes"] == 125
    assert launch["estimated_runner_minutes"] == 133
    assert launch["calibration_predecessor"]["mode"] == "same-stage-resume"


@pytest.mark.parametrize(("stage", "prior_stage"), [(2, "1"), (3, "2")])
def test_actual_launch_producer_carries_prior_stage_floor_once(tmp_path, stage, prior_stage):
    predecessor = _cumulative_accounting(
        stage=prior_stage, run_ids=("381",), estimated=120, charged=125,
    )

    result = _run_launch_script(
        tmp_path, stage=stage, prior="381", predecessor=predecessor,
    )

    assert result.returncode == 0, result.stderr
    launch = json.loads((tmp_path / "launch-accounting.json").read_text())
    assert launch["prior_runner_minutes"] == 125
    assert launch["estimated_runner_minutes"] == 133
    assert launch["calibration_predecessor"]["mode"] == "prior-stage"


@pytest.mark.parametrize(
    ("stage", "prior", "resume", "run_ids"),
    [(2, "381", "482", ("381", "482")), (3, "482", "583", ("381", "482", "583"))],
)
def test_actual_launch_producer_validates_resumed_later_stage_lineage_without_double_counting(
    tmp_path, stage, prior, resume, run_ids,
):
    predecessor = _cumulative_accounting(
        stage=stage, run_ids=run_ids, estimated=240, charged=245,
    )

    result = _run_launch_script(
        tmp_path, stage=stage, resume=resume, prior=prior, predecessor=predecessor,
    )

    assert result.returncode == 0, result.stderr
    launch = json.loads((tmp_path / "launch-accounting.json").read_text())
    assert launch["prior_runner_minutes"] == 245
    assert launch["estimated_runner_minutes"] == 253


@pytest.mark.parametrize(
    ("stage", "prior", "resume", "run_ids"),
    [(2, "381", "482", ("381", "482")), (3, "482", "583", ("381", "482", "583"))],
)
def test_actual_launch_output_is_consumed_unchanged_by_monitor_for_later_stage_resume(
    tmp_path, stage, prior, resume, run_ids,
):
    predecessor = _cumulative_accounting(
        stage=stage, run_ids=run_ids, estimated=240, charged=245,
    )
    produced = _run_launch_script(
        tmp_path, stage=stage, resume=resume, prior=prior, predecessor=predecessor,
    )
    assert produced.returncode == 0, produced.stderr
    emitted = (tmp_path / "launch-accounting.json").read_bytes()

    consumed = _consume_launch_with_monitor_script(tmp_path, stage=stage)

    assert consumed.returncode == 0, consumed.stderr
    assert (tmp_path / "calibration-launch/launch-accounting.json").read_bytes() == emitted
    budget = json.loads((tmp_path / "calibration-monitor-budget.json").read_text())
    assert budget["prior_runner_minutes"] == 245
    assert budget["estimated_runner_minutes"] == 246
    assert budget["charged_runner_minutes"] == 246
    assert budget["calibration_predecessor"]["source_lineage"] == [
        {"run_id": run_id, "run_attempt": "1"} for run_id in run_ids
    ]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda record: record["calibration_predecessor"].pop("source_lineage"),
         "launch accounting contract"),
        (lambda record: record["calibration_predecessor"].update(prior_stage_run_id="999"),
         "launch accounting contract"),
        (lambda record: record["calibration_predecessor"]["source_lineage"][-1].update(
            run_id="999"), "launch accounting contract"),
        (lambda record: record["calibration_predecessor"]["source_lineage"][-1].update(
            run_attempt="2"), "launch accounting contract"),
        (lambda record: record["calibration_predecessor"]["source_lineage"][-1].update(
            calibration_id="foreign"), "launch accounting contract"),
    ],
)
def test_actual_monitor_rejects_missing_conflicting_or_foreign_resume_lineage(
    tmp_path, mutation, message,
):
    predecessor = _cumulative_accounting(
        stage=2, run_ids=("381", "482"), estimated=240, charged=245,
    )
    produced = _run_launch_script(
        tmp_path, stage=2, resume="482", prior="381", predecessor=predecessor,
    )
    assert produced.returncode == 0, produced.stderr
    launch = json.loads((tmp_path / "launch-accounting.json").read_text())
    mutation(launch)
    (tmp_path / "launch-accounting.json").write_text(json.dumps(launch))

    consumed = _consume_launch_with_monitor_script(tmp_path, stage=2)

    assert consumed.returncode != 0
    assert message in consumed.stderr


def test_resumed_monitor_preserves_lower_later_observation_floor_before_single_import(tmp_path):
    predecessor = _cumulative_accounting(
        stage=2, run_ids=("381", "482"), estimated=240, charged=245,
    )
    produced = _run_launch_script(
        tmp_path, stage=2, resume="482", prior="381", predecessor=predecessor,
    )
    assert produced.returncode == 0, produced.stderr
    history = tmp_path / "monitor-history"
    history.mkdir()
    (history / "0000.json").write_text(json.dumps(_operational_source("700", 20)))

    consumed = _consume_launch_with_monitor_script(tmp_path, stage=2)

    assert consumed.returncode == 0, consumed.stderr
    budget = json.loads((tmp_path / "calibration-monitor-budget.json").read_text())
    assert budget["historical_floor_applied"] is True
    assert budget["prior_runner_minutes"] == 245
    assert budget["estimated_runner_minutes"] == 265
    assert budget["charged_runner_minutes"] == 265


def test_actual_launch_producer_rejects_conflicting_resumed_later_stage_lineage(tmp_path):
    predecessor = _cumulative_accounting(
        stage=3, run_ids=("999", "583"), estimated=300,
    )

    result = _run_launch_script(
        tmp_path, stage=3, resume="583", prior="482", predecessor=predecessor,
    )

    assert result.returncode != 0
    assert "conflicts with prior-stage lineage" in result.stderr


def test_actual_launch_producer_rejects_nonadjacent_prior_stage_ancestor(tmp_path):
    predecessor = _cumulative_accounting(
        stage=3, run_ids=("381", "482", "583"), estimated=300,
    )

    result = _run_launch_script(
        tmp_path, stage=3, resume="583", prior="381", predecessor=predecessor,
    )

    assert result.returncode != 0
    assert "conflicts with prior-stage lineage" in result.stderr


def test_actual_launch_producer_rejects_missing_or_contradictory_predecessor(tmp_path):
    missing = _run_launch_script(tmp_path, stage=2, prior="381")
    assert missing.returncode != 0

    contradictory_dir = tmp_path / "contradictory"
    contradictory_dir.mkdir()
    contradictory = _run_launch_script(
        contradictory_dir,
        stage=1,
        prior="381",
        predecessor=_cumulative_accounting(stage=0, run_ids=("381",), estimated=1),
    )
    assert contradictory.returncode != 0
    assert "contradictory predecessor" in contradictory.stderr


def test_actual_launch_producer_rejects_malformed_predecessor_source(tmp_path):
    predecessor = _cumulative_accounting(
        stage=1, run_ids=("381",), estimated=120,
    )
    predecessor["sources"] = [None]

    result = _run_launch_script(
        tmp_path, stage=2, prior="381", predecessor=predecessor,
    )

    assert result.returncode != 0
    assert "predecessor accounting is incompatible" in result.stderr


def test_actual_sparse_monitor_route_preserves_historical_floor(tmp_path):
    launch_result = _run_launch_script(tmp_path, stage=1)
    assert launch_result.returncode == 0, launch_result.stderr
    calibration_launch = tmp_path / "calibration-launch"
    calibration_launch.mkdir()
    shutil.copy(tmp_path / "launch-accounting.json", calibration_launch)
    history = tmp_path / "monitor-history"
    history.mkdir()
    historical = _operational_source("700", 20)
    (history / "0000.json").write_text(json.dumps(historical))
    bin_dir = _write_gh_jobs_stub(tmp_path / "monitor-provider", _calibration_jobs(shards=(8, 48)))
    env = {
        **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1", "CALIBRATION_ID": "cal-test",
        "CALIBRATION_STAGE": "1", "RUNNER_MINUTE_CEILING": "12000",
        "EXPECTED_SHARDS": json.dumps({"shard": [8, 48]}),
    }
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )

    result = _run_actions_bash(monitor, cwd=tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    budget = json.loads((tmp_path / "calibration-monitor-budget.json").read_text())
    assert budget["estimated_runner_minutes"] == 20
    assert budget["historical_floor_applied"] is True


def _write_sequenced_gh_jobs_stub(workspace, snapshots):
    provider = workspace / "sequenced-provider"
    provider.mkdir()
    for index, snapshot in enumerate(snapshots, 1):
        (provider / f"jobs-{index}.json").write_text(json.dumps(snapshot))
    counter = provider / "counter"
    gh = provider / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f"provider='{provider}'\n"
        "count=0\n"
        "test ! -f \"$provider/counter\" || count=$(cat \"$provider/counter\")\n"
        "count=$((count + 1))\n"
        "printf '%s\\n' \"$count\" > \"$provider/counter\"\n"
        f"last={len(snapshots)}\n"
        "test \"$count\" -le \"$last\" || count=$last\n"
        "cat \"$provider/jobs-$count.json\"\n"
    )
    gh.chmod(0o755)
    return provider, counter


def _monitor_environment(provider, *, shards=None):
    shards = shards or [8, 27, 28, 37, 48, 50, 51, 53]
    return {
        **os.environ,
        "PATH": f"{provider}:{os.environ['PATH']}",
        "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle",
        "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1",
        "CALIBRATION_ID": "cal-test",
        "CALIBRATION_STAGE": "1",
        "RUNNER_MINUTE_CEILING": "12000",
        "EXPECTED_SHARDS": json.dumps({"shard": shards}),
    }


def _run_monitor_collection_with_controlled_boundaries(
    tmp_path, monkeypatch, *, monotonic_values, outcomes,
):
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )
    collection = _first_python_heredoc(monitor)
    sample_dir = tmp_path / "monitor-observations" / "sample-0001"
    sample_dir.mkdir(parents=True)
    calls = []
    outcome_iterator = iter(outcomes)
    monotonic_iterator = iter(monotonic_values)
    timeout_expired = subprocess.TimeoutExpired

    def controlled_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        outcome = next(outcome_iterator)
        if outcome == "timeout":
            raise timeout_expired(command, kwargs["timeout"])
        return SimpleNamespace(
            stdout=json.dumps(outcome).encode(), stderr=b"", returncode=0,
        )

    fake_subprocess = SimpleNamespace(PIPE=-1, run=controlled_run)
    fake_time = SimpleNamespace(monotonic=lambda: next(monotonic_iterator))
    env = _monitor_environment(tmp_path)
    env["SAMPLE_DIR"] = str(sample_dir)
    with monkeypatch.context() as controlled:
        controlled.chdir(tmp_path)
        for key, value in env.items():
            controlled.setenv(key, value)
        controlled.setitem(sys.modules, "subprocess", fake_subprocess)
        controlled.setitem(sys.modules, "time", fake_time)
        try:
            exec(compile(collection, "calibration-monitor-collection", "exec"), {})
        except SystemExit as exc:
            return exc.code, sample_dir, calls
    raise AssertionError("production collection script did not terminate")


def test_calibration_monitor_recovers_only_from_a_fresh_whole_snapshot(tmp_path):
    assert _run_launch_script(tmp_path, stage=1).returncode == 0
    calibration_launch = tmp_path / "calibration-launch"
    calibration_launch.mkdir()
    shutil.copy(tmp_path / "launch-accounting.json", calibration_launch)
    valid = _calibration_jobs()
    incident = json.loads((
        Path(PLUGIN_DIR)
        / "tests/fixtures/calibration-monitor-pagination-incident/jobs-105-121.json"
    ).read_text())
    assert [page["total_count"] for page in incident] == [105, 121]
    assert [len(page["jobs"]) for page in incident] == [100, 21]
    for page in incident:
        for job in page["jobs"]:
            job["run_id"] = 700
            job["run_attempt"] = 1
    provider, counter = _write_sequenced_gh_jobs_stub(tmp_path, [incident, valid])
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )

    result = _run_actions_bash(
        monitor, cwd=tmp_path, env=_monitor_environment(provider),
    )

    assert result.returncode == 0, result.stderr
    assert counter.read_text().strip() == "2"
    assert json.loads((tmp_path / "jobs-monitor.json").read_text()) == valid
    assert json.loads((tmp_path / "calibration-monitor-lifecycle.json").read_text())[
        "action"
    ] == "complete"
    attempts = sorted((tmp_path / "monitor-observations").glob("**/jobs-attempt-*.json"))
    assert [json.loads(path.read_text()) for path in attempts] == [incident, valid]
    assert hashlib.sha256((
        Path(PLUGIN_DIR)
        / "tests/fixtures/calibration-monitor-pagination-incident/jobs-105-121.json"
    ).read_bytes()).hexdigest() == "1f96f207af9c95aa55e376024850516ea33fe269d864b660ace331633a75ea96"


def test_calibration_monitor_persistent_inconsistency_stops_after_three_whole_attempts(
    tmp_path,
):
    assert _run_launch_script(tmp_path, stage=1).returncode == 0
    calibration_launch = tmp_path / "calibration-launch"
    calibration_launch.mkdir()
    shutil.copy(tmp_path / "launch-accounting.json", calibration_launch)
    jobs = _calibration_jobs()
    incident = json.loads((
        Path(PLUGIN_DIR)
        / "tests/fixtures/calibration-monitor-pagination-incident/jobs-105-121.json"
    ).read_text())
    for page in incident:
        for job in page["jobs"]:
            job["run_id"] = 700
            job["run_attempt"] = 1
    provider, counter = _write_sequenced_gh_jobs_stub(
        tmp_path, [incident, incident, incident, jobs],
    )
    (tmp_path / "calibration-monitor-budget.json").write_text(
        '{"passed":true,"sentinel":"stale-continue"}\n'
    )
    (tmp_path / "calibration-monitor-lifecycle.json").write_text(
        '{"action":"continue","sentinel":"stale-continue"}\n'
    )
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )

    result = _run_actions_bash(
        monitor, cwd=tmp_path, env=_monitor_environment(provider),
    )

    assert result.returncode != 0
    assert counter.read_text().strip() == "3"
    budget = json.loads((tmp_path / "calibration-monitor-budget.json").read_text())
    lifecycle = json.loads((tmp_path / "calibration-monitor-lifecycle.json").read_text())
    assert budget["passed"] is False
    assert budget["fresh_accounting"] is False
    assert budget["conservative_worker_exposure_minutes"] == 8 * 35
    assert budget["cancellation_reserve"] == 1200
    assert lifecycle["action"] == "cancel"
    assert lifecycle["passed"] is False
    assert "sentinel" not in budget
    assert "sentinel" not in lifecycle


@pytest.mark.parametrize("fault", ["missing", "duplicate"])
def test_calibration_monitor_never_repairs_missing_or_duplicate_jobs_across_attempts(
    tmp_path, fault,
):
    assert _run_launch_script(tmp_path, stage=1).returncode == 0
    calibration_launch = tmp_path / "calibration-launch"
    calibration_launch.mkdir()
    shutil.copy(tmp_path / "launch-accounting.json", calibration_launch)
    valid = _calibration_jobs()
    malformed = json.loads(json.dumps(valid))
    if fault == "missing":
        malformed[0]["total_count"] += 1
    else:
        malformed[0]["jobs"][1]["id"] = malformed[0]["jobs"][0]["id"]
    provider, counter = _write_sequenced_gh_jobs_stub(
        tmp_path, [malformed, malformed, malformed, valid],
    )
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )

    result = _run_actions_bash(
        monitor, cwd=tmp_path, env=_monitor_environment(provider),
    )

    assert result.returncode != 0
    assert counter.read_text().strip() == "3"
    assert json.loads((tmp_path / "calibration-monitor-lifecycle.json").read_text())[
        "action"
    ] == "cancel"


def test_calibration_monitor_collection_and_publication_bounds_are_frozen():
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )

    assert "MAX_COLLECTION_ATTEMPTS = 3" in monitor
    assert "COLLECTION_ATTEMPT_TIMEOUT_SECONDS = 15" in monitor
    assert "COLLECTION_DEADLINE_SECONDS = 45" in monitor
    assert "subprocess.run(" in monitor
    assert "timeout=min(COLLECTION_ATTEMPT_TIMEOUT_SECONDS, remaining)" in monitor
    assert "os.replace(sample_budget, latest_budget)" in monitor
    assert "os.replace(sample_lifecycle, latest_lifecycle)" in monitor
    assert "cycle_elapsed=$((SECONDS - cycle_started))" in monitor
    assert "sleep $((60 - cycle_elapsed))" in monitor

    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    steps = workflow["jobs"]["calibration-monitor"]["steps"]
    retain = next(step for step in steps if step.get("id") == "retain-monitor")
    cancel = next(step for step in steps if step.get("id") == "cancel-monitor")
    retain_cancel = next(
        step for step in steps
        if step.get("name") == "Retain calibration monitor cancellation outcome"
    )
    assert retain["timeout-minutes"] == 5
    assert cancel["timeout-minutes"] == 2
    assert retain_cancel["timeout-minutes"] == 2
    assert sum(step["timeout-minutes"] for step in (retain, cancel, retain_cancel)) == 9


def test_calibration_monitor_exhausts_three_attempts_when_deadline_allows(
    tmp_path, monkeypatch,
):
    malformed = [{"total_count": 1, "jobs": []}]

    code, sample_dir, calls = _run_monitor_collection_with_controlled_boundaries(
        tmp_path, monkeypatch, monotonic_values=[0, 0, 10, 20],
        outcomes=[malformed, malformed, malformed],
    )

    assert code == 2
    record = json.loads((sample_dir / "collection.json").read_text())
    assert record["attempts_made"] == 3
    assert record["fresh_snapshot"] is False
    assert len(calls) == 3
    assert [call["timeout"] for call in calls] == [15, 15, 15]


def test_calibration_monitor_deadline_exhausts_before_attempt_three(
    tmp_path, monkeypatch,
):
    malformed = [{"total_count": 1, "jobs": []}]

    code, sample_dir, calls = _run_monitor_collection_with_controlled_boundaries(
        tmp_path, monkeypatch, monotonic_values=[0, 0, 20, 45],
        outcomes=[malformed, malformed],
    )

    assert code == 2
    assert len(calls) == 2
    record = json.loads((sample_dir / "collection.json").read_text())
    assert record["attempts_made"] == 2
    assert record["fresh_snapshot"] is False


def test_calibration_monitor_timeout_is_smaller_of_attempt_limit_and_remaining_time(
    tmp_path, monkeypatch,
):
    code, sample_dir, calls = _run_monitor_collection_with_controlled_boundaries(
        tmp_path, monkeypatch, monotonic_values=[0, 0, 35, 45],
        outcomes=["timeout", "timeout"],
    )

    assert code == 2
    assert [call["timeout"] for call in calls] == [15, 10]
    record = json.loads((sample_dir / "collection.json").read_text())
    assert [error["error_class"] for error in record["errors"]] == [
        "TimeoutExpired", "TimeoutExpired",
    ]


def test_calibration_monitor_recovers_after_controlled_failed_attempt(
    tmp_path, monkeypatch,
):
    malformed = [{"total_count": 1, "jobs": []}]
    valid = _calibration_jobs()

    code, sample_dir, calls = _run_monitor_collection_with_controlled_boundaries(
        tmp_path, monkeypatch, monotonic_values=[0, 0, 5],
        outcomes=[malformed, valid],
    )

    assert code == 0
    assert len(calls) == 2
    assert json.loads((tmp_path / "jobs-monitor.json").read_text()) == valid
    record = json.loads((sample_dir / "collection.json").read_text())
    assert record["attempts_made"] == 2
    assert record["fresh_snapshot"] is True


def test_calibration_monitor_exhaustion_publishes_current_fail_closed_decision(
    tmp_path, monkeypatch,
):
    malformed = [{"total_count": 1, "jobs": []}]
    (tmp_path / "calibration-monitor-budget.json").write_text(
        '{"passed":true,"sentinel":"stale"}\n'
    )
    (tmp_path / "calibration-monitor-lifecycle.json").write_text(
        '{"action":"continue","sentinel":"stale"}\n'
    )

    code, _, _ = _run_monitor_collection_with_controlled_boundaries(
        tmp_path, monkeypatch, monotonic_values=[0, 0, 10, 20],
        outcomes=[malformed, malformed, malformed],
    )

    assert code == 2
    budget = json.loads((tmp_path / "calibration-monitor-budget.json").read_text())
    lifecycle = json.loads((tmp_path / "calibration-monitor-lifecycle.json").read_text())
    assert budget["passed"] is False
    assert budget["fresh_accounting"] is False
    assert lifecycle["passed"] is False
    assert json.loads((tmp_path / "calibration-monitor-lifecycle.json").read_text())[
        "action"
    ] == "cancel"
    assert "sentinel" not in budget
    assert "sentinel" not in lifecycle


def test_calibration_monitor_attempts_cancellation_after_publication_failure(tmp_path):
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    steps = workflow["jobs"]["calibration-monitor"]["steps"]
    cancel = next(
        step["run"] for step in steps
        if step.get("name") == "Request cancellation after diagnostic retention"
    )
    (tmp_path / "calibration-monitor-containment-armed.txt").write_text("armed\n")
    provider = tmp_path / "cancel-provider"
    provider.mkdir()
    capture = provider / "capture"
    gh = provider / "gh"
    gh.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > '{capture}'\n")
    gh.chmod(0o755)

    result = _run_actions_bash(cancel, cwd=tmp_path, env={
        **os.environ,
        "PATH": f"{provider}:{os.environ['PATH']}",
        "GITHUB_REPOSITORY": "example/fettle",
        "GITHUB_RUN_ID": "700",
        "MONITOR_OUTCOME": "failure",
        "RETENTION_OUTCOME": "failure",
    })

    assert result.returncode == 0, result.stderr
    assert capture.read_text().splitlines() == [
        "api", "--method", "POST", "repos/example/fettle/actions/runs/700/cancel",
    ]
    assert (tmp_path / "calibration-monitor-cancellation-status.txt").read_text() == "accepted\n"


def test_calibration_monitor_preserves_current_cancel_before_failed_diagnostic_upload():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    steps = workflow["jobs"]["calibration-monitor"]["steps"]
    names = [step.get("name") for step in steps]
    preserve = names.index("Preserve current containment decision before diagnostic retention")
    retain = names.index("Retain monitor accounting before cancellation")
    cancel = names.index("Request cancellation after diagnostic retention")
    cancel_retain = names.index("Retain calibration monitor cancellation outcome")

    assert preserve < retain < cancel < cancel_retain
    assert steps[retain]["continue-on-error"] is True
    assert steps[cancel]["if"] == "always()"
    assert steps[cancel_retain]["if"] == "always() && steps.cancel-monitor.outcome != 'skipped'"


def test_monitor_initialization_failure_retains_typed_nonpass_terminal_accounting(
    tmp_path,
):
    launch_result = _run_launch_script(tmp_path, stage=1)
    assert launch_result.returncode == 0, launch_result.stderr
    launch = json.loads((tmp_path / "launch-accounting.json").read_text())
    launch.pop("prior_runner_minutes")
    calibration_launch = tmp_path / "calibration-launch"
    calibration_launch.mkdir()
    (calibration_launch / "launch-accounting.json").write_text(json.dumps(launch))
    bin_dir = _write_gh_jobs_stub(tmp_path / "monitor-provider", _calibration_jobs())
    env = {
        **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1", "CALIBRATION_ID": "cal-test",
        "CALIBRATION_STAGE": "1", "RUNNER_MINUTE_CEILING": "12000",
        "EXPECTED_SHARDS": json.dumps({"shard": [8, 27, 28, 37, 48, 50, 51, 53]}),
    }
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )
    failed = _run_actions_bash(monitor, cwd=tmp_path, env=env)
    assert failed.returncode != 0
    assert "launch accounting contract is incompatible" in failed.stderr
    diagnostic_log = (tmp_path / "calibration-monitor-error.log").read_text()
    assert "launch accounting contract is incompatible" in diagnostic_log
    assert not (tmp_path / "calibration-monitor-lifecycle.json").exists()

    cancellation = _workflow_step_script(
        "calibration-monitor", "Contain monitor failure and preserve terminal accounting",
    ).replace("${{ steps.monitor.outcome }}", "failure").replace(
        "${{ steps.retain-monitor.outcome }}", "success",
    )
    cancelled = _run_actions_bash(cancellation, cwd=tmp_path, env=env)
    assert cancelled.returncode != 0
    diagnostic = json.loads((tmp_path / "calibration-monitor-budget.json").read_text())
    assert diagnostic["passed"] is False
    assert diagnostic["kind"] == "calibration_monitor_containment"
    assert "launch accounting contract is incompatible" in diagnostic_log
    assert not (tmp_path / "calibration-monitor-lifecycle.json").exists()

    terminal_observer = tmp_path / "terminal-observer"
    terminal_observer.mkdir()
    shutil.copy(tmp_path / "calibration-monitor-budget.json", terminal_observer)
    accounting = _workflow_step_script(
        "calibration-accounting", "Collect cumulative job accounting",
    )
    blocked = _run_actions_bash(accounting, cwd=tmp_path, env={
        **env, "RESUME_RUN_ID": "", "PRIOR_RUN_ID": "",
    })
    assert blocked.returncode != 0
    assert "calibration-monitor-lifecycle.json" in blocked.stderr
    assert not (tmp_path / "calibration-accounting.json").exists()

    fallback = _workflow_step_script(
        "calibration-accounting", "Preserve typed terminal accounting on containment",
    )
    preserved = _run_actions_bash(fallback, cwd=tmp_path, env={
        **env, "RESUME_RUN_ID": "", "PRIOR_RUN_ID": "",
    })
    assert preserved.returncode == 0, preserved.stderr
    terminal = json.loads((tmp_path / "calibration-accounting.json").read_text())
    assert terminal["kind"] == "calibration_budget_decision"
    assert terminal["passed"] is False
    assert terminal["terminal_accounting_status"] == "indeterminate"
    assert terminal["observed_runner_minutes_floor"] == 8
    assert terminal["historical_charged_runner_minutes_floor"] is None
    assert terminal["missing_evidence"] == ["monitor_lifecycle"]


def test_terminal_accounting_fallback_survives_accounting_import_failure(tmp_path):
    jobs = tmp_path / "jobs-current.json"
    jobs.write_text(json.dumps(_calibration_jobs()))
    script = _workflow_step_script(
        "calibration-accounting", "Preserve typed terminal accounting on containment",
    ).replace("from fettle.staged_preflight import account_runner_minutes", "raise ImportError('missing')")

    preserved = _run_actions_bash(script, cwd=tmp_path, env={
        **os.environ, "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_RUN_ID": "700", "GITHUB_RUN_ATTEMPT": "1",
        "CALIBRATION_ID": "cal-test", "CALIBRATION_STAGE": "1",
        "RUNNER_MINUTE_CEILING": "12000",
    })

    assert preserved.returncode == 0, preserved.stderr
    terminal = json.loads((tmp_path / "calibration-accounting.json").read_text())
    assert terminal["passed"] is False
    assert terminal["terminal_accounting_status"] == "indeterminate"
    assert terminal["observed_runner_minutes_floor"] is None
    assert terminal["containment_reason"] == "ImportError: missing"
    assert terminal["evidence_sha256"]["jobs_current"] == hashlib.sha256(
        jobs.read_bytes()
    ).hexdigest()


def test_actual_terminal_accounting_output_is_accepted_once_by_next_stage_launch(tmp_path):
    launch_result = _run_launch_script(tmp_path, stage=1)
    assert launch_result.returncode == 0, launch_result.stderr
    calibration_launch = tmp_path / "calibration-launch"
    calibration_launch.mkdir()
    shutil.copy(tmp_path / "launch-accounting.json", calibration_launch)
    bin_dir = _write_gh_jobs_stub(tmp_path / "monitor-provider", _calibration_jobs())
    env = {
        **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1", "CALIBRATION_ID": "cal-test",
        "CALIBRATION_STAGE": "1", "RUNNER_MINUTE_CEILING": "12000",
        "EXPECTED_SHARDS": json.dumps({"shard": [8, 27, 28, 37, 48, 50, 51, 53]}),
    }
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )
    monitored = _run_actions_bash(monitor, cwd=tmp_path, env=env)
    assert monitored.returncode == 0, monitored.stderr
    terminal_observer = tmp_path / "terminal-observer"
    terminal_observer.mkdir()
    shutil.copy(tmp_path / "calibration-monitor-budget.json", terminal_observer)
    shutil.copy(tmp_path / "calibration-monitor-lifecycle.json", terminal_observer)
    accounting = _workflow_step_script(
        "calibration-accounting", "Collect cumulative job accounting",
    )
    reconciled = _run_actions_bash(accounting, cwd=tmp_path, env={
        **env, "RESUME_RUN_ID": "", "PRIOR_RUN_ID": "",
    })
    assert reconciled.returncode == 0, reconciled.stderr
    terminal = json.loads((tmp_path / "calibration-accounting.json").read_text())
    assert terminal["stage"] == "1"
    assert terminal["calibration_id"] == "cal-test"
    assert terminal["ceiling"] == 12000
    assert terminal["passed"] is True
    assert terminal["charged_runner_minutes"] >= terminal["estimated_runner_minutes"]

    next_stage = tmp_path / "next-stage"
    next_stage.mkdir()
    next_launch = _run_launch_script(
        next_stage, stage=2, prior="700", predecessor=terminal,
    )
    assert next_launch.returncode == 0, next_launch.stderr
    successor = json.loads((next_stage / "launch-accounting.json").read_text())
    effective = max(
        terminal["charged_runner_minutes"], terminal["estimated_runner_minutes"],
    )
    assert successor["prior_runner_minutes"] == effective
    assert successor["estimated_runner_minutes"] == effective + 8


def test_resumed_stage_monitor_lifecycle_reaches_terminal_accounting_once(tmp_path):
    predecessor = _cumulative_accounting(
        stage=2, run_ids=("381", "482"), estimated=240, charged=245,
    )
    launched = _run_launch_script(
        tmp_path, stage=2, resume="482", prior="381", predecessor=predecessor,
    )
    assert launched.returncode == 0, launched.stderr
    calibration_launch = tmp_path / "calibration-launch"
    calibration_launch.mkdir()
    shutil.copy(tmp_path / "launch-accounting.json", calibration_launch)
    shard = WAVES["wave-2"][0]
    bin_dir = _write_gh_jobs_stub(
        tmp_path / "provider", _calibration_jobs(shards=(shard,)), predecessor,
    )
    env = {
        **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1", "CALIBRATION_ID": "cal-test",
        "CALIBRATION_STAGE": "2", "RUNNER_MINUTE_CEILING": "12000",
        "EXPECTED_SHARDS": json.dumps({"shard": [shard]}),
    }
    monitor = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )
    monitored = _run_actions_bash(monitor, cwd=tmp_path, env=env)
    assert monitored.returncode == 0, monitored.stderr
    terminal_observer = tmp_path / "terminal-observer"
    terminal_observer.mkdir()
    shutil.copy(tmp_path / "calibration-monitor-budget.json", terminal_observer)
    shutil.copy(tmp_path / "calibration-monitor-lifecycle.json", terminal_observer)
    accounting = _workflow_step_script(
        "calibration-accounting", "Collect cumulative job accounting",
    )

    reconciled = _run_actions_bash(accounting, cwd=tmp_path, env={
        **env, "RESUME_RUN_ID": "482", "PRIOR_RUN_ID": "381",
    })

    assert reconciled.returncode == 0, reconciled.stderr
    terminal = json.loads((tmp_path / "calibration-accounting.json").read_text())
    assert terminal["source_lineage"] == [
        {"run_id": "381", "run_attempt": "1"},
        {"run_id": "482", "run_attempt": "1"},
        {"run_id": "700", "run_attempt": "1"},
    ]
    assert terminal["estimated_runner_minutes"] == 301
    assert terminal["charged_runner_minutes"] == 301


def test_actual_terminal_accounting_rejects_failed_prior_record(tmp_path):
    stage_shard = WAVES["wave-2"][0]
    terminal_observer = tmp_path / "terminal-observer"
    terminal_observer.mkdir()
    monitor = {
        **_operational_source("700", 8),
        "stage": "2", "calibration_id": "cal-test", "ceiling": 12000,
        "charged_runner_minutes": 8, "passed": True,
    }
    (terminal_observer / "calibration-monitor-budget.json").write_text(json.dumps(monitor))
    (terminal_observer / "calibration-monitor-lifecycle.json").write_text(json.dumps(
        _complete_calibration_lifecycle("2", [stage_shard])
    ))
    prior = _cumulative_accounting(stage=1, run_ids=("381",), estimated=20)
    prior["passed"] = False
    bin_dir = _write_gh_jobs_stub(
        tmp_path / "provider", _calibration_jobs(shards=(stage_shard,)), prior,
    )
    accounting = _workflow_step_script(
        "calibration-accounting", "Collect cumulative job accounting",
    )
    result = _run_actions_bash(accounting, cwd=tmp_path, env={
        **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1", "CALIBRATION_ID": "cal-test",
        "CALIBRATION_STAGE": "2", "RUNNER_MINUTE_CEILING": "12000",
        "RESUME_RUN_ID": "", "PRIOR_RUN_ID": "381",
    })

    assert result.returncode != 0
    assert "prior cumulative accounting is incompatible" in result.stderr
    assert not (tmp_path / "calibration-accounting.json").exists()


def test_calibration_monitor_uses_derived_lifecycle_and_leaves_shutdown_room():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    monitor = workflow["jobs"]["calibration-monitor"]
    source = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "335" in monitor["timeout-minutes"]
    assert "100" in monitor["timeout-minutes"]
    assert '{"1":8,"2":16}[stage]' in source
    assert "calibration_observer_contract(len(matrix)" in source
    assert "calibration_stage_3_observer_contract(matrix)" in source
    assert "evaluate_calibration_observer" in source
    assert "calibration-observer-contract.json" in source
    assert "calibration-monitor-lifecycle.json" in source
    assert '[[ "$action" == "cancel" ]] && exit 2' in source
    assert "deadline=$((SECONDS + 2100))" not in source


def test_stage_3_observer_readiness_loss_is_fail_closed_without_cancelling_accounting():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    jobs = workflow["jobs"]
    ready = jobs["calibration-stage-3-observer-ready"]
    monitor = jobs["calibration-monitor"]
    watchdog = jobs["calibration-stage-3-observer-watchdog"]

    producer = jobs["calibration-stage-3-observer-readiness"]
    assert producer["needs"] == ["prepare", "calibration-launch-gate"]
    assert ready["needs"] == [
        "prepare", "calibration-launch-gate", "calibration-stage-3-observer-readiness",
    ]
    assert ready["if"].startswith("always() &&")
    assert ready["timeout-minutes"] == 10
    assert jobs["calibration-stage-3-batch-1"]["needs"] == [
        "prepare", "calibration-stage-3-observer-ready",
    ]
    assert any(step.get("name") == "Establish observer readiness" for step in producer["steps"])
    assert any(step.get("name") == "Publish observer readiness" for step in producer["steps"])
    assert not any("observer readiness" in step.get("name", "").lower() for step in monitor["steps"])
    assert watchdog["needs"] == "calibration-stage-3-observer-ready"
    assert watchdog["timeout-minutes"] == 335
    watchdog_script = next(
        step["run"] for step in watchdog["steps"]
        if step.get("name") == "Cancel if observer is lost before valid completion"
    )
    assert "calibration-monitor-lifecycle.json" in watchdog_script
    assert "load_api_jobs_pages" in watchdog_script
    assert "/actions/runs/$GITHUB_RUN_ID/cancel" not in watchdog_script
    liveness_script = next(
        step["run"] for step in jobs["calibration-stage-3-observer-live-2"]["steps"]
        if step.get("name") == "Require live observer before next batch"
    )
    assert "load_api_jobs_pages" in liveness_script
    assert "observer-live-jobs.json" in liveness_script
    for number in range(2, 8):
        live = jobs[f"calibration-stage-3-observer-live-{number}"]
        batch = jobs[f"calibration-stage-3-batch-{number}"]
        assert live["needs"] == f"calibration-stage-3-admit-{number}"
        assert live["permissions"] == {"actions": "write", "contents": "read"}
        assert f"calibration-stage-3-observer-live-{number}" in batch["needs"]


def test_initial_observer_admission_uses_current_run_action_and_retains_visible_failure():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    jobs = workflow["jobs"]
    ready = jobs["calibration-stage-3-observer-ready"]
    steps = ready["steps"]
    downloads = [step for step in steps if step.get("name", "").startswith("Download exact observer readiness attempt")]
    retain = next(step for step in steps if step.get("name") == "Retain initial admission result")
    contain = next(step for step in steps if step.get("name") == "Preserve failed initial admission")
    source = "\n".join(step.get("run", "") for step in steps)

    assert len(downloads) == 3
    assert all(step["uses"] == "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" for step in downloads)
    assert all(
        "mutation-readback-probe-ready-{0}-{1}" in step["with"]["name"]
        and "mutation-calibration-observer-ready-{0}-{1}" in step["with"]["name"]
        for step in downloads
    )
    assert downloads[1]["if"] == "always() && steps.readiness-download-1.outcome != 'success'"
    assert "steps.readiness-download-2.outcome != 'success'" in downloads[2]["if"]
    assert retain["if"] == "always()"
    assert contain["if"] == "always()"
    assert "gh run download" not in source
    assert "2>/dev/null" not in source
    assert "validate_calibration_observer_readiness" in source
    assert "provider_error_class" in source
    assert "provider_error_detail" not in source
    assert "provider-attempts.jsonl" in source
    assert "provider_retries_exhausted" in source
    assert "access_denied" in source
    assert "transient_provider_error" in source
    assert "provider_resource_unavailable" in source
    assert "artifact_download_retries_exhausted" in source
    assert "observer-current-jobs.json" in source
    assert "observer is not live at initial admission" in source
    assert source.count("load_api_jobs_pages") >= 3


def test_monitor_contains_failed_initial_admission_without_waiting_worker_deadline():
    source = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )

    assert "calibration_stage_3_initial_admission_status" in source
    assert "load_api_jobs_pages(Path(\"jobs-monitor.json\"))" in source
    assert "initial_admission_status=initial_admission_status" in source
    assert 'initial_admission_status = "not_applicable"' in source
    assert 'initial_admission_status = calibration_stage_3_initial_admission_status(jobs)' in source


def test_monitor_contains_terminal_readiness_route_without_initial_admission(tmp_path):
    source = _workflow_step_script(
        "calibration-monitor", "Monitor active usage and request bounded cancellation",
    )
    assert "calibration_stage_3_initial_admission_status(jobs)" in source
    assert '[[ "$action" == "cancel" ]] && exit 2' in source

    selected = [WAVES["wave-3"][0]]
    contract = calibration_stage_3_observer_contract(selected)
    jobs = [{
        "name": "mutation (publish stage 3 observer readiness)",
        "status": "completed", "conclusion": "success",
    }]
    from scripts.staged_preflight import (
        calibration_stage_3_initial_admission_status,
        evaluate_calibration_observer,
    )

    status = calibration_stage_3_initial_admission_status(jobs)
    result = evaluate_calibration_observer(
        contract, jobs, elapsed_seconds=60, budget_passed=True,
        admitted_shards=[], initial_admission_status=status,
    )

    assert status == "failure"
    assert result["action"] == "cancel"
    assert result["reason"] == "initial stage 3 admission failed"


def test_actual_readiness_scripts_emit_and_validate_current_attempt_payload(tmp_path):
    producer = _workflow_step_script(
        "calibration-stage-3-observer-readiness", "Establish observer readiness",
    )
    consumer = _workflow_step_script(
        "calibration-stage-3-observer-ready", "Validate exact observer readiness",
    )
    monitor = {
        "id": 91, "name": "mutation (monitor calibration budget)",
        "status": "in_progress", "conclusion": None,
    }
    pages = [{"total_count": 1, "jobs": [monitor]}]
    provider = tmp_path / "provider"
    provider.mkdir()
    jobs_path = provider / "jobs.json"
    jobs_path.write_text(json.dumps(pages))
    gh = provider / "gh"
    gh.write_text(f"#!/bin/sh\ncat '{jobs_path}'\n")
    gh.chmod(0o755)
    candidate = "a" * 40
    env = {
        **os.environ, "PATH": f"{provider}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "2", "GITHUB_SHA": candidate,
        "GITHUB_WORKFLOW_SHA": candidate, "CALIBRATION_ID": "cal-readback",
        "ARTIFACT_NAME": "mutation-calibration-observer-ready-700-2",
    }

    produced = _run_actions_bash(producer, cwd=tmp_path, env=env)
    assert produced.returncode == 0, produced.stderr
    observer_ready = tmp_path / "observer-ready-1"
    observer_ready.mkdir()
    shutil.copy(tmp_path / "observer-readiness.json", observer_ready)
    shutil.copy(tmp_path / "observer-ready-jobs.json", observer_ready)

    validated = _run_actions_bash(consumer, cwd=tmp_path, env={
        **env, "DOWNLOAD_OUTCOME_1": "success",
        "DOWNLOAD_OUTCOME_2": "skipped", "DOWNLOAD_OUTCOME_3": "skipped",
    })

    assert validated.returncode == 0, validated.stderr
    readiness = json.loads((tmp_path / "observer-readiness.json").read_text())
    admission = json.loads((tmp_path / "initial-admission.json").read_text())
    assert readiness["monitor_job_id"] == 91
    assert readiness["artifact_name"] == env["ARTIFACT_NAME"]
    assert admission["passed"] is True
    assert admission["artifact_download_attempt"] == 1
    assert admission["monitor_job_id"] == 91
    assert admission["provider_attempts"][0]["outcome"] == "success"


def test_actual_initial_admission_script_classifies_exhausted_provider_errors(tmp_path):
    consumer = _workflow_step_script(
        "calibration-stage-3-observer-ready", "Validate exact observer readiness",
    )
    provider = tmp_path / "provider"
    provider.mkdir()
    gh = provider / "gh"
    gh.write_text("#!/bin/sh\necho 'HTTP 503 signed_url=redacted' >&2\nexit 1\n")
    gh.chmod(0o755)
    candidate = "a" * 40
    result = _run_actions_bash(consumer, cwd=tmp_path, env={
        **os.environ, "PATH": f"{provider}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "2", "GITHUB_SHA": candidate,
        "GITHUB_WORKFLOW_SHA": candidate, "CALIBRATION_ID": "cal-readback",
        "ARTIFACT_NAME": "mutation-calibration-observer-ready-700-2",
        "DOWNLOAD_OUTCOME_1": "failure", "DOWNLOAD_OUTCOME_2": "failure",
        "DOWNLOAD_OUTCOME_3": "failure",
    })

    assert result.returncode != 0
    admission = json.loads((tmp_path / "initial-admission.json").read_text())
    attempts = admission["provider_attempts"]
    assert admission["passed"] is False
    assert admission["provider_error_class"] == "provider_retries_exhausted"
    assert admission["artifact_download_attempt"] == 0
    assert [attempt["error_class"] for attempt in attempts] == [
        "transient_provider_error", "transient_provider_error", "transient_provider_error",
    ]
    assert "signed_url" not in (tmp_path / "provider-attempts.jsonl").read_text()
    assert not (tmp_path / "provider-error.tmp").exists()


def test_stage_3_monitor_accounts_support_costs_and_validates_floor_provenance():
    source = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    monitor = source.split("\n  calibration-monitor:", 1)[1].split(
        "\n  calibration-stage-3-observer-live-2:", 1,
    )[0]

    assert 'account_runner_minutes(' in monitor
    assert 'Path("jobs-monitor.json")' in monitor
    assert 'retain_historical_accounting_floor(usage, history)' in monitor
    assert 'decision.get("expected_run_id") != os.environ["GITHUB_RUN_ID"]' in monitor
    assert 'decision.get("calibration_id") != os.environ["CALIBRATION_ID"]' in monitor
    assert 'cancellation_reserve=1200' in monitor
    assert 'monitor-history' in monitor
    assert 'final_batch_jobs = [' in monitor
    assert 'route_complete=route_complete' in monitor
    assert 'steps.retain-monitor.outcome' in monitor
    assert "/actions/runs/$GITHUB_RUN_ID/cancel" in monitor
    workflow = yaml.safe_load(source)
    retain = next(
        step for step in workflow["jobs"]["calibration-monitor"]["steps"]
        if step.get("name") == "Retain monitor accounting before cancellation"
    )
    assert retain["timeout-minutes"] == 5
    contain = next(
        step for step in workflow["jobs"]["calibration-monitor"]["steps"]
        if step.get("name") == "Contain monitor failure and preserve terminal accounting"
    )
    assert contain["if"] == "always()"
    cancel = next(
        step for step in workflow["jobs"]["calibration-monitor"]["steps"]
        if step.get("name") == "Request cancellation after diagnostic retention"
    )
    assert cancel["if"] == "always()"


def test_terminal_accounting_and_aggregate_require_observer_package():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    jobs = workflow["jobs"]
    accounting = jobs["calibration-accounting"]
    aggregate = jobs["aggregate"]
    source = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    accounting_source = source.split("\n  calibration-accounting:", 1)[1].split(
        "\n  aggregate:", 1,
    )[0]

    assert accounting["timeout-minutes"] == 15
    assert aggregate["timeout-minutes"] == 30
    assert jobs["evidence-readback"]["timeout-minutes"] == 10
    assert "Download terminal observer evidence" in accounting_source
    assert 'lifecycle.get("action") != "complete"' in accounting_source
    assert 'len(admission_floors) != 6' in accounting_source
    assert 'sorted(admitted_batches) != list(range(1, 7))' in accounting_source
    assert 'support_bounds={' in accounting_source
    assert '"mutation (calibration accounting)": 15' in accounting_source
    assert '"mutation (assemble evidence)": 30' in accounting_source
    assert '"mutation evidence": 10' in accounting_source
    assert 'monitor.get("expected_run_id") != os.environ["GITHUB_RUN_ID"]' in accounting_source
    assert 'monitor.get("expected_run_attempt") != os.environ["GITHUB_RUN_ATTEMPT"]' in accounting_source
    assert "Preserve typed terminal accounting on containment" in accounting_source
    assert '"terminal_accounting_status": "indeterminate"' in accounting_source
    assert '"kind": "calibration_budget_decision"' in accounting_source
    assert any(
        step.get("name") == "Require successful bounded accounting before publication"
        for step in aggregate["steps"]
    )
    assert any(
        step.get("name") == "Bind successful accounting readback to calibration evidence"
        for step in aggregate["steps"]
    )
    assert 'report["accounting_sha256"]' in source
    assert 'name: mutation-calibration-accounting-${{ github.run_id }}' in source
    assert 'report.get("accounting_sha256")' in source


def test_primary_accounting_publication_failure_emits_exact_log_fallback(tmp_path):
    payload = {
        "schema_version": "1", "kind": "calibration_budget_decision",
        "passed": False, "billing_authority": False,
        "terminal_accounting_status": "indeterminate", "stage": "3",
        "calibration_id": "cal-test", "expected_run_id": "700",
        "expected_run_attempt": "1", "observed_runner_minutes_floor": 8,
        "historical_charged_runner_minutes_floor": 291.99,
    }
    exact = json.dumps(payload, indent=2).encode() + b"\n"
    (tmp_path / "calibration-accounting.json").write_bytes(exact)
    script = _workflow_step_script(
        "calibration-accounting", "Preserve exact accounting bytes in the job log",
    )
    env = {
        **os.environ, "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_SHA": "a" * 40,
        "GITHUB_WORKFLOW_REF": "example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
        "GITHUB_WORKFLOW_SHA": "a" * 40, "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1", "CALIBRATION_ID": "cal-test",
        "CALIBRATION_STAGE": "3", "PRIMARY_UPLOAD_OUTCOME": "failure",
    }

    result = _run_actions_bash(script, cwd=tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    from fettle.staged_preflight import recover_calibration_accounting_log_envelope
    recovered = recover_calibration_accounting_log_envelope(
        result.stdout.encode(), repository="example/fettle", candidate_sha="a" * 40,
        workflow_ref=env["GITHUB_WORKFLOW_REF"], workflow_sha="a" * 40,
        run_id="700", run_attempt="1", calibration_id="cal-test", stage="3",
    )
    assert recovered == exact


def test_accounting_log_recovery_script_preserves_bytes_but_remains_non_authoritative(tmp_path):
    from fettle.staged_preflight import (
        build_calibration_accounting_log_envelope,
        calibration_accounting_log_records,
    )
    payload = json.dumps({
        "schema_version": "1", "kind": "calibration_budget_decision",
        "passed": True, "billing_authority": False, "stage": "3",
        "calibration_id": "cal-test", "expected_run_id": "700",
        "expected_run_attempt": "1", "source_lineage": [],
    }, indent=2).encode() + b"\n"
    envelope = build_calibration_accounting_log_envelope(
        payload, repository="example/fettle", candidate_sha="a" * 40,
        workflow_ref="example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
        workflow_sha="a" * 40, run_id="700", run_attempt="1",
        calibration_id="cal-test", stage="3", primary_upload_outcome="failure",
    )
    provider = tmp_path / "provider"
    provider.mkdir()
    jobs = [{"total_count": 1, "jobs": [{
        "id": 77, "run_id": 700, "run_attempt": 1,
        "head_sha": "a" * 40, "name": "mutation (calibration accounting)",
        "status": "completed", "conclusion": "failure", "steps": [
            {"name": "Collect cumulative job accounting", "conclusion": "success"},
            {"name": "Preserve typed terminal accounting on containment", "conclusion": "skipped"},
            {"name": "Preserve exact accounting bytes in the job log", "conclusion": "success"},
            {"name": "Keep primary accounting publication failure visible", "conclusion": "failure"},
        ],
    }]}]
    (provider / "jobs.json").write_text(json.dumps(jobs))
    (provider / "log.txt").write_text("\n".join(calibration_accounting_log_records(envelope)) + "\n")
    bin_dir = provider / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f"jobs='{provider / 'jobs.json'}'\n"
        f"log='{provider / 'log.txt'}'\n"
        "case \"$*\" in *'/jobs?per_page=100'*) cat \"$jobs\";; *'/logs'*) cat \"$log\";; *) exit 2;; esac\n"
    )
    gh.chmod(0o755)
    script = _workflow_step_script(
        "aggregate", "Recover failed primary accounting publication from exact job log",
    )
    env = {
        **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_SHA": "a" * 40,
        "GITHUB_WORKFLOW_REF": "example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
        "GITHUB_WORKFLOW_SHA": "a" * 40, "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1", "CALIBRATION_ID": "cal-test", "CALIBRATION_STAGE": "3",
        "GH_TOKEN": "test",
    }

    result = _run_actions_bash(script, cwd=tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "retained-accounting/calibration-accounting.json").read_bytes() == payload
    readback = json.loads((tmp_path / "accounting-readback.json").read_text())
    assert readback["available"] is True
    assert readback["passed"] is False
    assert readback["authoritative_predecessor"] is False


def test_both_accounting_channels_unavailable_is_explicit_nonpass(tmp_path):
    provider = tmp_path / "provider"
    provider.mkdir()
    bin_dir = provider / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nexit 1\n")
    gh.chmod(0o755)
    script = _workflow_step_script(
        "aggregate", "Recover failed primary accounting publication from exact job log",
    )
    env = {
        **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_SHA": "a" * 40,
        "GITHUB_WORKFLOW_REF": "example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
        "GITHUB_WORKFLOW_SHA": "a" * 40, "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1", "CALIBRATION_ID": "cal-test", "CALIBRATION_STAGE": "3",
        "GH_TOKEN": "test",
    }

    result = _run_actions_bash(script, cwd=tmp_path, env=env)

    assert result.returncode != 0
    readback = json.loads((tmp_path / "accounting-readback.json").read_text())
    assert readback == {
        "schema_version": "1", "kind": "calibration_accounting_readback",
        "passed": False, "available": False, "authoritative_predecessor": False,
        "reason": "exact-attempt accounting job metadata is unavailable",
    }


def test_accounting_retention_workflow_keeps_failure_visible_and_tail_bounded():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    accounting = workflow["jobs"]["calibration-accounting"]
    aggregate = workflow["jobs"]["aggregate"]
    retain = _workflow_step("calibration-accounting", "Retain calibration accounting")
    visible = _workflow_step(
        "calibration-accounting", "Keep primary accounting publication failure visible",
    )
    recovery = _workflow_step(
        "aggregate", "Recover failed primary accounting publication from exact job log",
    )

    assert accounting["timeout-minutes"] == 15
    assert aggregate["timeout-minutes"] == 30
    assert retain["continue-on-error"] is True
    assert visible["if"] == "always()"
    assert recovery["timeout-minutes"] == 5
    assert "for attempt in 1 2 3" in recovery["run"]
    assert workflow["permissions"] == {"actions": "read", "contents": "read"}


def test_live_retention_probe_is_synthetic_bounded_and_non_authoritative():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/calibration-retention-probe.yml").read_text()
    )
    assert workflow["permissions"] == {"actions": "read", "contents": "read"}
    assert set(workflow["jobs"]) == {"producer", "reader"}
    assert sum(job["timeout-minutes"] for job in workflow["jobs"].values()) == 20
    assert workflow["jobs"]["reader"]["if"] == "always()"
    assert workflow["jobs"]["reader"]["needs"] == "producer"
    text = (Path(PLUGIN_DIR) / ".github/workflows/calibration-retention-probe.yml").read_text()
    assert "245 * 1024" in text
    assert "for attempt in 1 2 3" in text
    reader = next(
        step["run"] for step in workflow["jobs"]["reader"]["steps"]
        if step.get("name") == "Read and validate exact producer log"
    )
    assert "gh api --allow-escape-sequences" in reader
    assert '"repos/$GITHUB_REPOSITORY/actions/jobs/$job_id/logs"' in reader
    assert '"authoritative_predecessor": False' in text
    assert '"passed": False' in text
    assert '"provider_path_verified": True' in text
    assert "mutation" not in " ".join(workflow["jobs"])


def test_live_retention_probe_preserves_primary_failure_after_fallback():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/calibration-retention-probe.yml").read_text()
    )
    producer = workflow["jobs"]["producer"]["steps"]
    primary = next(step for step in producer if step.get("id") == "primary-publication")
    emit = next(step for step in producer if step.get("id") == "emit-fallback")
    visible = next(
        step for step in producer if step.get("name") == "Preserve deliberate primary failure"
    )
    assert "continue-on-error" not in primary
    assert primary["with"]["if-no-files-found"] == "error"
    assert primary["with"]["retention-days"] == 1
    assert emit["if"] == "always() && steps.primary-publication.outcome == 'failure'"
    assert visible["if"] == "always()"
    assert "exit 2" in visible["run"]


def test_live_retention_probe_is_called_only_by_existing_dispatch_workflow():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    modes = workflow[True]["workflow_dispatch"]["inputs"]["mode"]["options"]
    call = workflow["jobs"]["retention-provider-probe"]
    assert "retention-probe" in modes
    assert call["if"] == (
        "github.event_name == 'workflow_dispatch' && "
        "github.event.inputs.mode == 'retention-probe'"
    )
    assert call["uses"] == "./.github/workflows/calibration-retention-probe.yml"
    assert call["permissions"] == {"actions": "read", "contents": "read"}
    for job_name in ("prepare", "calibration-launch-gate", "full-shard", "aggregate"):
        assert "retention-probe" in workflow["jobs"][job_name]["if"]


def test_live_retention_probe_reader_requires_exact_provider_outcomes():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/calibration-retention-probe.yml").read_text()
    )
    reader = next(
        step for step in workflow["jobs"]["reader"]["steps"]
        if step.get("name") == "Read and validate exact producer log"
    )["run"]
    for required in (
        'job.get("head_sha") == os.environ["CANDIDATE_SHA"]',
        'job.get("conclusion") == "failure"',
        '"Deliberately fail primary artifact publication"',
        '"Emit exact diagnostic fallback records"',
        '"Preserve deliberate primary failure"',
        "recovered != exact",
    ):
        assert required in reader


def test_live_retention_probe_actual_producer_scripts_reconstruct_exact_bytes(tmp_path):
    env = {
        **os.environ, "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_SHA": "a" * 40,
        "GITHUB_WORKFLOW_REF": "example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
        "GITHUB_WORKFLOW_SHA": "a" * 40, "GITHUB_RUN_ID": "700",
        "GITHUB_RUN_ATTEMPT": "1", "PROBE_ID": "probe-local",
        "PRIMARY_UPLOAD_OUTCOME": "failure",
    }
    generate = _run_actions_bash(
        _retention_probe_step_script("producer", "Generate bounded synthetic accounting bytes"),
        cwd=tmp_path, env=env,
    )
    emit = _run_actions_bash(
        _retention_probe_step_script("producer", "Emit exact diagnostic fallback records"),
        cwd=tmp_path, env=env,
    )

    assert generate.returncode == 0, generate.stderr
    assert emit.returncode == 0, emit.stderr
    exact = (tmp_path / "synthetic-accounting.json").read_bytes()
    assert 245 * 1024 < len(exact) <= 256 * 1024
    from fettle.staged_preflight import recover_calibration_accounting_log_envelope
    recovered = recover_calibration_accounting_log_envelope(
        emit.stdout.encode(), repository="example/fettle", candidate_sha="a" * 40,
        workflow_ref=env["GITHUB_WORKFLOW_REF"], workflow_sha="a" * 40,
        run_id="700", run_attempt="1", calibration_id="probe-local", stage="1",
    )
    assert recovered == exact
    assert len(emit.stdout.splitlines()) <= 32
    assert max(map(len, emit.stdout.splitlines())) < 13 * 1024


def test_live_retention_probe_rejects_missing_or_mismatched_identity(tmp_path):
    script = _retention_probe_step_script("producer", "Validate exact probe identity")
    base = {**os.environ, "GITHUB_SHA": "a" * 40, "CANDIDATE_SHA": "a" * 40}
    missing = _run_actions_bash(script, cwd=tmp_path, env={**base, "PROBE_ID": ""})
    mismatch = _run_actions_bash(
        script, cwd=tmp_path,
        env={**base, "CANDIDATE_SHA": "b" * 40, "PROBE_ID": "probe-local"},
    )
    assert missing.returncode != 0
    assert "probe_id is malformed" in missing.stderr
    assert mismatch.returncode != 0
    assert "dispatch SHA differs from candidate_sha" in mismatch.stderr


def test_live_retention_probe_contains_no_mutation_execution_command():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/calibration-retention-probe.yml").read_text()
    )
    scripts = "\n".join(
        step.get("run", "") for job in workflow["jobs"].values()
        for step in job["steps"]
    )
    assert "fettle mutation" not in scripts
    assert "fettle.mutation_test" not in scripts
    assert "mutmut" not in scripts


def test_readback_probe_reuses_registered_production_path_and_is_zero_worker():
    workflow_path = Path(PLUGIN_DIR) / ".github/workflows/mutation.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    jobs = workflow["jobs"]
    modes = workflow[True]["workflow_dispatch"]["inputs"]["mode"]["options"]

    assert "readback-probe" in modes
    assert not (Path(PLUGIN_DIR) / ".github/workflows/calibration-readback-probe.yml").exists()
    assert "readback-probe" in jobs["calibration-stage-3-observer-readiness"]["if"]
    assert "readback-probe" in jobs["calibration-stage-3-observer-ready"]["if"]
    assert jobs["calibration-stage-3-observer-ready"]["needs"] == [
        "prepare", "calibration-launch-gate", "calibration-stage-3-observer-readiness",
    ]
    finalizer = jobs["readback-probe-finalizer"]
    assert finalizer["if"] == (
        "github.event_name == 'workflow_dispatch' && "
        "github.event.inputs.mode == 'readback-probe'"
    )
    assert finalizer["timeout-minutes"] == 10
    assert finalizer["permissions"] == {"actions": "read", "contents": "read"}
    finalizer_source = "\n".join(step.get("run", "") for step in finalizer["steps"])
    assert "mutation_workers_started\": 0" in finalizer_source
    assert '"passed": False' in finalizer_source
    assert '"billing_authority": False' in finalizer_source
    assert '"authoritative_predecessor": False' in finalizer_source
    assert '"qualification_eligible": False' in finalizer_source
    assert "probe_id is reused or its provider identity is indeterminate" in finalizer_source
    assert "load_api_jobs_pages" in finalizer_source
    assert "load_api_workflow_run_pages" in finalizer_source
    assert "provider_error_class=access_denied" in finalizer_source
    assert "provider_error_class=transient_provider_error" in finalizer_source
    assert "provider_error_class=provider_resource_unavailable" in finalizer_source
    assert finalizer_source.count("rm -f provider-error.tmp") >= 2
    observe_source = _workflow_step_script(
        "readback-probe-finalizer", "Validate probe identity and zero-worker finalization",
    )
    assert "readback-probe-result.json" not in observe_source
    finalize_source = _workflow_step_script(
        "readback-probe-finalizer", "Validate retained probe admission and finalize",
    )
    assert "retained-probe-admission/initial-admission.json" in finalize_source
    assert "validate_readback_probe_admission" in finalize_source
    assert "probe admission contains duplicate keys" in finalize_source
    assert "fettle mutation" not in finalizer_source
    assert "fettle.mutation_test" not in finalizer_source
    assert "mutmut" not in finalizer_source

    worker_jobs = [
        "prepare", "calibration-launch-gate", "full-shard", "calibration-monitor",
        "calibration-accounting", "aggregate", "evidence-readback",
        *[f"calibration-stage-3-batch-{number}" for number in range(1, 8)],
        *[f"calibration-stage-3-admit-{number}" for number in range(2, 8)],
    ]
    for job_name in worker_jobs:
        assert "readback-probe" not in jobs[job_name]["if"] or "!= 'readback-probe'" in jobs[job_name]["if"]


def test_readback_probe_and_normal_calibration_conditions_are_disjoint():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    jobs = workflow["jobs"]

    for number in range(1, 8):
        condition = jobs[f"calibration-stage-3-batch-{number}"]["if"]
        assert "mode == 'calibration'" in condition
        assert "calibration_stage == '3'" in condition
        assert "readback-probe" not in condition
    for number in range(2, 8):
        condition = jobs[f"calibration-stage-3-admit-{number}"]["if"]
        assert "mode == 'calibration'" in condition
        assert "readback-probe" not in condition
    assert jobs["calibration-monitor"]["if"] == (
        "github.event_name == 'workflow_dispatch' && "
        "github.event.inputs.mode == 'calibration'"
    )
    assert "readback-probe" not in jobs["calibration-accounting"]["if"]
    assert "!= 'readback-probe'" in jobs["aggregate"]["if"]
    assert "!= 'readback-probe'" in jobs["evidence-readback"]["if"]


@pytest.mark.parametrize(
    ("scenario", "admission_conclusion", "contained"),
    [("success", "success", False), ("failed-initial-admission", "failure", True)],
)
def test_actual_readback_probe_finalizer_is_non_authoritative_and_zero_worker(
    tmp_path, scenario, admission_conclusion, contained,
):
    observe_script = _workflow_step_script(
        "readback-probe-finalizer", "Validate probe identity and zero-worker finalization",
    )
    producer_script = _workflow_step_script(
        "calibration-stage-3-observer-readiness", "Establish observer readiness",
    )
    consumer_script = _workflow_step_script(
        "calibration-stage-3-observer-ready", "Validate exact observer readiness",
    )
    candidate = "a" * 40
    probe_id = f"probe-{scenario}"
    run_id = 700
    jobs = [
        {
            "id": 91, "name": "mutation (readback probe zero-worker finalizer)",
            "status": "in_progress", "conclusion": None,
        },
        {
            "id": 92, "name": "mutation (publish stage 3 observer readiness)",
            "status": "completed", "conclusion": "success",
        },
        {
            "id": 93, "name": "mutation (require stage 3 observer readiness)",
            "status": "completed", "conclusion": admission_conclusion,
        },
        {
            "id": 94, "name": "calibration-stage-3-batch-1",
            "status": "completed", "conclusion": "skipped",
        },
        {
            "id": 95, "name": "mutation (full shard 0, advisory)",
            "status": "completed", "conclusion": "skipped",
        },
    ]
    runs = [{
        "id": run_id, "display_title": f"Mutation readback probe {probe_id}",
        "event": "workflow_dispatch",
    }]
    provider = tmp_path / "provider"
    provider.mkdir()
    (provider / "jobs.json").write_text(json.dumps([{
        "total_count": len(jobs), "jobs": jobs,
    }]))
    (provider / "runs.json").write_text(json.dumps([{
        "total_count": len(runs), "workflow_runs": runs,
    }]))
    gh = provider / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f"case \"$*\" in *'/actions/workflows/mutation.yml/runs?'*) cat '{provider / 'runs.json'}';; "
        f"*'/attempts/1/jobs?'*) cat '{provider / 'jobs.json'}';; *) exit 2;; esac\n"
    )
    gh.chmod(0o755)

    probe_env = {
        **os.environ, "PATH": f"{provider}:{os.environ['PATH']}", "PYTHONPATH": PLUGIN_DIR,
        "GITHUB_REPOSITORY": "example/fettle", "GITHUB_RUN_ID": str(run_id),
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": candidate,
        "GITHUB_WORKFLOW_SHA": candidate, "CANDIDATE_SHA": candidate,
        "PROBE_ID": probe_id, "PROBE_SCENARIO": scenario, "GH_TOKEN": "test",
        "PROBE_MODE": "true", "CALIBRATION_ID": probe_id,
        "OBSERVER_JOB_NAME": "mutation (readback probe zero-worker finalizer)",
        "ARTIFACT_NAME": f"mutation-readback-probe-ready-{run_id}-1",
    }

    produced = _run_actions_bash(producer_script, cwd=tmp_path, env=probe_env)
    assert produced.returncode == 0, produced.stderr
    observer_ready = tmp_path / "observer-ready-1"
    observer_ready.mkdir()
    shutil.copy(tmp_path / "observer-readiness.json", observer_ready)
    shutil.copy(tmp_path / "observer-ready-jobs.json", observer_ready)
    admitted = _run_actions_bash(consumer_script, cwd=tmp_path, env={
        **probe_env, "DOWNLOAD_OUTCOME_1": "success",
        "DOWNLOAD_OUTCOME_2": "skipped", "DOWNLOAD_OUTCOME_3": "skipped",
    })
    assert (admitted.returncode != 0) is contained, admitted.stderr
    actual_admission = json.loads((tmp_path / "initial-admission.json").read_text())
    assert actual_admission["monitor_job_id"] == 91
    assert actual_admission["provider_validation_passed"] is True
    assert actual_admission["passed"] is False
    if contained:
        assert actual_admission["failure_code"] == "forced_calibration_identity_mismatch"

    result = _run_actions_bash(observe_script, cwd=tmp_path, env=probe_env)

    assert result.returncode == 0, result.stderr
    retained = tmp_path / "retained-probe-admission"
    retained.mkdir()
    shutil.copy(tmp_path / "initial-admission.json", retained)
    finalized = _run_actions_bash(
        _workflow_step_script(
            "readback-probe-finalizer", "Validate retained probe admission and finalize",
        ),
        cwd=tmp_path, env={
            **os.environ, "PYTHONPATH": PLUGIN_DIR,
            "GITHUB_REPOSITORY": "example/fettle", "GITHUB_RUN_ID": str(run_id),
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": candidate,
            "GITHUB_WORKFLOW_SHA": candidate, "CANDIDATE_SHA": candidate,
            "PROBE_ID": probe_id, "PROBE_SCENARIO": scenario,
        },
    )
    assert finalized.returncode == 0, finalized.stderr
    record = json.loads((tmp_path / "readback-probe-result.json").read_text())
    assert record["probe_only"] is True
    assert record["billing_authority"] is False
    assert record["passed"] is False
    assert record["authoritative_predecessor"] is False
    assert record["qualification_eligible"] is False
    assert record["mutation_workers_started"] == 0
    assert record["containment_demonstrated"] is contained
    assert record["provider_path_verified"] is True


def test_actual_readback_probe_finalizer_rejects_invalid_mode_values(tmp_path):
    script = _workflow_step_script(
        "readback-probe-finalizer", "Validate probe identity and zero-worker finalization",
    )
    candidate = "a" * 40
    base = {
        **os.environ, "PYTHONPATH": PLUGIN_DIR, "GITHUB_SHA": candidate,
        "GITHUB_WORKFLOW_SHA": candidate, "CANDIDATE_SHA": candidate,
        "PROBE_ID": "probe-invalid", "PROBE_SCENARIO": "", "GH_TOKEN": "test",
    }

    missing = _run_actions_bash(script, cwd=tmp_path, env=base)
    unknown = _run_actions_bash(
        script, cwd=tmp_path, env={**base, "PROBE_SCENARIO": "calibration"},
    )

    assert missing.returncode != 0
    assert unknown.returncode != 0
    assert "probe_scenario is malformed" in missing.stderr
    assert "probe_scenario is malformed" in unknown.stderr
    assert not (tmp_path / "readback-probe-result.json").exists()


def test_probe_producer_and_consumer_validate_inputs_before_artifacts():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    for job_name in (
        "calibration-stage-3-observer-readiness", "calibration-stage-3-observer-ready",
    ):
        steps = workflow["jobs"][job_name]["steps"]
        validation_index = next(
            index for index, step in enumerate(steps)
            if step.get("name") == "Validate exact readback probe dispatch"
        )
        artifact_index = next(
            index for index, step in enumerate(steps)
            if "observer readiness" in step.get("name", "").lower()
            and step.get("name") != "Validate exact readback probe dispatch"
        )
        validation = steps[validation_index]
        assert validation_index < artifact_index
        assert validation["if"] == "github.event.inputs.mode == 'readback-probe'"
        assert "probe_id is malformed" in validation["run"]
        assert "probe_scenario is malformed" in validation["run"]
        assert "dispatch SHA differs from candidate_sha" in validation["run"]


def test_readiness_producers_classify_provider_errors_without_raw_stderr_retention():
    production = _workflow_step_script(
        "calibration-stage-3-observer-readiness", "Establish observer readiness",
    )
    assert "2> provider-error.tmp" in production
    assert "provider_error_class=access_denied" in production
    assert "provider_error_class=transient_provider_error" in production
    assert "provider_error_class=provider_resource_unavailable" in production
    assert "rm -f provider-error.tmp" in production


def test_calibration_publication_is_atomic_and_consolidation_is_inventory_bound():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    reusable = (Path(PLUGIN_DIR) / ".github/workflows/mutation-calibration-shard.yml").read_text()

    for source in (workflow, reusable):
        assert "> mutation-report.json.tmp" in source
        assert "mv mutation-report.json.tmp mutation-report.json" in source
    assert "load_mutation_report_candidates" in workflow
    assert "build_calibration_representation_inventory" in workflow
    assert "read_calibration_representation_inventory" in workflow
    assert "--aggregate validated-calibration-reports" in workflow
    assert "representation-inventory.json" in workflow
    assert "validate_calibration_accounting(predecessor)" in (
        Path(PLUGIN_DIR) / "fettle/staged_preflight.py"
    ).read_text()


def test_calibration_workflow_requires_fixed_12000_minute_ceiling():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert 'os.environ["RUNNER_MINUTE_CEILING"]=="12000"' in workflow
    assert "int(value)<=12000" not in workflow


def test_stage_3_calibration_uses_seven_output_gated_fixed_batches():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    jobs = workflow["jobs"]

    batch_names = [f"calibration-stage-3-batch-{number}" for number in range(1, 8)]
    admission_names = [f"calibration-stage-3-admit-{number}" for number in range(2, 8)]
    assert all(name in jobs for name in batch_names + admission_names)
    assert jobs[batch_names[0]]["needs"] == ["prepare", "calibration-stage-3-observer-ready"]
    for number in range(2, 8):
        batch = jobs[f"calibration-stage-3-batch-{number}"]
        admission = jobs[f"calibration-stage-3-admit-{number}"]
        assert admission["if"] == (
            "always() && github.event.inputs.mode == 'calibration' && "
            "github.event.inputs.calibration_stage == '3' && "
            f"needs.calibration-stage-3-batch-{number - 1}.result != 'skipped'"
        )
        assert admission["needs"] == ["prepare", f"calibration-stage-3-batch-{number - 1}"]
        assert batch["needs"] == [
            "prepare", f"calibration-stage-3-admit-{number}",
            f"calibration-stage-3-observer-live-{number}",
        ]
        assert batch["strategy"]["max-parallel"] == 32
    assert "calibration_stage == '3'" in jobs["full-shard"]["if"]
    assert jobs["calibration-stage-3-batch-7"] in [jobs[name] for name in batch_names]


def test_calibration_reusable_workflows_preserve_worker_and_containment_contracts():
    shard = (Path(PLUGIN_DIR) / ".github/workflows/mutation-calibration-shard.yml").read_text()
    admission = (Path(PLUGIN_DIR) / ".github/workflows/mutation-calibration-admission.yml").read_text()

    assert 'python-version: "3.12.13"' in shard
    assert "--timeout 1740 --json" in shard
    assert "retention-days: 90" in shard
    assert 'if [[ -n "${{ inputs.resume_run_id }}" ]]' in shard
    assert '--resume-checkpoints "calibration-resume/resume-checkpoints/' in shard
    assert "select_shard_subset_attempts" in admission
    assert "if report.get(\"shard_index\") in completed_prefix" in admission
    assert "retain_historical_accounting_floor" in admission
    assert "--paginate --slurp" in admission
    assert "completed_prefix = [index for batch in fixed[:completed_batches] for index in batch]" in admission
    assert "a later batch report exists before admission" in admission
    assert "select_shard_subset_attempts(reports, 256, completed_prefix)" in admission
    assert "steps.validate.outcome != 'success' || steps.retain.outcome != 'success'" in admission
    assert "/actions/runs/$GITHUB_RUN_ID/cancel" not in admission


def test_staged_preflight_publishes_consumer_aliases_with_provenance():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()

    assert "preflight-publication.json" in workflow
    assert "mutation-manifests-${{ github.run_id }}" in workflow
    assert "mutation-preflight-${{ github.run_id }}" in workflow
    assert '"candidate_sha": "${{ github.event.inputs.candidate_sha }}"' in workflow
    assert '"source_run_id": "${{ github.event.inputs.source_run_id }}"' in workflow
    assert "Download published consumer aliases" in workflow
    assert 'published_aggregate.read_bytes() == Path("retained/mutation-preflight.json").read_bytes()' in workflow
    assert 'preflight_completion.read_bytes() == Path("retained/staged-preflight-continuation.json").read_bytes()' in workflow
    assert 'publication["manifest_count"] == len(manifests) == 256' in workflow

    consumer = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    assert "assert preflight_attestation.is_file() and manifest_attestation.is_file()" in consumer
    assert 'publication.get("manifest_count") == len(manifests) == 256' in consumer
    assert 'publication.get("manifest_topology_sha256") == topology' in consumer
    assert 'publication.get("publication_run_attempt") == "1"' in consumer
    assert 'completion.get("source", {}).get("run_id") == publication["source_run_id"]' in consumer


def test_staged_publication_readback_and_calibration_consumer_delivery_path(tmp_path):
    continuation = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )
    mutation = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    candidate = "a" * 40
    source_run = "37"
    publication_run = "38"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifests = workspace / "staged-plan/mutation-manifests"
    manifests.mkdir(parents=True)
    for index in range(256):
        (manifests / f"partition-{index}.json").write_text(
            json.dumps({"shard_index": index}) + "\n"
        )
    (workspace / "mutation-preflight.json").write_text(json.dumps({
        "status": "completed", "passed": True, "revision": candidate,
        "shard_count": 256, "generated": 256, "canonicalized": 256,
        "collisions": 0,
    }) + "\n")
    (workspace / "staged-preflight-continuation.json").write_text(json.dumps({
        "status": "completed", "passed": True, "kind": "fresh_staged_preflight",
        "candidate_sha": candidate, "source": {"run_id": source_run},
        "origins": {str(index): {"run_id": publication_run} for index in range(256)},
    }) + "\n")

    aggregate_steps = continuation["jobs"]["aggregate"]["steps"]
    publish = next(
        step["run"] for step in aggregate_steps
        if step.get("name") == "Build provenance-bound consumer publication"
    )
    publish = (
        publish.replace("${{ github.event.inputs.candidate_sha }}", candidate)
        .replace("${{ github.event.inputs.source_run_id }}", source_run)
        .replace("${{ github.run_id }}", publication_run)
        .replace("${{ github.run_attempt }}", "1")
    )
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python"
    python.symlink_to(sys.executable)
    subprocess.run(
        ["/bin/bash", "-e", "-c", publish], cwd=workspace,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}, check=True,
    )

    retained = workspace / "retained"
    retained.mkdir()
    for name in ("mutation-preflight.json", "staged-preflight-continuation.json"):
        shutil.copy2(workspace / name, retained / name)
    published = workspace / "published"
    manifest_alias = published / f"mutation-manifests-{publication_run}"
    preflight_alias = published / f"mutation-preflight-{publication_run}"
    shutil.copytree(workspace / "published-manifests", manifest_alias)
    preflight_alias.mkdir(parents=True)
    for name in (
        "mutation-preflight.json", "preflight-publication.json",
        "staged-preflight-continuation.json",
    ):
        shutil.copy2(workspace / name, preflight_alias / name)

    readback_steps = continuation["jobs"]["readback"]["steps"]
    readback = next(
        step["run"] for step in readback_steps
        if step.get("name") == "Verify downloaded aggregate and origin record"
    )
    readback = (
        readback.replace("${{ github.event.inputs.candidate_sha }}", candidate)
        .replace("${{ github.event.inputs.source_run_id }}", source_run)
        .replace("${{ github.run_id }}", publication_run)
    )
    subprocess.run([sys.executable, "-c", _python_heredoc(readback)], cwd=workspace, check=True)
    assert json.loads((workspace / "readback-checksums.json").read_text())

    altered_completion = b"{}\n"
    for alias in (manifest_alias, preflight_alias):
        (alias / "staged-preflight-continuation.json").write_bytes(altered_completion)
        attestation = alias / "preflight-publication.json"
        payload = json.loads(attestation.read_text())
        payload["completion_sha256"] = hashlib.sha256(altered_completion).hexdigest()
        attestation.write_text(json.dumps(payload, indent=2) + "\n")
    rejected = subprocess.run(
        [sys.executable, "-c", _python_heredoc(readback)], cwd=workspace,
        capture_output=True, text=True,
    )
    assert rejected.returncode != 0
    for alias in (manifest_alias, preflight_alias):
        shutil.copy2(workspace / "staged-preflight-continuation.json", alias)
        shutil.copy2(workspace / "preflight-publication.json", alias)

    shutil.copytree(manifest_alias, workspace / "mutation-manifests")
    shutil.copytree(preflight_alias, workspace / "retained-preflight")
    prepare_steps = mutation["jobs"]["prepare"]["steps"]
    consume = next(
        step["run"] for step in prepare_steps
        if step.get("name") == "Verify retained SHA-bound preflight"
    )
    subprocess.run(
        [sys.executable, "-c", _python_heredoc(consume)], cwd=workspace,
        env={**os.environ, "GITHUB_SHA": candidate, "PREFLIGHT_RUN_ID": publication_run},
        check=True,
    )


def test_explicit_calibration_uses_required_pr_check_name_and_enforces_result():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    aggregate_job = workflow.split("\n  aggregate:", 1)[1]

    assert "name: mutation evidence" in aggregate_job
    assert "report.get('passed') is True" in aggregate_job
    assert "mutation (full aggregate, advisory)" not in aggregate_job
    assert "github.event.inputs.mode != 'calibration'" in aggregate_job
    assert '"qualification_executed":False' in aggregate_job


def test_mutation_replay_uses_retained_canonical_corpus():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "fettle mutation run --all" not in workflow
    assert "--resume-manifest mutation-manifests/partition-${{ matrix.shard }}.json" in workflow
    assert "--retained-preflight retained-preflight/mutation-preflight.json" in workflow
    # resume_run_id is free-text dispatch input: it must be validated and must
    # reach the shell only via env indirection, never direct interpolation.
    assert '--calibration-id "replay-${RESUME_RUN_ID:-${{ github.run_id }}}"' in workflow
    assert 'RESUME_RUN_ID: ${{ github.event.inputs.resume_run_id }}' in workflow
    assert 'test "$RESUME_RUN_ID" -eq "$RESUME_RUN_ID"' in workflow
    assert '"replay-${{ github.event.inputs.resume_run_id' not in workflow
    assert "github.event.inputs.mode == 'replay' && format('replay-{0}', github.event.inputs.resume_run_id)" in workflow
    assert "${{ github.event.inputs.resume_run_id != '' && '--resume-checkpoints resume-checkpoints' || '' }}" in workflow
    assert "if: always()\n        uses: actions/upload-artifact@" in workflow


def test_partition_manifest_rejects_tampering(tmp_path, monkeypatch):
    from fettle.mutation_test import load_partition_manifest, write_partition_manifests

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/a.py").write_text("x = 1\n")
    (tmp_path / "tests/test_a.py").write_text("import src.a\n")
    monkeypatch.setattr("fettle.mutation_test._revision", lambda root: "a" * 40)
    paths = write_partition_manifests(
        str(tmp_path), {"paths": ["src/"], "full_shards": 1, "default_chunk_lines": 60},
        tmp_path / "manifests",
    )
    manifest = load_partition_manifest(paths[0])
    assert manifest["ranges"] == [{"file": "src/a.py", "start": 1, "end": 1}]

    value = json.loads(paths[0].read_text())
    value["ranges"][0]["end"] = 2
    paths[0].write_text(json.dumps(value))
    try:
        load_partition_manifest(paths[0])
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("tampered manifest was accepted")


def test_partition_manifest_must_match_configured_shard_count(tmp_path, monkeypatch):
    from fettle.mutation_test import run_mutation_test, write_partition_manifests

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/a.py").write_text("x = 1\n")
    (tmp_path / "tests/test_a.py").write_text("import src.a\n")
    monkeypatch.setattr("fettle.mutation_test._revision", lambda root: "a" * 40)
    manifest = write_partition_manifests(
        str(tmp_path), {"paths": ["src/"], "full_shards": 1}, tmp_path / "manifests",
    )[0]

    result = run_mutation_test(str(tmp_path), {
        "paths": ["src/"], "all": True, "full_shards": 2, "manifest": str(manifest),
    })

    assert result["status"] == "unknown"
    assert "shard count" in result["message"]


def test_partition_manifest_files_must_match_ranges(tmp_path):
    from fettle.mutation_test import load_partition_manifest

    payload = {
        "schema_version": "1", "revision": "a" * 40, "shard_index": 0,
        "shard_count": 1, "files": ["src/a.py"],
        "ranges": [{"file": "src/b.py", "start": 1, "end": 1}],
    }
    from fettle.mutation_test import _canonical_digest
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({**payload, "digest": _canonical_digest(payload)}))

    try:
        load_partition_manifest(path)
    except ValueError as exc:
        assert "files" in str(exc)
    else:
        raise AssertionError("inconsistent manifest was accepted")
