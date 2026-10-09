import json
import hashlib
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fettle.mutation_test import aggregate_preflight_shards
from scripts.staged_preflight import (
    ARTIFACT_RETENTION_DAYS,
    BUDGET,
    FROZEN_CANDIDATE,
    RECOVERY_ORCHESTRATION_SHA,
    RECOVERY_RUN_ID,
    SOURCE_ORCHESTRATION_SHA,
    SOURCE_REPORT_SHA256,
    SOURCE_RUN_ID,
    SOURCE_WORKFLOW_REF,
    WAVES,
    WAVE_3_BATCHES,
    calibration_stage_3_batches,
    account_runner_minutes,
    combine_accounting,
    build_plan,
    build_continuation_plan,
    build_fresh_continuation_plan,
    build_fresh_completion_record,
    build_recovery_plan,
    build_recovery_record,
    combine_accounting_sources,
    observed_runner_minutes,
    plan_calibration_continuation,
    evaluate_calibration_budget,
    retain_historical_accounting_floor,
    validate_wave,
    validate_continuation_topology,
    validate_continuation_artifacts,
    validate_continuation_dispatches,
    validate_continuation_batch,
    validate_source_handoff,
)


def test_fixed_waves_cover_every_shard_once_and_reconcile_budget():
    members = [index for shards in WAVES.values() for index in shards]

    assert [len(WAVES[name]) for name in ("wave-1", "wave-2", "wave-3")] == [8, 32, 216]
    assert 27 in WAVES["wave-1"]
    assert len(members) == len(set(members)) == 256
    assert sorted(members) == list(range(256))
    assert BUDGET == {
        "operational_ceiling_runner_minutes": 1220,
        "wave_allowances": {"wave-1": 32, "wave-2": 120, "wave-3": 800},
        "orchestration_and_aggregation": 168,
        "cancellation_headroom": 100,
        "launch_ceiling": {
            "wave-2": 32,
            "wave-3": 152,
            "aggregate": 952,
            "complete": 1120,
        },
    }
    assert sum(BUDGET["wave_allowances"].values()) + BUDGET["orchestration_and_aggregation"] + BUDGET["cancellation_headroom"] == 1220
    assert BUDGET["launch_ceiling"] == {
        "wave-2": 32,
        "wave-3": 152,
        "aggregate": 952,
        "complete": 1120,
    }
    assert ARTIFACT_RETENTION_DAYS == 90
    assert validate_continuation_topology() == {
        "matrix_jobs": 216,
        "matrix_batches": WAVE_3_BATCHES,
        "matrix_batch_sizes": [32, 32, 32, 32, 32, 32, 24],
        "support_jobs": 13,
        "expanded_jobs": 229,
        "per_matrix_platform_limit": 256,
        "project_expanded_job_limit": 256,
    }
    assert [index for batch in WAVE_3_BATCHES for index in batch] == WAVES["wave-3"]


def _fixture(monkeypatch, tmp_path):
    root = tmp_path / "root"
    manifests = tmp_path / "manifests"
    reports = tmp_path / "reports"
    root.mkdir()
    manifests.mkdir()
    reports.mkdir()
    (root / "requirements-mutation.txt").write_text("mutmut==2.5.1\n")
    (root / ".fettle.toml").write_text("[mutation]\n")
    items = []
    for index in range(256):
        item = {"revision": FROZEN_CANDIDATE, "shard_index": index, "shard_count": 256,
                "files": ["fettle/a.py"], "ranges": [{"file": "fettle/a.py", "start": index + 1, "end": index + 1}],
                "digest": f"{index:064x}"}
        items.append(item)
        (manifests / f"partition-{index}.json").write_text(json.dumps(item))
    monkeypatch.setattr("scripts.staged_preflight._load_manifests", lambda *_: items)
    identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": "owner/repo/.github/workflows/mutation.yml@refs/heads/test",
        "run_id": "1", "run_attempt": "1",
    }
    plan = build_plan(root, manifests, "a" * 40, identity)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    return root, manifests, reports, items, identity, plan_path


def _write_wave(reports: Path, manifests: list[dict], wave="wave-1"):
    for index in WAVES[wave]:
        path = reports / str(index)
        path.mkdir()
        fingerprint = f"{index + 1:064x}"
        (path / "mutation-preflight.json").write_text(json.dumps({
            "status": "completed", "passed": True, "engine_version": "2.5.1",
            "shard_index": index, "shard_count": 256, "manifest_digest": manifests[index]["digest"],
            "line_ranges": manifests[index]["ranges"], "files": manifests[index]["files"],
            "generated": 1, "canonicalized": 1, "collisions": 0,
            "fingerprints": [fingerprint], "corpus": [{"fingerprint": fingerprint}],
        }))


def _batch_fixture(monkeypatch, tmp_path, batch=1):
    root, manifests_dir, reports, manifests, _, _ = _fixture(monkeypatch, tmp_path)
    identity = {
        "repository": "owner/repo", "workflow": "Staged preflight continuation",
        "workflow_ref": "owner/repo/.github/workflows/staged-preflight-continuation.yml@refs/heads/test",
        "run_id": "39", "run_attempt": "1",
    }
    candidate = "c" * 40
    for manifest in manifests:
        manifest["revision"] = candidate
    plan = build_plan(root, manifests_dir, candidate, identity, candidate_sha=candidate)
    plan.update({
        "mode": "fresh-staged-preflight-continuation",
        "topology": validate_continuation_topology(),
    })
    plan_path = tmp_path / "continuation-plan.json"
    plan_path.write_text(json.dumps(plan))
    completed = [index for members in WAVE_3_BATCHES[:batch] for index in members]
    for index in completed:
        path = reports / str(index)
        path.mkdir()
        fingerprint = f"{index + 1:064x}"
        (path / "mutation-preflight.json").write_text(json.dumps({
            "status": "completed", "passed": True, "engine_version": "2.5.1",
            "shard_index": index, "shard_count": 256,
            "manifest_digest": manifests[index]["digest"],
            "line_ranges": manifests[index]["ranges"], "files": manifests[index]["files"],
            "generated": 1, "canonicalized": 1, "collisions": 0,
            "fingerprints": [fingerprint], "corpus": [{"fingerprint": fingerprint}],
        }))
    jobs = []
    for index in completed:
        jobs.append({
            "id": 1000 + index, "run_id": 39, "run_attempt": 1,
            "name": f"mutation (continuation shard {index})", "status": "completed",
            "conclusion": "success", "steps": [{"name": "run", "conclusion": "success"}],
        })
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(json.dumps({"total_count": len(jobs), "jobs": jobs}))
    artifacts = [{
        "id": 2000 + index,
        "name": f"mutation-preflight-wave-3-39-1-{index}",
        "size_in_bytes": 100, "digest": f"sha256:{index:064x}", "expired": False,
        "workflow_run": {"id": 39, "head_sha": candidate},
    } for index in completed]
    artifacts_path = tmp_path / "artifacts.json"
    artifacts_path.write_text(json.dumps({"total_count": len(artifacts), "artifacts": artifacts}))
    return root, manifests_dir, reports, plan_path, jobs_path, artifacts_path, identity, candidate


def test_batch_admission_validates_exact_evidence_and_emits_only_next_matrix(monkeypatch, tmp_path):
    fixture = _batch_fixture(monkeypatch, tmp_path)

    result = validate_continuation_batch(
        fixture[0], fixture[3], fixture[1], fixture[2], fixture[4], fixture[5],
        batch=1, orchestration_sha=fixture[7], identity=fixture[6],
    )

    assert result["validated_shards"] == WAVE_3_BATCHES[0]
    assert result["cumulative_shards"] == WAVE_3_BATCHES[0]
    assert result["next_matrix"] == {"shard": WAVE_3_BATCHES[1]}


@pytest.mark.parametrize("batch", range(1, 7))
def test_batch_admission_validates_each_cumulative_boundary(monkeypatch, tmp_path, batch):
    fixture = _batch_fixture(monkeypatch, tmp_path, batch=batch)

    result = validate_continuation_batch(
        fixture[0], fixture[3], fixture[1], fixture[2], fixture[4], fixture[5],
        batch=batch, orchestration_sha=fixture[7], identity=fixture[6],
    )

    expected = [index for members in WAVE_3_BATCHES[:batch] for index in members]
    assert result["validated_shards"] == WAVE_3_BATCHES[batch - 1]
    assert result["cumulative_shards"] == expected
    assert result["next_matrix"] == {"shard": WAVE_3_BATCHES[batch]}


