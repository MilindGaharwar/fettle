import json
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
    validate_wave,
    validate_continuation_topology,
    validate_continuation_artifacts,
    validate_manifest_handoff,
    validate_preflight_report_handoff,
)


def test_fixed_waves_cover_every_shard_once_and_reconcile_budget():
    members = [index for shards in WAVES.values() for index in shards]

    assert [len(WAVES[name]) for name in ("wave-1", "wave-2", "wave-3")] == [8, 32, 216]
    assert 27 in WAVES["wave-1"]
    assert len(members) == len(set(members)) == 256
    assert sorted(members) == list(range(256))
    assert sum(BUDGET["wave_allowances"].values()) + BUDGET["orchestration_and_aggregation"] + BUDGET["cancellation_headroom"] == 800
    assert BUDGET["launch_ceiling"] == {
        "wave-2": 20,
        "wave-3": 95,
        "aggregate": 595,
        "complete": 700,
    }
    assert ARTIFACT_RETENTION_DAYS == 90
    assert validate_continuation_topology() == {
        "matrix_jobs": 216, "support_jobs": 8, "expanded_jobs": 224, "platform_limit": 256,
    }


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


@pytest.mark.parametrize("fault", [None, "missing", "duplicate", "misplaced", "tampered"])
def test_manifest_handoff_enforces_exact_artifact_layout(monkeypatch, tmp_path, fault):
    root, manifests, _reports, items, _identity, plan_path = _fixture(monkeypatch, tmp_path)
    def load_exact(_root, directory, candidate_sha=FROZEN_CANDIDATE):
        loaded = [json.loads((directory / f"partition-{index}.json").read_text())
                  for index in range(256)]
        if loaded != items or candidate_sha != FROZEN_CANDIDATE:
            raise ValueError("manifest content differs from expected topology")
        return loaded

    monkeypatch.setattr("scripts.staged_preflight._load_manifests", load_exact)
    artifact_root = tmp_path / "artifact"
    manifest_root = artifact_root / "source-plan/mutation-manifests"
    manifest_root.mkdir(parents=True)
    for index, item in enumerate(items):
        (manifest_root / f"partition-{index}.json").write_text(json.dumps(item))
    if fault == "missing":
        (manifest_root / "partition-0.json").unlink()
    elif fault == "duplicate":
        duplicate = artifact_root / "duplicate"
        duplicate.mkdir()
        (duplicate / "partition-0.json").write_text(json.dumps(items[0]))
    elif fault == "misplaced":
        (artifact_root / "partition-0.json").write_text(
            (manifest_root / "partition-0.json").read_text()
        )
        (manifest_root / "partition-0.json").unlink()
    elif fault == "tampered":
        changed = json.loads((manifest_root / "partition-0.json").read_text())
        changed["ranges"][0]["end"] += 1
        (manifest_root / "partition-0.json").write_text(json.dumps(changed))

    if fault is None:
        result = validate_manifest_handoff(root, artifact_root, plan_path)
        assert result["manifest_root"] == "source-plan/mutation-manifests"
        assert result["manifest_count"] == 256
    else:
        with pytest.raises(ValueError):
            validate_manifest_handoff(root, artifact_root, plan_path)


def test_report_handoff_reads_exact_manifest_and_report(monkeypatch, tmp_path):
    root, _manifests, reports, items, _identity, plan_path = _fixture(monkeypatch, tmp_path)
    plan = json.loads(plan_path.read_text())
    plan["execution_wave"] = {"shards": WAVES["wave-3"], "max_parallel": 8}
    plan_path.write_text(json.dumps(plan))
    artifact_root = tmp_path / "artifact"
    manifest_root = artifact_root / "source-plan/mutation-manifests"
    manifest_root.mkdir(parents=True)
    for index, item in enumerate(items):
        (manifest_root / f"partition-{index}.json").write_text(json.dumps(item))
    monkeypatch.setattr(
        "scripts.staged_preflight._load_manifests", lambda *_args, **_kwargs: items,
    )
    index = WAVES["wave-3"][0]
    fingerprint = f"{index + 1:064x}"
    report_path = reports / "mutation-preflight.json"
    report_path.write_text(json.dumps({
        "status": "completed", "passed": True, "engine_version": "2.5.1",
        "shard_index": index, "shard_count": 256,
        "manifest_digest": items[index]["digest"], "line_ranges": items[index]["ranges"],
        "files": items[index]["files"], "generated": 1, "canonicalized": 1,
        "collisions": 0, "fingerprints": [fingerprint],
        "corpus": [{"fingerprint": fingerprint}],
    }))

    result = validate_preflight_report_handoff(
        root, artifact_root, plan_path, report_path, index,
    )

    assert result["passed"] is True
    assert result["shard_index"] == index

    report_path.write_text("")
    with pytest.raises(json.JSONDecodeError):
        validate_preflight_report_handoff(root, artifact_root, plan_path, report_path, index)


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
        "status": status, "conclusion": conclusion, "started_at": start,
        "completed_at": end, "runner_id": runner_id, "runner_name": "runner" if runner_id else None,
        "runner_group_id": None, "runner_group_name": None,
        "steps": [{"name": "work"}] if steps is None and runner_id else (steps or []),
    }


def _jobs_file(tmp_path, pages, name="jobs.json"):
    path = tmp_path / name
    path.write_text(json.dumps(pages))
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
@pytest.mark.parametrize("status", ["completed", "queued"])
def test_accounting_rejects_nonexecuted_status_with_any_runner_identity(tmp_path, field, status):
    job = _job(
        1,
        status=status,
        conclusion="skipped" if status == "completed" else None,
        end="2026-10-06T01:00:00Z" if status == "completed" else None,
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
    [(20, "wave-2", True), (20.01, "wave-2", False), (95, "wave-3", True),
     (595, "aggregate", True), (700, "complete", True), (700.01, "complete", False)],
)
def test_budget_transition_boundaries(used, next_wave, passed):
    assert (used <= BUDGET["launch_ceiling"][next_wave]) is passed


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
    assert result["topology"]["expanded_jobs"] == 224
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
        "37", "a" * 40, SOURCE_WORKFLOW_REF, "b" * 40,
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
