"""Mutation baseline establishment and changed-scope comparison contracts."""

import json
import threading
from datetime import UTC, datetime
import pytest

from fettle.mutation_baseline import (
    compare_report,
    establish_baseline,
    load_baseline,
    load_classifications,
    save_baseline,
)
from fettle.overrides import OverrideRecord


def _record(fingerprint="a" * 64, engine_id="1", state="survived", file="src/a.py"):
    return {
        "fingerprint": fingerprint, "engine_id": engine_id, "state": state,
        "file": file, "line": 2, "operator": "Compare", "before": "x == 1",
        "after": "x != 1", "mapped_tests": ["tests/test_a.py"],
        "source_context_digest": "1" * 64,
        "rerun_command": f"mutmut run {engine_id}",
    }


def _report(**changes):
    report = {
        "schema_version": "2", "status": "completed", "selection": "all",
        "revision": "a" * 40, "engine_version": "2.5.1",
        "test_runner": "python -m pytest -x --assert=plain {mapped_tests}",
        "files_tested": ["src/a.py"], "tests_run": ["tests/test_a.py"],
        "line_ranges": [{"file": "src/a.py", "start": 1, "end": 3}],
        "policy_digest": "b" * 64, "source_scope_digest": "c" * 64,
        "test_mapping_digest": "d" * 64, "line_range_digest": "e" * 64,
        "killed": 9, "survived": 1, "timeout": 0, "suspicious": 0,
        "untested": 0, "skipped": 0, "score": 90.0, "duration_ms": 100,
        "total_duration_ms": 250,
        "non_killed": [_record()],
    }
    report.update(changes)
    return report


def _override(check_id, fingerprint, **changes):
    fields = {
        "actor": "owner", "reason": "temporary", "timestamp": "2026-08-01T00:00:00Z",
        "expiry": "2026-09-01T00:00:00Z", "check_id": check_id,
        "scope": "src/a.py", "revision": "a" * 40, "policy_digest": "b" * 64,
        "evidence_id": fingerprint, "surface": "ci",
    }
    fields.update(changes)
    return OverrideRecord.create(**fields)


def test_establish_requires_two_matching_complete_reports_and_zero_untested():
    first = _report()
    second = _report(non_killed=[_record(engine_id="99")], duration_ms=120)
    baseline = establish_baseline([first, second], ["run-1", "run-2"], floor=90, target=95)
    assert baseline["survivor_fingerprints"] == ["a" * 64]
    assert baseline["run_ids"] == ["run-1", "run-2"]
    assert baseline["max_duration_ms"] == 120
    assert baseline["max_total_duration_ms"] == 250
    assert baseline["target"] == 95

    with pytest.raises(ValueError, match="exactly two"):
        establish_baseline([first], ["run-1"], floor=90)
    untested = _record("f" * 64, "2", "untested")
    with pytest.raises(ValueError, match="untested"):
        establish_baseline([first, _report(untested=1, non_killed=[_record(), untested])], ["1", "2"], floor=90)
    with pytest.raises(ValueError, match="differ"):
        establish_baseline([first, _report(revision="f" * 40)], ["1", "2"], floor=90)


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"policy_digest": "short"}, "policy_digest"),
        ({"killed": -1}, "counts"),
        ({"score": 91.0}, "score"),
        ({"duration_ms": -1}, "duration"),
    ],
)
def test_establish_rejects_malformed_identity_count_score_and_runtime(changes, message):
    with pytest.raises(ValueError, match=message):
        establish_baseline([_report(**changes), _report(**changes)], ["1", "2"], floor=90)


def test_baseline_load_and_compare_and_swap_never_overwrite_malformed_or_newer(tmp_path):
    path = tmp_path / ".fettle/mutation-baseline.json"
    path.parent.mkdir()
    path.write_text("broken")
    with pytest.raises(ValueError, match="parse"):
        load_baseline(path)
    with pytest.raises(ValueError, match="existing"):
        save_baseline(path, {"schema_version": "1"})
    assert path.read_text() == "broken"

    path.unlink()
    baseline = establish_baseline([_report(), _report()], ["1", "2"], floor=90)
    digest = save_baseline(path, baseline)
    with pytest.raises(ValueError, match="changed"):
        save_baseline(path, baseline, expected_digest="0" * 64)
    assert save_baseline(path, baseline, expected_digest=digest) == digest