@pytest.mark.parametrize(
    "fault", ["failed", "cancelled", "missing-job", "duplicate-job", "missing-artifact",
              "duplicate-artifact", "incompatible-artifact", "missing-report",
              "duplicate-report", "malformed-report", "later-job", "identity"],
)
def test_batch_admission_rejects_non_pass_evidence(monkeypatch, tmp_path, fault):
    fixture = list(_batch_fixture(monkeypatch, tmp_path))
    jobs_path, artifacts_path, reports, identity = fixture[4], fixture[5], fixture[2], fixture[6]
    jobs_payload = json.loads(jobs_path.read_text())
    artifacts_payload = json.loads(artifacts_path.read_text())
    if fault in {"failed", "cancelled"}:
        jobs_payload["jobs"][0]["conclusion"] = fault
    elif fault == "missing-job":
        jobs_payload["jobs"].pop()
    elif fault == "duplicate-job":
        jobs_payload["jobs"].append(deepcopy(jobs_payload["jobs"][0]))
        jobs_payload["jobs"][-1]["id"] += 9000
    elif fault == "later-job":
        later = deepcopy(jobs_payload["jobs"][0])
        later["id"] += 9000
        later["name"] = f"mutation (continuation shard {WAVE_3_BATCHES[1][0]})"
        jobs_payload["jobs"].append(later)
    elif fault == "missing-artifact":
        artifacts_payload["artifacts"].pop()
    elif fault == "duplicate-artifact":
        artifacts_payload["artifacts"].append(deepcopy(artifacts_payload["artifacts"][0]))
        artifacts_payload["artifacts"][-1]["id"] += 9000
    elif fault == "incompatible-artifact":
        artifacts_payload["artifacts"][0]["workflow_run"]["head_sha"] = "d" * 40
    elif fault in {"missing-report", "malformed-report", "duplicate-report"}:
        target = next(reports.rglob("mutation-preflight.json"))
        if fault == "missing-report":
            target.unlink()
        elif fault == "malformed-report":
            target.write_text("[]")
        else:
            duplicate = reports / "duplicate"
            duplicate.mkdir()
            (duplicate / target.name).write_bytes(target.read_bytes())
    else:
        identity = {**identity, "run_id": "40"}
    jobs_payload["total_count"] = len(jobs_payload["jobs"])
    artifacts_payload["total_count"] = len(artifacts_payload["artifacts"])
    jobs_path.write_text(json.dumps(jobs_payload))
    artifacts_path.write_text(json.dumps(artifacts_payload))

    with pytest.raises(ValueError):
        validate_continuation_batch(
            fixture[0], fixture[3], fixture[1], fixture[2], fixture[4], fixture[5],
            batch=1, orchestration_sha=fixture[7], identity=identity,
        )


def test_wave_validation_accepts_exact_complete_membership(monkeypatch, tmp_path):
    root, manifests_dir, reports, manifests, identity, plan = _fixture(monkeypatch, tmp_path)
    _write_wave(reports, manifests)

    result = validate_wave(root, plan, manifests_dir, reports, "wave-1", "a" * 40, identity)

    assert result["passed"] is True
    assert result["shards"] == WAVES["wave-1"]
    assert len(result["report_digests"]) == 8


@pytest.mark.parametrize("fault", ["missing", "duplicate", "failed", "malformed", "substituted", "identity"])
def test_wave_validation_rejects_invalid_evidence(monkeypatch, tmp_path, fault):
    root, manifests_dir, reports, manifests, identity, plan = _fixture(monkeypatch, tmp_path)
    _write_wave(reports, manifests)
    target = reports / str(WAVES["wave-1"][0]) / "mutation-preflight.json"
    if fault == "missing":
        target.unlink()
    elif fault == "duplicate":
        duplicate = reports / "duplicate"
        duplicate.mkdir()
        (duplicate / target.name).write_bytes(target.read_bytes())
    elif fault == "malformed":
        target.write_text("[]")
    elif fault == "identity":
        changed = deepcopy(identity)
        changed["run_attempt"] = "2"
        identity = changed
    else:
        payload = json.loads(target.read_text())
        if fault == "failed":
            payload["passed"] = False
        if fault == "substituted":
            payload["manifest_digest"] = "f" * 64
        target.write_text(json.dumps(payload))

    with pytest.raises(ValueError):
        validate_wave(root, plan, manifests_dir, reports, "wave-1", "a" * 40, identity)


def test_all_fixed_waves_feed_authoritative_complete_corpus_aggregation(monkeypatch, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("\n".join(f"line_{index} = 1" for index in range(256)) + "\n")
    reports = []
    for shards in WAVES.values():
        for index in shards:
            fingerprint = f"{index + 1:064x}"
            reports.append({
                "status": "completed", "passed": True, "engine_version": "2.5.1",
                "shard_index": index, "shard_count": 256, "manifest_digest": f"{index:064x}",
                "line_ranges": [{"file": "src/app.py", "start": index + 1, "end": index + 1}],
                "files": ["src/app.py"], "generated": 1, "canonicalized": 1, "collisions": 0,
                "fingerprints": [fingerprint], "corpus": [{"fingerprint": fingerprint}],
            })

    monkeypatch.setattr("fettle.mutation_test._revision", lambda _root: FROZEN_CANDIDATE)

    result = aggregate_preflight_shards(str(tmp_path), reports, ["src/"], [], 256)

    assert result["status"] == "completed"
    assert result["generated"] == result["canonicalized"] == 256
    assert result["collisions"] == 0


def test_mixed_origin_recovery_record_reconciles_all_256_reports(monkeypatch, tmp_path):
    root, manifests_dir, reports_dir, manifests, identity, _ = _fixture(monkeypatch, tmp_path)
    identity["run_id"] = "38"
    plan = build_plan(root, manifests_dir, "b" * 40, identity)
    plan.update({
        "mode": "staged-preflight-recovery",
        "source": {"run_id": SOURCE_RUN_ID, "verdict": "original run remains permanently non-pass"},
        "origin_assignment": {
            str(index): {
                "run_id": SOURCE_RUN_ID if index in WAVES["wave-1"] else "38",
                "run_attempt": "1",
                "wave": next(name for name, shards in WAVES.items() if index in shards),
            }
            for index in range(256)
        },
    })
    for wave in WAVES:
        _write_wave(reports_dir, manifests, wave)
    monkeypatch.setattr(
        "scripts.staged_preflight.SOURCE_REPORT_SHA256",
        {
            index: _file_sha(reports_dir / str(index) / "mutation-preflight.json")
            for index in WAVES["wave-1"]
        },
    )
    plan_path = tmp_path / "recovery-plan.json"
    plan_path.write_text(json.dumps(plan))
    aggregate_path = tmp_path / "aggregate.json"
    aggregate_path.write_text(json.dumps({
        "status": "completed", "passed": True, "revision": FROZEN_CANDIDATE,
        "shard_count": 256, "manifest_digests": plan["manifest_digests"],
        "generated": 256, "canonicalized": 256, "collisions": 0,
    }))

    result = build_recovery_record(plan_path, reports_dir, aggregate_path)

    assert result["passed"] is True
    assert len(result["origins"]) == 256
    assert result["origins"]["8"]["run_id"] == SOURCE_RUN_ID
    assert result["origins"]["0"]["run_id"] == "38"
    assert all(item["artifact_sha256"] for item in result["origins"].values())


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "boolean-index", "source-hash", "origin", "aggregate"],
)
def test_recovery_record_rejects_incomplete_or_conflicting_origins(monkeypatch, tmp_path, fault):
    root, manifests_dir, reports_dir, manifests, identity, _ = _fixture(monkeypatch, tmp_path)
    identity["run_id"] = "38"
    plan = build_plan(root, manifests_dir, "b" * 40, identity)
    plan.update({
        "mode": "staged-preflight-recovery", "source": {"run_id": SOURCE_RUN_ID},
        "origin_assignment": {
            str(index): {"run_id": SOURCE_RUN_ID if index in WAVES["wave-1"] else "38",
                         "run_attempt": "1", "wave": next(name for name, shards in WAVES.items() if index in shards)}
            for index in range(256)
        },
    })
    for wave in WAVES:
        _write_wave(reports_dir, manifests, wave)
    expected = {
        index: _file_sha(reports_dir / str(index) / "mutation-preflight.json")
        for index in WAVES["wave-1"]
    }
    monkeypatch.setattr("scripts.staged_preflight.SOURCE_REPORT_SHA256", expected)
    if fault == "missing":
        (reports_dir / "0" / "mutation-preflight.json").unlink()
    elif fault == "duplicate":
        duplicate = reports_dir / "duplicate"
        duplicate.mkdir()
        (duplicate / "mutation-preflight.json").write_bytes(
            (reports_dir / "0" / "mutation-preflight.json").read_bytes(),
        )
    elif fault == "boolean-index":
        path = reports_dir / "1" / "mutation-preflight.json"
        report = json.loads(path.read_text())
        report["shard_index"] = True
        path.write_text(json.dumps(report))
    elif fault == "source-hash":
        expected[WAVES["wave-1"][0]] = "0" * 64
    elif fault == "origin":
        plan["origin_assignment"]["0"]["run_id"] = SOURCE_RUN_ID
    plan_path = tmp_path / "recovery-plan.json"
    plan_path.write_text(json.dumps(plan))
    aggregate_path = tmp_path / "aggregate.json"
    aggregate_path.write_text(json.dumps({
        "status": "completed", "passed": True, "revision": FROZEN_CANDIDATE,
        "shard_count": 256, "manifest_digests": plan["manifest_digests"],
        "generated": 255 if fault == "aggregate" else 256,
        "canonicalized": 256, "collisions": 0,
    }))

    with pytest.raises(ValueError):
        build_recovery_record(plan_path, reports_dir, aggregate_path)


