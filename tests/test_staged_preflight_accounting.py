"""Workflow accounting-envelope contracts owned by staged preflight."""

import json
import os
import subprocess
from pathlib import Path


PLUGIN_DIR = str(Path(__file__).resolve().parents[1])


def _run_actions_bash(script, *, cwd, env):
    env = {key: value for key, value in env.items() if value is not None}
    return subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


def _workflow_step_script(job_name, step_name):
    import yaml
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    return next(step for step in workflow["jobs"][job_name]["steps"] if step.get("name") == step_name)["run"]


def _retention_probe_step_script(job_name, step_name):
    import yaml
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/calibration-retention-probe.yml").read_text())
    return next(step for step in workflow["jobs"][job_name]["steps"] if step.get("name") == step_name)["run"]

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