def test_baseline_concurrent_compare_and_swap_has_one_winner(tmp_path):
    path = tmp_path / ".fettle/mutation-baseline.json"
    baseline = establish_baseline([_report(), _report()], ["1", "2"], floor=90)
    digest = save_baseline(path, baseline)
    barrier = threading.Barrier(2)
    outcomes = []

    def update(floor):
        candidate = {**baseline, "floor": floor}
        barrier.wait()
        try:
            save_baseline(path, candidate, expected_digest=digest)
        except ValueError:
            outcomes.append("rejected")
        else:
            outcomes.append("saved")

    threads = [threading.Thread(target=update, args=(floor,)) for floor in (91.0, 92.0)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["rejected", "saved"]
    assert load_baseline(path)["floor"] in {91.0, 92.0}


def test_floor_reduction_requires_exact_baseline_override():
    old = establish_baseline([_report(), _report()], ["1", "2"], floor=90)
    reports = [_report(score=80.0, killed=8, survived=2, non_killed=[_record(), _record("f" * 64, "2")])] * 2
    with pytest.raises(ValueError, match="floor"):
        establish_baseline(reports, ["3", "4"], floor=80, previous=old)
    survivor_override = _override("mutation.survivor", "baseline-floor")
    with pytest.raises(ValueError, match="floor"):
        establish_baseline(reports, ["3", "4"], floor=80, previous=old, overrides=[survivor_override])
    baseline_override = _override("mutation.baseline", "baseline-floor")
    result = establish_baseline(reports, ["3", "4"], floor=80, previous=old, overrides=[baseline_override])
    assert result["floor"] == 80


def test_compare_labels_new_existing_resolved_and_waived_without_changing_counts():
    baseline = establish_baseline([_report(), _report()], ["1", "2"], floor=90)
    new = _record("f" * 64, "2")
    current = _report(selection="changed", survived=1, killed=9, non_killed=[new])
    waiver = _override("mutation.survivor", new["fingerprint"])
    result = compare_report(
        current, baseline, overrides=[waiver], now=datetime(2026, 8, 8, tzinfo=UTC)
    )
    assert [item["disposition"] for item in result["records"]] == ["waived"]
    assert result["resolved"] == ["a" * 64]
    assert result["raw_counts"]["survived"] == 1


def test_compare_bounds_actionable_preview_without_truncating_records():
    baseline = establish_baseline([_report(), _report()], ["1", "2"], floor=90)
    records = [
        {**_record(f"{index:064x}", str(index), file="src/a.py"), "line": 2 if index < 3 else index}
        for index in range(1, 11)
    ] + [
        {**_record(f"{index:064x}", str(index), file="src/b.py"), "line": index}
        for index in range(11, 14)
    ]
    current = _report(
        selection="changed", files_tested=["src/a.py", "src/b.py"],
        survived=len(records), killed=0, score=0.0, non_killed=records,
    )

    result = compare_report(current, baseline, max_findings_per_line=1, max_findings_per_file=7)

    assert len(result["records"]) == 13
    assert len(result["finding_preview"]) == 10
    assert sum(item["file"] == "src/a.py" for item in result["finding_preview"]) == 7
    assert sum(item["line"] == 2 for item in result["finding_preview"]) == 1
    assert result["passed"] is False


def test_compare_rejects_partial_unknown_identity_without_a_pass():
    baseline = establish_baseline([_report(), _report()], ["1", "2"], floor=90)
    unknown = _record("f" * 64, "2")
    del unknown["source_context_digest"]

    result = compare_report(
        _report(selection="changed", non_killed=[unknown]), baseline,
        now=datetime(2026, 8, 8, tzinfo=UTC),
    )

    assert result["status"] == "unknown"
    assert result["passed"] is False


@pytest.mark.parametrize(
    "changes",
    [
        {"timestamp": "2026-08-08T00:00:01Z"},
        {"expiry": "2026-08-08T00:00:00Z"},
        {"revision": "c" * 40},
        {"policy_digest": "c" * 64},
        {"evidence_id": "e" * 64},
        {"surface": "local"},
    ],
)
def test_survivor_override_requires_active_exact_context(changes):
    baseline = establish_baseline([_report(), _report()], ["1", "2"], floor=90)
    new = _record("f" * 64, "2")
    override = _override("mutation.survivor", new["fingerprint"], **changes)

    result = compare_report(
        _report(selection="changed", non_killed=[new]), baseline,
        overrides=[override], now=datetime(2026, 8, 8, tzinfo=UTC),
    )

    assert result["records"][0]["disposition"] == "new"


def test_classification_ledger_is_strict_and_stale_context_does_not_suppress(tmp_path):
    path = tmp_path / "classifications.json"
    path.write_text(json.dumps({
        "schema_version": "1",
        "classifications": [{
            "fingerprint": "f" * 64, "classification": "equivalent", "owner": "owner",
            "reason": "same observable value", "expiry": "2026-09-01T00:00:00Z",
            "policy_digest": "b" * 64, "source_context_digest": "1" * 64,
            "evidence": {"type": "behavioral", "steps": "run the case", "expected": "same result"},
        }],
    }))
    records = load_classifications(path)
    current = _report(
        selection="changed", non_killed=[{**_record("f" * 64), "source_context_digest": "2" * 64}]
    )
    baseline = establish_baseline([_report(), _report()], ["1", "2"], floor=90)
    result = compare_report(current, baseline, classifications=records, now=datetime(2026, 8, 8, tzinfo=UTC))
    assert result["records"][0]["disposition"] == "new"

    path.write_text('{"schema_version":"1","classifications":[{"classification":"unknown"}]}')
    with pytest.raises(ValueError):
        load_classifications(path)


@pytest.mark.parametrize(
    "evidence",
    [
        {"type": "behavioral", "steps": "run case", "expected": "same result"},
        {"type": "static", "tool": "proof", "version": "1.0", "result_digest": "2" * 64},
        {"type": "oracle", "target": "tests/oracle.txt", "content_digest": "3" * 64},
    ],
)
def test_classification_evidence_variants_validate_independently(tmp_path, evidence):
    if evidence["type"] == "oracle":
        (tmp_path / "tests").mkdir()
        target = tmp_path / evidence["target"]
        target.write_text("oracle")
        import hashlib
        evidence = {**evidence, "content_digest": hashlib.sha256(b"oracle").hexdigest()}
    path = tmp_path / ".fettle/classifications.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": "1",
        "classifications": [{
            "fingerprint": "f" * 64, "classification": "equivalent", "owner": "owner",
            "reason": "same observable value", "expiry": "2026-09-01T00:00:00Z",
            "policy_digest": "b" * 64, "source_context_digest": "1" * 64,
            "evidence": evidence,
        }],
    }))

    assert load_classifications(path, root=tmp_path)[0]["evidence"] == evidence


@pytest.mark.parametrize(
    "evidence,message",
    [
        ({"type": "behavioral", "steps": "run case"}, "incomplete"),
        ({"type": "static", "tool": "proof", "version": "1.0", "result_digest": "bad"}, "digest"),
        ({"type": "oracle", "target": "../outside", "content_digest": "3" * 64}, "relative"),
        ({"type": "oracle", "target": "tests/missing", "content_digest": "3" * 64}, "target"),
    ],
)
def test_classification_rejects_invalid_or_stale_evidence(tmp_path, evidence, message):
    path = tmp_path / ".fettle/classifications.json"
    path.parent.mkdir()
    path.write_text(json.dumps({
        "schema_version": "1",
        "classifications": [{
            "fingerprint": "f" * 64, "classification": "equivalent", "owner": "owner",
            "reason": "same observable value", "expiry": "2026-09-01T00:00:00Z",
            "policy_digest": "b" * 64, "source_context_digest": "1" * 64,
            "evidence": evidence,
        }],
    }))

    with pytest.raises(ValueError, match=message):
        load_classifications(path, root=tmp_path)