def test_wave_validation_rejects_different_orchestration_commit(monkeypatch, tmp_path):
    root, manifests_dir, reports, manifests, identity, plan = _fixture(monkeypatch, tmp_path)
    _write_wave(reports, manifests)

    with pytest.raises(ValueError, match="identity"):
        validate_wave(root, plan, manifests_dir, reports, "wave-1", "b" * 40, identity)


@pytest.mark.parametrize(
    "payload",
    [[], [{"jobs": []}], [{"jobs": [{"started_at": None, "completed_at": "2026-10-06T01:00:00Z"}]}]],
)
def test_budget_usage_rejects_missing_or_partial_job_evidence(tmp_path, payload):
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError):
        observed_runner_minutes(path)


def test_budget_usage_sums_completed_runner_time(tmp_path):
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps([{"total_count": 3, "jobs": [
        {"id": 1, "status": "completed", "conclusion": "success", "runner_id": 1,
         "runner_name": "runner", "runner_group_id": None, "runner_group_name": None,
         "steps": [{}], "started_at": "2026-10-06T01:00:00Z", "completed_at": "2026-10-06T01:02:30Z"},
        {"id": 2, "status": "in_progress", "conclusion": None, "runner_id": 2,
         "runner_name": "runner", "runner_group_id": None, "runner_group_name": None,
         "steps": [{}], "started_at": "2026-10-06T01:00:00Z", "completed_at": None},
        {"id": 3, "started_at": None, "completed_at": None, "status": "completed",
         "conclusion": "skipped", "runner_id": None, "runner_name": None,
         "runner_group_id": None, "runner_group_name": None, "steps": []},
    ]}]))

    now = datetime(2026, 10, 6, 1, 3, tzinfo=UTC)

    assert observed_runner_minutes(path, now) == 5.5


def _job(job_id, *, status="completed", conclusion="success", start="2026-10-06T01:00:00Z",
         end="2026-10-06T01:02:00Z", runner_id=10, steps=None, run_id=7, run_attempt=1):
    return {
        "id": job_id, "run_id": run_id, "run_attempt": run_attempt,
        "created_at": start,
        "status": status, "conclusion": conclusion, "started_at": start,
        "completed_at": end, "runner_id": runner_id, "runner_name": "runner" if runner_id else None,
        "runner_group_id": None, "runner_group_name": None,
        "steps": [{"name": "work"}] if steps is None and runner_id else (steps or []),
    }


def _jobs_file(tmp_path, pages, name="jobs.json"):
    path = tmp_path / name
    path.write_text(json.dumps(pages))
    return path


def test_accounting_preserves_observed_acquisition_exposure_and_terminal_revision(tmp_path):
    fixture = json.loads((Path(__file__).parent / "fixtures/staged_preflight_accounting_revision.json").read_text())
    responses = Path(__file__).parent / "fixtures/staged_preflight_accounting_revision"
    charges = []
    for index, observation in enumerate(fixture["observations"], 1):
        path = responses / f"jobs-{index}.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == fixture["provenance"]["snapshot_sha256"][index - 1]

        result = account_runner_minutes(
            path, datetime.fromisoformat(observation["observed_at"].replace("Z", "+00:00")),
            expected_run_id="37795579761", expected_run_attempt="1", job_timeout_minutes=35,
        )

        anomalous = next(job for job in result["included_jobs"] if job["id"] == fixture["provenance"]["job_id"])
        charges.append(anomalous["minutes"])
        assert anomalous["execution_evidence"] == "absent"
        anomaly = next(item for item in result["anomalies"] if item["id"] == anomalous["id"])
        assert anomaly["resource_usage_basis"].startswith("bounded exposure")
    assert charges == [0.12, 0.38, 0.65]

    path = responses / "jobs-terminal.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == fixture["provenance"]["terminal_jobs_sha256"]
    result = account_runner_minutes(path, expected_run_id="37795579761", expected_run_attempt="1")
    corrected = next(job for job in result["included_jobs"] if job["id"] == fixture["provenance"]["job_id"])
    assert corrected["minutes"] == 1.17
    assert corrected["started_at"] == fixture["terminal"]["started_at"]
    assert corrected["execution_evidence"] == "confirmed"


def test_accounting_does_not_use_execution_timeout_to_erase_queue_exposure(tmp_path):
    job = _job(1, status="queued", conclusion=None, start="2026-10-06T01:00:00Z",
               end=None, runner_id=None, steps=[])
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 2, tzinfo=UTC), expected_run_id="7",
        expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 60
    assert result["anomalies"][0]["timeout_bound_applied"] is False
    assert "cannot safely truncate" in result["anomalies"][0]["timeout_note"]


def test_accounting_does_not_trust_later_reported_start_to_reduce_exposure(tmp_path):
    job = _job(1, status="queued", conclusion=None, start="2026-10-06T01:30:00Z",
               end=None, runner_id=None, steps=[])
    job["created_at"] = "2026-10-06T01:00:00Z"
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 3, tzinfo=UTC), expected_run_id="7",
        expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 120
    assert result["anomalies"][0]["timeout_bound_applied"] is False


def test_accounting_uses_dispatch_when_reported_start_precedes_it(tmp_path):
    job = _job(1, status="queued", conclusion=None, start="2026-10-06T01:00:00Z",
               end=None, runner_id=None, steps=[])
    job["created_at"] = "2026-10-06T01:30:00Z"
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 2, tzinfo=UTC), expected_run_id="7",
        expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 30


@pytest.mark.parametrize("now, timeout", [(None, 35), (datetime(2026, 10, 6, 1, 1, tzinfo=UTC), None)])
def test_accounting_rejects_acquisition_exposure_without_explicit_bound(tmp_path, now, timeout):
    job = _job(1, status="queued", conclusion=None, start="2026-10-06T01:00:00Z",
               end=None, runner_id=None, steps=[])
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="explicit observation bound"):
        account_runner_minutes(path, now, expected_run_id="7", expected_run_attempt="1",
                               job_timeout_minutes=timeout)


def test_accounting_rejects_acquisition_exposure_without_dispatch_time(tmp_path):
    job = _job(1, status="queued", conclusion=None, end=None, runner_id=None, steps=[])
    job.pop("created_at")
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="created_at"):
        account_runner_minutes(
            path, datetime(2026, 10, 6, 1, 1, tzinfo=UTC), expected_run_id="7",
            expected_run_attempt="1", job_timeout_minutes=35,
        )


def test_accounting_acquisition_exposure_can_cross_budget_gate(tmp_path):
    jobs = [
        _job(index, status="queued", conclusion=None, start="2026-10-06T01:00:00Z",
             end=None, runner_id=None, steps=[])
        for index in range(1, 33)
    ]
    path = _jobs_file(tmp_path, [{"total_count": len(jobs), "jobs": jobs}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 1, 36, tzinfo=UTC), expected_run_id="7",
        expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 1152
    assert result["estimated_runner_minutes"] > BUDGET["launch_ceiling"]["complete"]


def test_accounting_rejects_naive_explicit_observation_time(tmp_path):
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1)]}])

    with pytest.raises(ValueError, match="timezone-aware"):
        account_runner_minutes(path, datetime(2026, 10, 6, 1, 1),
                               expected_run_id="7", expected_run_attempt="1")


