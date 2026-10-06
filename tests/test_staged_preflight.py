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
    WAVES,
    build_plan,
    observed_runner_minutes,
    validate_wave,
)


def test_fixed_waves_cover_every_shard_once_and_reconcile_budget():
    members = [index for shards in WAVES.values() for index in shards]

    assert [len(WAVES[name]) for name in ("wave-1", "wave-2", "wave-3")] == [8, 32, 216]
    assert 27 in WAVES["wave-1"]
    assert len(members) == len(set(members)) == 256
    assert sorted(members) == list(range(256))
    assert sum(BUDGET["wave_allowances"].values()) + BUDGET["orchestration_and_aggregation"] + BUDGET["cancellation_headroom"] == 740
    assert BUDGET["launch_ceiling"] == {
        "wave-2": 20,
        "wave-3": 95,
        "aggregate": 595,
        "complete": 640,
    }
    assert ARTIFACT_RETENTION_DAYS == 90


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
    path.write_text(json.dumps([{"jobs": [
        {"started_at": "2026-10-06T01:00:00Z", "completed_at": "2026-10-06T01:02:30Z"},
        {"started_at": "2026-10-06T01:00:00Z", "completed_at": None},
        {"started_at": None, "completed_at": None, "status": "completed", "conclusion": "skipped"},
    ]}]))

    now = datetime(2026, 10, 6, 1, 3, tzinfo=UTC)

    assert observed_runner_minutes(path, now) == 5.5
