import hashlib
import json
from pathlib import Path

import pytest

from scripts import e2_preflight_recovery as recovery


def _write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def _fixture(monkeypatch, tmp_path):
    plan = {
        "candidate_sha": recovery.CANDIDATE_SHA,
        "manifest_topology_digest": "d" * 64,
    }
    plan_path = _write(tmp_path / "plan.json", plan)
    monkeypatch.setattr(recovery, "SOURCE_PLAN_SHA256", hashlib.sha256(plan_path.read_bytes()).hexdigest())
    manifests = tmp_path / "manifests"
    for index in range(256):
        _write(manifests / f"partition-{index}.json", {"shard_index": index})
    reports = {}
    report_hashes = {}
    for wave in ("wave-1", "wave-2"):
        directory = tmp_path / wave
        reports[wave] = directory
        for index in recovery.WAVES[wave]:
            path = _write(directory / str(index) / "mutation-preflight.json", {"shard_index": index})
            report_hashes[index] = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(recovery, "REPORT_SHA256", report_hashes)
    validations = {
        wave: {"status": "completed", "passed": True, "wave": wave}
        for wave in ("wave-1", "wave-2")
    }
    validation_paths = {
        wave: _write(tmp_path / f"{wave}-validation.json", value)
        for wave, value in validations.items()
    }
    monkeypatch.setattr(
        recovery, "WAVE_VALIDATION_SHA256",
        {wave: hashlib.sha256(path.read_bytes()).hexdigest()
         for wave, path in validation_paths.items()},
    )
    def validate_fixture(_root, _plan, fixture_manifests, _reports, wave, _sha, _identity):
        if json.loads((fixture_manifests / "partition-0.json").read_text()) != {"shard_index": 0}:
            raise ValueError("wave manifest digests differ from the frozen topology")
        return validations[wave]

    monkeypatch.setattr(recovery, "validate_wave", validate_fixture)
    jobs = [
        {"id": 1, "run_id": int(recovery.SOURCE_RUN_ID), "run_attempt": 1,
         "name": "mutation (staged preflight wave 1 shard 8)", "conclusion": "success",
         "steps": [{"name": "work", "conclusion": "success"}]},
        {"id": recovery.SOURCE_FAILURE_JOB_ID, "run_id": int(recovery.SOURCE_RUN_ID),
         "run_attempt": 1, "name": "mutation (dispatch staged preflight continuation)",
         "conclusion": "failure",
         "steps": [{"name": "Dispatch immutable continuation", "conclusion": "failure"}]},
    ]
    run = {"id": int(recovery.SOURCE_RUN_ID), "run_attempt": 1,
           "head_sha": recovery.CANDIDATE_SHA, "path": ".github/workflows/mutation.yml",
           "event": "workflow_dispatch",
           "head_branch": "audit/hardening-integration-20261005",
           "status": "completed", "conclusion": "failure"}
    setup_run = {
        "id": int(recovery.SETUP_RUN_ID), "run_attempt": 1,
        "head_sha": "91c72a71fae004c8a23b846cb887d48d467f2e61",
        "head_branch": recovery.RECOVERY_BRANCH, "event": "workflow_dispatch",
        "status": "completed", "conclusion": "failure",
    }
    setup_jobs = [
        {
            "id": job_id, "run_id": int(recovery.SETUP_RUN_ID), "run_attempt": 1,
            "name": name, "conclusion": conclusion,
            "steps": [{
                "name": "Bind candidate and recovery orchestration identities",
                "conclusion": "failure",
            }] if job_id == recovery.SETUP_FAILURE_JOB_ID else [],
        }
        for job_id, (name, conclusion) in recovery.SETUP_JOB_INVENTORY.items()
    ]
    layout_jobs = []
    layout_logs = tmp_path / "layout-logs"
    layout_logs.mkdir()
    for job_id, shard in recovery.LAYOUT_FAILURE_SHARD_JOBS.items():
        layout_jobs.append({
            "id": job_id, "run_id": int(recovery.LAYOUT_FAILURE_RUN_ID),
            "run_attempt": 1, "name": f"mutation (continuation shard {shard})",
            "runner_id": job_id, "conclusion": "failure",
            "steps": [{"name": "Execute previously unattempted shard", "conclusion": "failure"}],
        })
        (layout_logs / f"shard-{job_id}.log").write_text(
            "cannot parse mutation partition manifest "
            f"staged-plan/mutation-manifests/partition-{shard}.json\n"
        )
    for index in sorted(set(recovery.WAVES["wave-3"]) - set(recovery.LAYOUT_FAILURE_SHARD_JOBS.values())):
        layout_jobs.append({
            "id": 200000 + index, "run_id": int(recovery.LAYOUT_FAILURE_RUN_ID),
            "run_attempt": 1, "name": f"mutation (continuation shard {index})",
            "runner_id": 0, "conclusion": "cancelled", "steps": [],
        })
    layout_jobs.extend({
        "id": 300000 + index, "run_id": int(recovery.LAYOUT_FAILURE_RUN_ID),
        "run_attempt": 1, "name": f"support {index}", "runner_id": index + 1,
        "conclusion": "success", "steps": [],
    } for index in range(7))
    layout_artifacts = [
        {
            "name": f"mutation-preflight-wave-3-{recovery.LAYOUT_FAILURE_RUN_ID}-1-{shard}",
            "size_in_bytes": 162, "digest": digest, "expired": False,
        }
        for shard, digest in recovery.LAYOUT_FAILURE_ARTIFACT_DIGESTS.items()
    ]
    artifacts = []
    for wave in ("wave-1", "wave-2"):
        for index in recovery.WAVES[wave]:
            artifacts.append({
                "id": 1000 + index, "name": f"mutation-preflight-{wave}-{recovery.SOURCE_RUN_ID}-1-{index}",
                "size_in_bytes": 1, "digest": f"sha256:{index:064x}", "expired": False,
            })
    monkeypatch.setattr(
        recovery, "REPORT_ARTIFACT_INVENTORY_SHA256",
        {
            wave: hashlib.sha256(json.dumps(sorted(
                ({key: item[key] for key in ("id", "name", "size_in_bytes", "digest", "expired")}
                 for item in artifacts if f"mutation-preflight-{wave}-" in item["name"]),
                key=lambda item: item["name"]), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            for wave in ("wave-1", "wave-2")
        },
    )
    paths = {
        "root": tmp_path,
        "source_run_path": _write(tmp_path / "run.json", run),
        "source_jobs_path": _write(tmp_path / "jobs.json", [{"total_count": len(jobs), "jobs": jobs}]),
        "source_failure_log_path": tmp_path / "failure.log",
        "source_artifacts_path": _write(
            tmp_path / "artifacts.json",
            [{"total_count": len(artifacts), "artifacts": artifacts}],
        ),
        "setup_run_path": _write(tmp_path / "setup-run.json", setup_run),
        "setup_jobs_path": _write(
            tmp_path / "setup-jobs.json",
            [{"total_count": len(setup_jobs), "jobs": setup_jobs}],
        ),
        "setup_artifacts_path": _write(
            tmp_path / "setup-artifacts.json", [{"total_count": 0, "artifacts": []}],
        ),
        "layout_run_path": _write(tmp_path / "layout-run.json", {
            "id": int(recovery.LAYOUT_FAILURE_RUN_ID), "run_attempt": 1,
            "head_sha": recovery.LAYOUT_FAILURE_ORCHESTRATION_SHA,
            "head_branch": recovery.RECOVERY_BRANCH, "event": "workflow_dispatch",
            "status": "completed", "conclusion": "failure",
        }),
        "layout_jobs_path": _write(
            tmp_path / "layout-jobs.json",
            [{"total_count": len(layout_jobs), "jobs": layout_jobs}],
        ),
        "layout_artifacts_path": _write(
            tmp_path / "layout-artifacts.json",
            [{"total_count": len(layout_artifacts), "artifacts": layout_artifacts}],
        ),
        "layout_logs_dir": layout_logs,
        "prior_runs_path": _write(tmp_path / "prior-runs.json", []),
        "plan_path": plan_path, "manifests_dir": manifests,
        "wave_1_reports": reports["wave-1"], "wave_2_reports": reports["wave-2"],
        "wave_1_validation": validation_paths["wave-1"],
        "wave_2_validation": validation_paths["wave-2"],
        "orchestration_sha": "a" * 40, "current_run_id": "99",
    }
    paths["source_failure_log_path"].write_text(
        "failed to run git: fatal: not a git repository (or any of the parent directories): .git\n",
    )
    return paths


def test_authorized_handoff_recovery_accepts_only_pinned_complete_source(monkeypatch, tmp_path):
    result = recovery.validate_source_exception(**_fixture(monkeypatch, tmp_path))

    assert result["passed"] is True
    assert result["source_run"]["verdict"] == "permanently failed; dispatch handoff only"
    assert result["retained_reports"] == 40
    assert result["recovery_run_id"] == "99"
    assert len(result["execution_wave"]["shards"]) == 216


@pytest.mark.parametrize(
    "fault",
    ["wrong-attempt", "candidate", "missing-report", "altered-report", "duplicate",
     "manifest", "prior-wave-3", "wave-3-artifact", "other-failure", "failure-log",
     "setup-run", "setup-origin", "setup-step", "setup-execution", "setup-artifact",
     "setup-missing", "setup-extra", "malformed-setup", "malformed-prior-run",
     "layout-started", "layout-log", "layout-artifact"],
)
def test_authorized_handoff_recovery_rejects_incompatible_evidence(monkeypatch, tmp_path, fault):
    paths = _fixture(monkeypatch, tmp_path)
    if fault in {"wrong-attempt", "candidate"}:
        run = json.loads(paths["source_run_path"].read_text())
        run["run_attempt" if fault == "wrong-attempt" else "head_sha"] = 2 if fault == "wrong-attempt" else "f" * 40
        paths["source_run_path"].write_text(json.dumps(run))
    elif fault in {"missing-report", "altered-report"}:
        report = next(paths["wave_1_reports"].rglob("mutation-preflight.json"))
        report.unlink() if fault == "missing-report" else report.write_text('{"shard_index": 8, "changed": true}')
    elif fault == "duplicate":
        source = next(paths["wave_1_reports"].rglob("mutation-preflight.json"))
        duplicate = paths["wave_1_reports"] / "duplicate" / "mutation-preflight.json"
        duplicate.parent.mkdir()
        duplicate.write_bytes(source.read_bytes())
    elif fault == "manifest":
        manifest = paths["manifests_dir"] / "partition-0.json"
        manifest.write_text('{"shard_index": 0, "changed": true}')
    elif fault == "prior-wave-3":
        paths["prior_runs_path"].write_text(json.dumps([{
            "databaseId": 100, "headBranch": recovery.RECOVERY_BRANCH,
            "headSha": "b" * 40, "event": "workflow_dispatch",
        }]))
    elif fault == "wave-3-artifact":
        pages = json.loads(paths["source_artifacts_path"].read_text())
        pages[0]["artifacts"].append({"name": "mutation-preflight-wave-3-1-1-35"})
        paths["source_artifacts_path"].write_text(json.dumps(pages))
    elif fault == "other-failure":
        pages = json.loads(paths["source_jobs_path"].read_text())
        pages[0]["jobs"].append({"id": 3, "run_id": int(recovery.SOURCE_RUN_ID),
                                  "run_attempt": 1, "name": "other", "conclusion": "failure"})
        pages[0]["total_count"] += 1
        paths["source_jobs_path"].write_text(json.dumps(pages))
    elif fault == "setup-run":
        setup = json.loads(paths["setup_run_path"].read_text())
        setup["head_sha"] = "f" * 40
        paths["setup_run_path"].write_text(json.dumps(setup))
    elif fault == "setup-origin":
        pages = json.loads(paths["setup_jobs_path"].read_text())
        pages[0]["jobs"][0]["run_id"] = 1
        paths["setup_jobs_path"].write_text(json.dumps(pages))
    elif fault == "setup-step":
        pages = json.loads(paths["setup_jobs_path"].read_text())
        pages[0]["jobs"][0]["steps"][0]["name"] = "different failure"
        paths["setup_jobs_path"].write_text(json.dumps(pages))
    elif fault == "setup-execution":
        pages = json.loads(paths["setup_jobs_path"].read_text())
        shard = next(
            job for job in pages[0]["jobs"]
            if job["name"].startswith("mutation (continuation shard ")
        )
        shard["conclusion"] = "success"
        paths["setup_jobs_path"].write_text(json.dumps(pages))
    elif fault == "setup-artifact":
        paths["setup_artifacts_path"].write_text(json.dumps([{
            "total_count": 1, "artifacts": [{"name": "unexpected"}],
        }]))
    elif fault == "malformed-setup":
        paths["setup_jobs_path"].write_text("{}")
    elif fault == "setup-missing":
        pages = json.loads(paths["setup_jobs_path"].read_text())
        pages[0]["jobs"].pop()
        pages[0]["total_count"] -= 1
        paths["setup_jobs_path"].write_text(json.dumps(pages))
    elif fault == "setup-extra":
        pages = json.loads(paths["setup_jobs_path"].read_text())
        pages[0]["jobs"].append({
            "id": 3, "run_id": int(recovery.SETUP_RUN_ID), "run_attempt": 1,
            "name": "unexpected", "conclusion": "success", "steps": [],
        })
        pages[0]["total_count"] += 1
        paths["setup_jobs_path"].write_text(json.dumps(pages))
    elif fault == "malformed-prior-run":
        paths["prior_runs_path"].write_text("[null]")
    elif fault == "layout-started":
        pages = json.loads(paths["layout_jobs_path"].read_text())
        cancelled = next(job for job in pages[0]["jobs"] if job.get("runner_id") == 0)
        cancelled["runner_id"] = 1
        paths["layout_jobs_path"].write_text(json.dumps(pages))
    elif fault == "layout-log":
        job_id = next(iter(recovery.LAYOUT_FAILURE_SHARD_JOBS))
        (paths["layout_logs_dir"] / f"shard-{job_id}.log").write_text("mutmut run\n")
    elif fault == "layout-artifact":
        pages = json.loads(paths["layout_artifacts_path"].read_text())
        pages[0]["artifacts"][0]["digest"] = "sha256:" + "0" * 64
        paths["layout_artifacts_path"].write_text(json.dumps(pages))
    else:
        paths["source_failure_log_path"].write_text("different error\n")

    with pytest.raises(ValueError):
        recovery.validate_source_exception(**paths)