def _source_handoff_fixture(tmp_path):
    repository = "owner/repo"
    source_run_id = "37"
    candidate_sha = "f" * 40
    orchestration_sha = "e" * 40
    branch = "candidate"
    workflow_ref = f"{repository}/.github/workflows/mutation.yml@refs/heads/{branch}"
    run = {
        "id": 37, "run_attempt": 1, "status": "completed", "conclusion": "failure",
        "event": "workflow_dispatch", "head_sha": orchestration_sha, "head_branch": branch,
        "path": ".github/workflows/mutation.yml",
        "head_repository": {"full_name": repository},
    }
    jobs = []
    names = {
        "mutation (freeze staged preflight)",
        "mutation (validate staged preflight wave 1)",
        "mutation (validate staged preflight wave 2)",
        "mutation (monitor staged preflight budget)",
    }
    names.update(f"mutation (staged preflight wave 1 shard {index})" for index in WAVES["wave-1"])
    names.update(f"mutation (staged preflight wave 2 shard {index})" for index in WAVES["wave-2"])
    for job_id, name in enumerate(sorted(names), 1):
        jobs.append({
            **_job(job_id, run_id=37, steps=[{"name": "work", "conclusion": "success"}]),
            "name": name,
        })
    dispatch = {
        **_job(len(jobs) + 1, run_id=37, conclusion="failure", steps=[
            {"name": "Set up job", "conclusion": "success"},
            {"name": "Dispatch immutable continuation", "conclusion": "failure"},
            {"name": "Retain handoff evidence", "conclusion": "skipped"},
        ]),
        "name": "mutation (dispatch staged preflight continuation)",
    }
    jobs.append(dispatch)
    artifact_names = {
        f"mutation-staged-plan-{source_run_id}-1",
        f"mutation-preflight-wave-1-validation-{source_run_id}-1",
        f"mutation-preflight-wave-2-validation-{source_run_id}-1",
        f"mutation-preflight-monitor-{source_run_id}-1",
    }
    artifact_names.update(
        f"mutation-preflight-{wave}-{source_run_id}-1-{index}"
        for wave in ("wave-1", "wave-2") for index in WAVES[wave]
    )
    artifacts = [{
        "id": index, "name": name, "expired": False,
        "workflow_run": {"id": 37, "head_sha": orchestration_sha},
    } for index, name in enumerate(sorted(artifact_names), 1)]
    run_path = tmp_path / "source-run.json"
    jobs_path = tmp_path / "source-jobs.json"
    artifacts_path = tmp_path / "source-artifacts.json"
    run_path.write_text(json.dumps(run))
    jobs_path.write_text(json.dumps([{"total_count": len(jobs), "jobs": jobs}]))
    artifacts_path.write_text(json.dumps([{
        "total_count": len(artifacts), "artifacts": artifacts,
    }]))
    return {
        "run": run, "jobs": jobs, "artifacts": artifacts,
        "run_path": run_path, "jobs_path": jobs_path, "artifacts_path": artifacts_path,
        "repository": repository, "source_run_id": source_run_id,
        "candidate_sha": candidate_sha, "source_orchestration_sha": orchestration_sha,
        "source_workflow_ref": workflow_ref,
    }


def _validate_source_fixture(fixture):
    return validate_source_handoff(
        fixture["run_path"], fixture["jobs_path"], fixture["artifacts_path"],
        repository=fixture["repository"], source_run_id=fixture["source_run_id"],
        candidate_sha=fixture["candidate_sha"],
        source_orchestration_sha=fixture["source_orchestration_sha"],
        source_workflow_ref=fixture["source_workflow_ref"],
    )


def test_source_handoff_accepts_failure_confined_to_dispatch(tmp_path):
    fixture = _source_handoff_fixture(tmp_path)

    result = _validate_source_fixture(fixture)

    assert result["handoff_only_failure"] is True
    assert result["prerequisite_job_count"] == 44
    assert result["prerequisite_artifact_count"] == 44


@pytest.mark.parametrize(
    "fault",
    ["shard", "gate", "identity", "artifact", "expired", "artifact-origin", "ambiguous"],
)
def test_source_handoff_rejects_substantive_or_ambiguous_failures(tmp_path, fault):
    fixture = _source_handoff_fixture(tmp_path)
    if fault == "shard":
        fixture["jobs"][0]["conclusion"] = "failure"
    elif fault == "gate":
        next(job for job in fixture["jobs"] if job["name"] == "mutation (validate staged preflight wave 2)")["conclusion"] = "failure"
    elif fault == "identity":
        fixture["run"]["head_sha"] = "d" * 40
    elif fault == "artifact":
        fixture["artifacts"].pop()
    elif fault == "expired":
        fixture["artifacts"][0]["expired"] = True
    elif fault == "artifact-origin":
        fixture["artifacts"][0]["workflow_run"]["head_sha"] = "d" * 40
    else:
        dispatch = fixture["jobs"][-1]
        dispatch["steps"].insert(1, {"name": "Unknown failed step", "conclusion": "failure"})
    fixture["run_path"].write_text(json.dumps(fixture["run"]))
    fixture["jobs_path"].write_text(json.dumps([{
        "total_count": len(fixture["jobs"]), "jobs": fixture["jobs"],
    }]))
    fixture["artifacts_path"].write_text(json.dumps([{
        "total_count": len(fixture["artifacts"]), "artifacts": fixture["artifacts"],
    }]))

    with pytest.raises(ValueError):
        _validate_source_fixture(fixture)


def test_continuation_dispatch_validation_rejects_duplicates(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps([{"total_count": 0, "workflow_runs": []}]))
    current = tmp_path / "current.json"
    current.write_text(json.dumps([{"total_count": 1, "workflow_runs": [{
        "id": 41, "display_title": "Staged preflight continuation for source 37/1",
    }]}]))

    assert validate_continuation_dispatches(empty, "37")["passed"] is True
    assert validate_continuation_dispatches(current, "37", "41")["passed"] is True
    with pytest.raises(ValueError, match="already has"):
        validate_continuation_dispatches(current, "37")


def _calibration_run_file(tmp_path, name="run.json", **changes):
    run = {
        "schema_version": "1", "kind": "calibration_source",
        "run_id": "37", "run_attempt": "1", "revision": "f" * 40,
        "mode": "calibration", "calibration_id": "calibration-a",
        "calibration_stage": "1",
        **changes,
    }
    path = tmp_path / name
    path.write_text(json.dumps(run))
    return path


def test_accounting_excludes_proven_skipped_job_but_records_reversed_timestamp(tmp_path):
    skipped = _job(
        1, conclusion="skipped", start="2026-10-06T01:00:01Z",
        end="2026-10-06T01:00:00Z", runner_id=None, steps=[],
    )
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [skipped]}])

    result = account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")

    assert result["estimated_runner_minutes"] == 0
    assert result["excluded_jobs"][0]["reason"] == "completed skipped job did not acquire a runner"
    assert result["excluded_jobs"][0]["excluded_fields"] == ["started_at", "completed_at"]
    assert result["anomalies"][0]["reason"] == "skipped job timestamps are reversed"


@pytest.mark.parametrize("field", ["runner_id", "runner_name", "runner_group_id", "runner_group_name"])
def test_accounting_rejects_skipped_job_with_any_runner_identity(tmp_path, field):
    job = _job(
        1,
        status="completed",
        conclusion="skipped",
        end="2026-10-06T01:00:00Z",
        runner_id=None,
        steps=[],
    )
    job.update({
        "runner_id": None, "runner_name": None,
        "runner_group_id": None, "runner_group_name": None,
    })
    job[field] = 9 if field.endswith("_id") else "runner"
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize("field", ["runner_id", "runner_name", "runner_group_id", "runner_group_name"])
def test_accounting_rejects_missing_runner_identity_field(tmp_path, field):
    job = _job(1, conclusion="skipped", runner_id=None, steps=[])
    job.pop(field)
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="runner identity is incomplete"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize("conclusion", ["success", "failure", "cancelled", "timed_out"])
def test_accounting_charges_every_completed_executed_job(tmp_path, conclusion):
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, conclusion=conclusion)]}])

    result = account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")

    assert result["estimated_runner_minutes"] == 2
    assert result["included_jobs"][0]["conclusion"] == conclusion


def test_accounting_charges_in_progress_job_to_observation_time(tmp_path):
    job = _job(1, status="in_progress", conclusion=None, end=None)
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 1, 3, tzinfo=UTC),
        expected_run_id="7", expected_run_attempt="1",
    )

    assert result["estimated_runner_minutes"] == 3
    assert result["included_jobs"][0]["basis"] == "elapsed through observation time"


@pytest.mark.parametrize("status", ["queued", "requested", "pending", "waiting"])
def test_accounting_charges_runner_acquisition_transition(tmp_path, status):
    job = _job(1, status=status, conclusion=None, end=None, steps=[])
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 1, 3, tzinfo=UTC),
        expected_run_id="7", expected_run_attempt="1",
    )

    assert result["estimated_runner_minutes"] == 3
    assert result["included_jobs"][0]["basis"] == (
        "runner-acquisition transition elapsed through observation time"
    )


def test_accounting_rejects_transition_with_unbounded_metadata(tmp_path):
    missing_start = _job(1, status="queued", conclusion=None, start=None, end=None)

    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [missing_start]}])
    with pytest.raises(ValueError):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_charges_and_flags_partial_identity_during_acquisition(tmp_path):
    partial_runner = _job(2, status="queued", conclusion=None, end=None)
    partial_runner["runner_name"] = None
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [partial_runner]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 1, 3, tzinfo=UTC),
        expected_run_id="7", expected_run_attempt="1",
    )

    assert result["estimated_runner_minutes"] == 3
    assert result["anomalies"][0]["reason"] == (
        "active job runner identity is partial during acquisition"
    )


def test_accounting_rejects_partial_identity_after_completion(tmp_path):
    completed = _job(2)
    completed["runner_name"] = None
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [completed]}])

    with pytest.raises(ValueError, match="partial"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_does_not_exclude_started_job_with_missing_execution_metadata(tmp_path):
    job = _job(
        1, status="queued", conclusion=None, end=None, runner_id=None, steps=[],
    )
    job.update({"runner_name": None, "runner_group_id": None, "runner_group_name": None})
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="explicit observation bound"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize(
    "job",
    [
        _job(1, start=None, end="2026-10-06T01:02:00Z"),
        _job(1, status="completed", conclusion="cancelled", start=None, end=None, runner_id=None),
        _job(1, start="2026-10-06T01:02:00Z", end="2026-10-06T01:00:00Z"),
    ],
)
def test_accounting_rejects_unknown_usage_for_potentially_executed_job(tmp_path, job):
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_accepts_complete_pagination_and_rejects_duplicate_jobs(tmp_path):
    pages = [
        {"total_count": 2, "jobs": [_job(1)]},
        {"total_count": 2, "jobs": [_job(2)]},
    ]
    path = _jobs_file(tmp_path, pages)

    result = account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")
    assert result["page_count"] == 2
    assert result["job_count"] == 2
    assert result["estimated_runner_minutes"] == 4

    pages[1]["jobs"][0]["id"] = 1
    path.write_text(json.dumps(pages))
    with pytest.raises(ValueError, match="duplicate"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_rejects_wrong_run_or_attempt(tmp_path):
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_attempt=2)]}])

    with pytest.raises(ValueError, match="origin"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize("field", ["total_count", "id"])
def test_accounting_rejects_boolean_integer_fields(tmp_path, field):
    job = _job(1)
    page = {"total_count": 1, "jobs": [job]}
    if field == "total_count":
        page[field] = True
    else:
        job[field] = True
    path = _jobs_file(tmp_path, [page])

    with pytest.raises(ValueError):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize(
    ("used", "next_wave", "passed"),
    [(32, "wave-2", True), (32.01, "wave-2", False),
     (100.77, "wave-3", True), (152, "wave-3", True), (152.01, "wave-3", False),
     (952, "aggregate", True), (952.01, "aggregate", False),
     (1120, "complete", True), (1120.01, "complete", False)],
)
def test_budget_transition_boundaries(used, next_wave, passed):
    assert (used <= BUDGET["launch_ceiling"][next_wave]) is passed


def test_calibration_budget_reserves_cancellation_lag_and_rejects_unknown_usage():
    accounting = {"estimated_runner_minutes": 10799.5, "included_jobs": []}
    accepted = evaluate_calibration_budget(accounting, ceiling=12000, cancellation_reserve=1200)
    exhausted = evaluate_calibration_budget(
        {**accounting, "estimated_runner_minutes": 10800.01},
        ceiling=12000, cancellation_reserve=1200,
    )

    assert accepted["passed"] is True
    assert accepted["launch_cutoff"] == 10800
    assert accepted["cancellation_lag_charge"] == 0
    assert accepted["billing_authority"] is False
    assert exhausted["passed"] is False
    with pytest.raises(ValueError, match="usage"):
        evaluate_calibration_budget({}, ceiling=12000, cancellation_reserve=1200)
    with pytest.raises(ValueError, match="included job"):
        evaluate_calibration_budget(
            {"estimated_runner_minutes": 1}, ceiling=12000, cancellation_reserve=1200,
        )


@pytest.mark.parametrize("status", [None, True, 2, "queued", "unknown"])
def test_calibration_budget_rejects_malformed_included_job_status(status):
    with pytest.raises(ValueError, match="included job"):
        evaluate_calibration_budget(
            {"estimated_runner_minutes": 1, "included_jobs": [{"status": status}]},
            ceiling=12000, cancellation_reserve=1200,
        )


def test_calibration_budget_charges_active_jobs_for_cancellation_lag():
    accounting = {
        "estimated_runner_minutes": 10791,
        "included_jobs": [
            {"status": "in_progress", "minutes": 1, "basis": "elapsed through observation time", "execution_evidence": "confirmed"},
            {"status": "in_progress", "minutes": 1, "basis": "elapsed through observation time", "execution_evidence": "confirmed"},
            {"status": "completed"},
        ],
    }

    result = evaluate_calibration_budget(accounting, ceiling=12000, cancellation_reserve=1200)

    assert result["cancellation_lag_charge"] == 10
    assert result["charged_runner_minutes"] == 10801
    assert result["passed"] is False


def test_calibration_budget_accepts_conservatively_bounded_queued_acquisition():
    accounting = {
        "estimated_runner_minutes": 100,
        "included_jobs": [{
            "status": "queued", "minutes": 100,
            "basis": "queued acquisition exposure bounded from dispatch through observation",
            "execution_evidence": "absent",
        }],
    }

    result = evaluate_calibration_budget(accounting, ceiling=1500, cancellation_reserve=1200)

    assert result["active_jobs"] == 1
    assert result["cancellation_lag_charge"] == 5
    assert result["charged_runner_minutes"] == 105
    assert result["passed"] is True


@pytest.mark.parametrize(
    "job",
    [
        {"status": "queued", "minutes": 1, "basis": "unknown", "execution_evidence": "absent"},
        {"status": "queued", "minutes": 1, "basis": "queued acquisition exposure bounded from dispatch through observation", "execution_evidence": "confirmed"},
        {"status": "queued", "minutes": -1, "basis": "queued acquisition exposure bounded from dispatch through observation", "execution_evidence": "absent"},
    ],
)
def test_calibration_budget_rejects_malformed_acquisition(job):
    with pytest.raises(ValueError, match="acquisition|active"):
        evaluate_calibration_budget(
            {"estimated_runner_minutes": 1, "included_jobs": [job]},
            ceiling=1500, cancellation_reserve=1200,
        )


def test_calibration_stage_3_batches_are_exact_and_fixed():
    batches = calibration_stage_3_batches(WAVES["wave-3"])

    assert [len(batch) for batch in batches] == [32, 32, 32, 32, 32, 32, 24]
    assert len(WAVES["wave-3"]) == 216
    assert [shard for batch in batches for shard in batch] == WAVES["wave-3"]
    assert len(set(shard for batch in batches for shard in batch)) == 216
    assert set(WAVES["wave-1"]) | set(WAVES["wave-2"]) | set(WAVES["wave-3"]) == set(range(256))

    with pytest.raises(ValueError, match="exact frozen shard membership"):
        calibration_stage_3_batches(WAVES["wave-3"][:-1])


def test_sparse_continuation_requires_job_provenance_for_missing_checkpoints(tmp_path):
    manifests = [
        {"shard_index": 0, "digest": "a" * 64},
        {"shard_index": 1, "digest": "b" * 64},
        {"shard_index": 2, "digest": "c" * 64},
    ]
    jobs = [
        _job(1, run_id=37),
        _job(2, run_id=37, conclusion="cancelled"),
        _job(3, run_id=37, conclusion="skipped", runner_id=None, steps=[]),
    ]
    for index, job in enumerate(jobs):
        job["name"] = f"execute / mutation (full shard {index}, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 3, "jobs": jobs}])
    checkpoints = tmp_path / "checkpoints"
    checkpoint_dir = checkpoints / "mutation-checkpoint-calibration-a-0"
    checkpoint_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps({
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        }, "outcomes": {"x": {}},
        "attempts": [], "status": "completed", "pending": 0,
    }))
    reports = tmp_path / "reports" / "0"
    reports.mkdir(parents=True)
    reports.joinpath("mutation-report.json").write_text(json.dumps({
        "status": "completed", "shard_index": 0, "calibration_id": "calibration-a",
        "revision": "f" * 40, "preflight_digest": "e" * 64,
        "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
        "environment_digest": "c" * 64,
    }))

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, checkpoints, tmp_path / "reports",
        manifests, [0, 1, 2], "calibration-a", "37", "1", "f" * 40, "1",
    )

    assert result["matrix"] == {"shard": [1, 2]}
    assert result["shards"]["0"]["state"] == "completed"
    assert result["shards"]["1"]["state"] == "started_interrupted"
    assert result["shards"]["2"]["state"] == "never_started"


def test_sparse_continuation_never_infers_missing_checkpoint(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [
        {**_job(1, run_id=37), "name": "mutation (full shard 0, advisory)"},
    ]}])

    with pytest.raises(ValueError, match="successful shard 0 has no checkpoint"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


def test_sparse_continuation_proves_skipped_shard_never_acquired_runner(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="skipped", runner_id=None, steps=[])
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
        tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
        "f" * 40, "1",
    )

    assert result["matrix"] == {"shard": [0]}
    assert result["shards"]["0"]["state"] == "never_started"


def test_sparse_continuation_retries_cancelled_no_runner_but_charges_interval(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="cancelled", runner_id=None, steps=[])
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
        tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
        "f" * 40, "1",
    )

    assert result["matrix"] == {"shard": [0]}
    assert result["shards"]["0"]["state"] == "cancelled_before_execution"
    assert result["accounting"]["estimated_runner_minutes"] == 2


@pytest.mark.parametrize("fault", ["calibration", "manifest", "duplicate"])
def test_sparse_continuation_rejects_incompatible_or_conflicting_checkpoints(tmp_path, fault):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [
        {**_job(1, run_id=37), "name": "mutation (full shard 0, advisory)"},
    ]}])
    checkpoints = tmp_path / "checkpoints"
    first = checkpoints / "one"
    first.mkdir(parents=True)
    payload = {
        "schema_version": "1", "calibration_id": "other" if fault == "calibration" else "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "b" * 64 if fault == "manifest" else "a" * 64,
            "corpus_digest": "d" * 64, "environment_digest": "c" * 64,
        },
        "outcomes": {}, "attempts": [], "status": "completed", "pending": 0,
    }
    first.joinpath("mutation-checkpoint.json").write_text(json.dumps(payload))
    if fault == "duplicate":
        second = checkpoints / "two"
        second.mkdir()
        second.joinpath("mutation-checkpoint.json").write_text(json.dumps(payload))

    with pytest.raises(ValueError):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, checkpoints, tmp_path / "reports",
            manifests, [0], "calibration-a", "37", "1", "f" * 40, "1",
        )


def test_sparse_continuation_rejects_conflicting_shared_checkpoint_identity(tmp_path):
    manifests = [
        {"shard_index": 0, "digest": "a" * 64},
        {"shard_index": 1, "digest": "b" * 64},
    ]
    jobs = []
    checkpoints = tmp_path / "checkpoints"
    for index, manifest in enumerate(manifests):
        job = _job(index + 1, run_id=37)
        job["name"] = f"mutation (full shard {index}, advisory)"
        jobs.append(job)
        directory = checkpoints / str(index)
        directory.mkdir(parents=True)
        directory.joinpath("mutation-checkpoint.json").write_text(json.dumps({
            "schema_version": "1", "calibration_id": "calibration-a",
            "identity": {
                "revision": "f" * 40,
                "preflight_digest": ("e" if index == 0 else "9") * 64,
                "manifest_digest": manifest["digest"], "corpus_digest": "d" * 64,
                "environment_digest": "c" * 64,
            },
            "outcomes": {}, "attempts": [], "status": "completed", "pending": 0,
        }))
    jobs_path = _jobs_file(tmp_path, [{"total_count": 2, "jobs": jobs}])

    with pytest.raises(ValueError, match="conflicting shared identity"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, checkpoints, tmp_path / "reports",
            manifests, [0, 1], "calibration-a", "37", "1", "f" * 40, "1",
        )


def test_sparse_continuation_regenerates_report_from_complete_checkpoint(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37)
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoints = tmp_path / "checkpoints" / "0"
    checkpoints.mkdir(parents=True)
    checkpoints.joinpath("mutation-checkpoint.json").write_text(json.dumps({
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        },
        "outcomes": {}, "attempts": [], "status": "completed", "pending": 0,
    }))

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
        tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
        "f" * 40, "1",
    )

    assert result["matrix"] == {"shard": [0]}
    assert result["shards"]["0"]["state"] == "completed_checkpoint_missing_report"


def test_sparse_continuation_rejects_wrong_source_run_inputs(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="skipped", runner_id=None, steps=[])
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    run_path = _calibration_run_file(tmp_path)
    run = json.loads(run_path.read_text())
    run["calibration_id"] = "other"
    run_path.write_text(json.dumps(run))

    with pytest.raises(ValueError, match="source run provenance"):
        plan_calibration_continuation(
            run_path, jobs_path, tmp_path / "checkpoints", tmp_path / "reports",
            manifests, [0], "calibration-a", "37", "1", "f" * 40, "1",
        )


def test_calibration_continuation_and_budget_cli_delivery_path(tmp_path):
    manifests = tmp_path / "manifests"
    checkpoints = tmp_path / "checkpoints" / "completed"
    reports = tmp_path / "reports" / "completed"
    manifests.mkdir()
    checkpoints.mkdir(parents=True)
    reports.mkdir(parents=True)
    for index in range(256):
        (manifests / f"partition-{index}.json").write_text(json.dumps({
            "shard_index": index, "digest": f"{index + 1:064x}",
        }))
    completed = WAVES["wave-1"][0]
    identity = {
        "revision": "f" * 40, "preflight_digest": "e" * 64,
        "manifest_digest": f"{completed + 1:064x}", "corpus_digest": "d" * 64,
        "environment_digest": "c" * 64,
    }
    checkpoints.joinpath("mutation-checkpoint.json").write_text(json.dumps({
        "schema_version": "1", "calibration_id": "calibration-a", "identity": identity,
        "outcomes": {"a" * 64: {"state": "killed", "duration_ms": 1}},
        "attempts": [], "status": "completed", "pending": 0,
    }))
    reports.joinpath("mutation-report.json").write_text(json.dumps({
        "status": "completed", "shard_index": completed,
        "calibration_id": "calibration-a", **identity,
    }))
    jobs = []
    for position, index in enumerate(WAVES["wave-1"]):
        if index == completed:
            job = _job(position + 1, run_id=37)
        else:
            job = _job(
                position + 1, run_id=37, conclusion="skipped", runner_id=None, steps=[],
            )
        job["name"] = f"mutation (full shard {index}, advisory)"
        jobs.append(job)
    jobs_path = _jobs_file(tmp_path, [{"total_count": len(jobs), "jobs": jobs}])
    run_path = _calibration_run_file(tmp_path)
    continuation = tmp_path / "continuation.json"
    script = Path(__file__).parents[1] / "scripts" / "staged_preflight.py"

    subprocess.run([
        sys.executable, str(script), "plan-calibration-continuation",
        "--provenance", str(run_path), "--jobs", str(jobs_path),
        "--checkpoints", str(tmp_path / "checkpoints"),
        "--reports", str(tmp_path / "reports"), "--manifests", str(manifests),
        "--stage", "1", "--calibration-id", "calibration-a",
        "--run-id", "37", "--run-attempt", "1", "--revision", "f" * 40,
        "--output", str(continuation),
    ], check=True)
    plan = json.loads(continuation.read_text())
    assert plan["matrix"]["shard"] == WAVES["wave-1"][1:]
    accounting = tmp_path / "accounting.json"
    accounting.write_text(json.dumps(plan["accounting"]))
    budget = tmp_path / "budget.json"
    subprocess.run([
        sys.executable, str(script), "calibration-budget",
        "--accounting", str(accounting), "--ceiling", "12000",
        "--cancellation-reserve", "1200", "--output", str(budget),
    ], check=True)
    retained = json.loads(budget.read_text())
    assert retained["passed"] is True
    assert retained["billing_authority"] is False
    assert retained["cancellation_lag_charge"] == 0


def test_combined_accounting_charges_original_and_recovery_attempts(tmp_path):
    prior = _jobs_file(
        tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "prior.json",
    )
    current = _jobs_file(
        tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=38)]}], "current.json",
    )

    result = combine_accounting(
        prior, current, expected_prior_run_id="37", expected_current_run_id="38",
        expected_prior_run_attempt="1", expected_current_run_attempt="1",
    )

    assert result["estimated_runner_minutes"] == 4
    assert [item["expected_run_id"] for item in result["sources"]] == ["37", "38"]


def test_three_run_accounting_preserves_every_explicit_origin(tmp_path):
    sources = [
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(index, run_id=run_id)]}],
                    f"{run_id}.json"), str(run_id), "1")
        for index, run_id in enumerate((37, 38, 39), 1)
    ]

    result = combine_accounting_sources(sources)

    assert result["estimated_runner_minutes"] == 6
    assert [item["expected_run_id"] for item in result["sources"]] == ["37", "38", "39"]


def test_terminal_reconciliation_preserves_higher_historical_accounting_floor(tmp_path):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps({
        **terminal, "estimated_runner_minutes": 3.5,
    }))

    result = retain_historical_accounting_floor(terminal, [historical_path])

    assert result["terminal_reconciled_runner_minutes"] == 2
    assert result["historical_observed_runner_minutes_floor"] == 3.5
    assert result["estimated_runner_minutes"] == 3.5
    assert result["historical_floor_applied"] is True
    assert result["historical_accounting"][0]["sha256"] == _file_sha(historical_path)


def test_terminal_reconciliation_keeps_later_higher_terminal_total(tmp_path):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps({
        **terminal, "estimated_runner_minutes": 1.5,
    }))

    result = retain_historical_accounting_floor(terminal, [historical_path])

    assert result["terminal_reconciled_runner_minutes"] == 2
    assert result["estimated_runner_minutes"] == 2
    assert result["historical_floor_applied"] is False


def test_terminal_reconciliation_accepts_prior_floored_combined_report(tmp_path):
    prior = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "prior.json"),
        expected_run_id="37", expected_run_attempt="1",
    )
    current = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=38)]}], "current.json"),
        expected_run_id="38", expected_run_attempt="1",
    )
    terminal = {
        "schema_version": "1", "kind": "combined_operational_runner_time_estimate",
        "billing_authority": False, "estimated_runner_minutes": 4, "sources": [prior, current],
    }
    first_path = tmp_path / "first.json"
    first_path.write_text(json.dumps({
        **terminal, "estimated_runner_minutes": 5,
        "sources": [{**prior, "estimated_runner_minutes": 3}, current],
    }))
    first = retain_historical_accounting_floor(terminal, [first_path])
    retained_path = tmp_path / "retained.json"
    retained_path.write_text(json.dumps(first))

    result = retain_historical_accounting_floor(terminal, [retained_path])

    assert result["terminal_reconciled_runner_minutes"] == 4
    assert result["estimated_runner_minutes"] == 5
    assert result["historical_floor_applied"] is True


def test_terminal_reconciliation_validates_current_accounting_without_history(tmp_path):
    malformed = {
        "schema_version": "999", "kind": "operational_runner_time_estimate",
        "billing_authority": False, "expected_run_id": "37", "expected_run_attempt": "1",
        "estimated_runner_minutes": 2,
    }

    with pytest.raises(ValueError, match="malformed"):
        retain_historical_accounting_floor(malformed, [])


def test_terminal_reconciliation_rejects_historical_origin_drift(tmp_path):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps({
        **terminal, "expected_run_id": "99",
    }))

    with pytest.raises(ValueError, match="incompatible origin"):
        retain_historical_accounting_floor(terminal, [historical_path])


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", "999"), ("billing_authority", True),
     ("estimated_runner_minutes", float("nan")),
     ("estimated_runner_minutes", float("inf"))],
)
def test_terminal_reconciliation_rejects_malformed_current_accounting(tmp_path, field, value):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    terminal[field] = value
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps(account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=37)]}], "prior.json"),
        expected_run_id="37", expected_run_attempt="1",
    )))

    with pytest.raises(ValueError, match="malformed"):
        retain_historical_accounting_floor(terminal, [historical_path])


@pytest.mark.parametrize("field", ["schema_version", "billing_authority"])
def test_terminal_reconciliation_rejects_malformed_nested_historical_source(tmp_path, field):
    prior = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "prior.json"),
        expected_run_id="37", expected_run_attempt="1",
    )
    current = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=38)]}], "current.json"),
        expected_run_id="38", expected_run_attempt="1",
    )
    combined = {
        "schema_version": "1", "kind": "combined_operational_runner_time_estimate",
        "billing_authority": False, "estimated_runner_minutes": 4, "sources": [prior, current],
    }
    historical = json.loads(json.dumps(combined))
    historical["sources"][0][field] = "999" if field == "schema_version" else True
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps(historical))

    with pytest.raises(ValueError, match="malformed"):
        retain_historical_accounting_floor(combined, [historical_path])


def test_four_run_accounting_adds_aggregation_overhead_once(tmp_path):
    sources = [
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(index, run_id=run_id)]}],
                    f"{run_id}.json"), str(run_id), "1")
        for index, run_id in enumerate((37, 38, 39, 40), 1)
    ]

    result = combine_accounting_sources(sources)

    assert result["estimated_runner_minutes"] == 8
    assert [item["expected_run_id"] for item in result["sources"]] == ["37", "38", "39", "40"]


def test_three_run_accounting_rejects_wrong_middle_origin(tmp_path):
    sources = [
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "37.json"), "37", "1"),
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=99)]}], "38.json"), "38", "1"),
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(3, run_id=39)]}], "39.json"), "39", "1"),
    ]

    with pytest.raises(ValueError, match="origin"):
        combine_accounting_sources(sources)


def test_continuation_artifact_inventory_is_exact_and_digest_bound(monkeypatch, tmp_path):
    artifacts = [
        {"id": index + 1, "name": f"mutation-preflight-wave-3-37550308775-1-{index}",
         "size_in_bytes": 1, "digest": f"sha256:{index:064x}", "expired": False}
        for index in WAVES["wave-3"]
    ]
    path = tmp_path / "artifacts.json"
    path.write_text(json.dumps([{"artifacts": artifacts}]))
    artifacts = sorted(artifacts, key=lambda artifact: artifact["name"])
    digest = __import__("hashlib").sha256(
        json.dumps(artifacts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    monkeypatch.setattr("scripts.staged_preflight.CONTINUATION_ARTIFACT_INVENTORY_SHA256", digest)

    result = validate_continuation_artifacts(path)

    assert result["reports"] == 216
    assert result["inventory_sha256"] == digest


@pytest.mark.parametrize("fault", ["missing", "expired", "digest", "inventory"])
def test_continuation_artifact_inventory_rejects_conflicts(monkeypatch, tmp_path, fault):
    artifacts = [
        {"id": index + 1, "name": f"mutation-preflight-wave-3-37550308775-1-{index}",
         "size_in_bytes": 1, "digest": f"sha256:{index:064x}", "expired": False}
        for index in WAVES["wave-3"]
    ]
    if fault == "missing":
        artifacts.pop()
    elif fault == "expired":
        artifacts[0]["expired"] = True
    elif fault == "digest":
        artifacts[0]["digest"] = "unknown"
    path = tmp_path / "artifacts.json"
    path.write_text(json.dumps([{"artifacts": artifacts}]))
    monkeypatch.setattr(
        "scripts.staged_preflight.CONTINUATION_ARTIFACT_INVENTORY_SHA256", "0" * 64,
    )

    with pytest.raises(ValueError):
        validate_continuation_artifacts(path)


def test_combined_accounting_rejects_recovery_attempt_two(tmp_path):
    prior = _jobs_file(
        tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "prior.json",
    )
    current = _jobs_file(
        tmp_path,
        [{"total_count": 1, "jobs": [_job(2, run_id=38, run_attempt=2)]}],
        "current.json",
    )

    with pytest.raises(ValueError, match="origin"):
        combine_accounting(
            prior, current, expected_prior_run_id="37", expected_current_run_id="38",
            expected_prior_run_attempt="1", expected_current_run_attempt="1",
        )


def test_recovery_plan_reuses_only_exact_compatible_wave_one(monkeypatch, tmp_path):
    root, manifests_dir, reports, manifests, _, _ = _fixture(monkeypatch, tmp_path)
    source_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF,
        "run_id": SOURCE_RUN_ID, "run_attempt": "1",
    }
    source_plan = build_plan(root, manifests_dir, SOURCE_ORCHESTRATION_SHA, source_identity)
    source_plan_path = tmp_path / "source-plan.json"
    source_plan_path.write_text(json.dumps(source_plan))
    _write_wave(reports, manifests)
    monkeypatch.setattr("scripts.staged_preflight.SOURCE_PLAN_SHA256", _file_sha(source_plan_path))
    monkeypatch.setattr(
        "scripts.staged_preflight.SOURCE_REPORT_SHA256",
        {
            index: _file_sha(reports / str(index) / "mutation-preflight.json")
            for index in WAVES["wave-1"]
        },
    )
    recovery_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": "owner/repo/.github/workflows/mutation.yml@refs/heads/recovery",
        "run_id": "38", "run_attempt": "1",
    }

    result = build_recovery_plan(
        root, source_plan_path, manifests_dir, reports, "b" * 40, recovery_identity,
    )

    assert result["source"]["run_id"] == SOURCE_RUN_ID
    assert set(result["execution_waves"]) == {"wave-2", "wave-3"}
    assert result["origin_assignment"]["8"]["run_id"] == SOURCE_RUN_ID
    assert result["origin_assignment"]["0"]["run_id"] == "38"


def test_continuation_plan_revalidates_both_runs_and_schedules_only_wave_three(
    monkeypatch, tmp_path,
):
    root, manifests_dir, source_reports, manifests, _, _ = _fixture(monkeypatch, tmp_path)
    source_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF, "run_id": SOURCE_RUN_ID, "run_attempt": "1",
    }
    source_plan = build_plan(root, manifests_dir, SOURCE_ORCHESTRATION_SHA, source_identity)
    source_plan_path = tmp_path / "source-plan.json"
    source_plan_path.write_text(json.dumps(source_plan))
    _write_wave(source_reports, manifests, "wave-1")
    monkeypatch.setattr("scripts.staged_preflight.SOURCE_PLAN_SHA256", _file_sha(source_plan_path))
    monkeypatch.setattr(
        "scripts.staged_preflight.SOURCE_REPORT_SHA256",
        {index: _file_sha(source_reports / str(index) / "mutation-preflight.json")
         for index in WAVES["wave-1"]},
    )
    recovery_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF, "run_id": RECOVERY_RUN_ID, "run_attempt": "1",
    }
    recovery_plan = build_recovery_plan(
        root, source_plan_path, manifests_dir, source_reports,
        RECOVERY_ORCHESTRATION_SHA, recovery_identity,
    )
    recovery_plan_path = tmp_path / "recovery-plan.json"
    recovery_plan_path.write_text(json.dumps(recovery_plan))
    recovery_reports = tmp_path / "recovery-reports"
    recovery_reports.mkdir()
    _write_wave(recovery_reports, manifests, "wave-2")
    recovery_validation = validate_wave(
        root, recovery_plan_path, manifests_dir, recovery_reports, "wave-2",
        RECOVERY_ORCHESTRATION_SHA, recovery_identity,
    )
    recovery_validation_path = tmp_path / "recovery-validation.json"
    recovery_validation_path.write_text(json.dumps(recovery_validation))
    monkeypatch.setattr("scripts.staged_preflight.RECOVERY_PLAN_SHA256", _file_sha(recovery_plan_path))
    monkeypatch.setattr(
        "scripts.staged_preflight.RECOVERY_VALIDATION_SHA256",
        _file_sha(recovery_validation_path),
    )
    monkeypatch.setattr(
        "scripts.staged_preflight.RECOVERY_REPORT_SHA256",
        {index: _file_sha(recovery_reports / str(index) / "mutation-preflight.json")
         for index in WAVES["wave-2"]},
    )
    continuation_identity = {
        "repository": "owner/repo", "workflow": "Staged preflight continuation",
        "workflow_ref": "owner/repo/.github/workflows/staged-preflight-continuation.yml@refs/heads/test",
        "run_id": "39", "run_attempt": "1",
    }

    result = build_continuation_plan(
        root, source_plan_path, source_reports, recovery_plan_path, recovery_reports,
        recovery_validation_path, manifests_dir, "c" * 40, continuation_identity,
    )

    assert result["execution_wave"]["shards"] == WAVES["wave-3"]
    assert result["topology"]["expanded_jobs"] == 229
    assert result["origin_assignment"]["8"]["run_id"] == SOURCE_RUN_ID
    assert result["origin_assignment"]["0"]["run_id"] == RECOVERY_RUN_ID
    assert result["origin_assignment"]["35"]["run_id"] == "39"


def test_fresh_continuation_uses_validated_immutable_candidate_inputs(monkeypatch, tmp_path):
    root, manifests_dir, wave_1_reports, manifests, _, source_plan_path = _fixture(
        monkeypatch, tmp_path,
    )
    source_plan = json.loads(source_plan_path.read_text())
    source_plan["workflow"]["run_id"] = "37"
    source_plan["workflow"]["workflow_ref"] = SOURCE_WORKFLOW_REF
    source_plan_path.write_text(json.dumps(source_plan))
    _write_wave(wave_1_reports, manifests, "wave-1")
    wave_2_reports = tmp_path / "wave-2-reports"
    wave_2_reports.mkdir()
    _write_wave(wave_2_reports, manifests, "wave-2")
    source_identity = source_plan["workflow"]
    validations = []
    for wave, reports in (("wave-1", wave_1_reports), ("wave-2", wave_2_reports)):
        validation = validate_wave(
            root, source_plan_path, manifests_dir, reports, wave, "a" * 40, source_identity,
        )
        path = tmp_path / f"{wave}-validation.json"
        path.write_text(json.dumps(validation))
        validations.append(path)
    continuation_identity = {
        "repository": "owner/repo", "workflow": "Staged preflight continuation",
        "workflow_ref": "owner/repo/.github/workflows/staged-preflight-continuation.yml@refs/heads/test",
        "run_id": "38", "run_attempt": "1",
    }

    result = build_fresh_continuation_plan(
        root, source_plan_path, wave_1_reports, wave_2_reports,
        validations[0], validations[1], manifests_dir, _file_sha(source_plan_path),
        "37", "a" * 40, SOURCE_WORKFLOW_REF, FROZEN_CANDIDATE,
        continuation_identity, FROZEN_CANDIDATE,
    )

    assert result["candidate_sha"] == FROZEN_CANDIDATE
    assert result["execution_wave"]["shards"] == WAVES["wave-3"]
    assert result["source"]["validations"]["wave-2"]["passed"] is True
    assert result["origin_assignment"]["0"]["run_id"] == "37"
    assert result["origin_assignment"]["35"]["run_id"] == "38"


def test_fresh_continuation_rejects_changed_candidate_or_plan_digest(monkeypatch, tmp_path):
    root, manifests_dir, reports, _manifests, _, source_plan_path = _fixture(monkeypatch, tmp_path)
    validation = tmp_path / "validation.json"
    validation.write_text("{}")
    identity = {
        "repository": "owner/repo", "workflow": "Staged preflight continuation",
        "workflow_ref": "ref", "run_id": "38", "run_attempt": "1",
    }

    with pytest.raises(ValueError):
        build_fresh_continuation_plan(
            root, source_plan_path, reports, reports, validation, validation,
            manifests_dir, "0" * 64, "37", "a" * 40, SOURCE_WORKFLOW_REF,
            "b" * 40, identity, "f" * 40,
        )


def test_fresh_completion_record_reconciles_exact_once_corpus(monkeypatch, tmp_path):
    root, manifests_dir, reports, manifests, identity, _ = _fixture(monkeypatch, tmp_path)
    identity["run_id"] = "38"
    plan = build_plan(root, manifests_dir, "b" * 40, identity)
    plan.update({
        "mode": "fresh-staged-preflight-continuation",
        "source": {"run_id": "37", "run_attempt": "1"},
        "origin_assignment": {
            str(index): {"run_id": "37" if index not in WAVES["wave-3"] else "38",
                         "run_attempt": "1", "wave": next(name for name, shards in WAVES.items() if index in shards)}
            for index in range(256)
        },
    })
    for wave in WAVES:
        _write_wave(reports, manifests, wave)
    plan_path = tmp_path / "fresh-plan.json"
    plan_path.write_text(json.dumps(plan))
    aggregate_path = tmp_path / "aggregate.json"
    aggregate_path.write_text(json.dumps({
        "status": "completed", "passed": True, "revision": FROZEN_CANDIDATE,
        "shard_count": 256, "manifest_digests": plan["manifest_digests"],
        "generated": 256, "canonicalized": 256, "collisions": 0,
    }))

    result = build_fresh_completion_record(plan_path, reports, aggregate_path)

    assert result["kind"] == "fresh_staged_preflight"
    assert len(result["origins"]) == 256


def _file_sha(path):
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("fault", ["plan", "report", "runtime", "policy", "topology"])
def test_recovery_plan_rejects_incompatible_or_modified_source(monkeypatch, tmp_path, fault):
    root, manifests_dir, reports, manifests, _, _ = _fixture(monkeypatch, tmp_path)
    source_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF,
        "run_id": SOURCE_RUN_ID, "run_attempt": "1",
    }
    source_plan = build_plan(root, manifests_dir, SOURCE_ORCHESTRATION_SHA, source_identity)
    if fault == "runtime":
        source_plan["runtime"]["python"] = "0.0"
    elif fault == "policy":
        source_plan["policy"]["fettle_toml_sha256"] = "0" * 64
    elif fault == "topology":
        source_plan["manifest_digests"][0] = "f" * 64
    source_plan_path = tmp_path / "source-plan.json"
    source_plan_path.write_text(json.dumps(source_plan))
    _write_wave(reports, manifests)
    monkeypatch.setattr("scripts.staged_preflight.SOURCE_PLAN_SHA256", _file_sha(source_plan_path))
    monkeypatch.setattr(
        "scripts.staged_preflight.SOURCE_REPORT_SHA256",
        {index: _file_sha(reports / str(index) / "mutation-preflight.json") for index in WAVES["wave-1"]},
    )
    if fault == "plan":
        monkeypatch.setattr("scripts.staged_preflight.SOURCE_PLAN_SHA256", "0" * 64)
    elif fault == "report":
        expected = dict(SOURCE_REPORT_SHA256)
        expected[WAVES["wave-1"][0]] = "0" * 64
        monkeypatch.setattr("scripts.staged_preflight.SOURCE_REPORT_SHA256", expected)
    recovery_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": "owner/repo/.github/workflows/mutation.yml@refs/heads/recovery",
        "run_id": "38", "run_attempt": "1",
    }

    with pytest.raises(ValueError):
        build_recovery_plan(
            root, source_plan_path, manifests_dir, reports, "b" * 40, recovery_identity,
        )
