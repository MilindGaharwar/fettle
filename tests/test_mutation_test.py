"""P34 mutation evidence integrity contracts."""

import subprocess
from unittest.mock import patch

import pytest

from fettle.mutation_test import (
    _shard_files,
    aggregate_shards,
    _get_all_py_files,
    _get_changed_py_files,
    _parse_result_ids,
    _run_mutmut,
    evaluate_stability,
    compute_score,
    main,
    run_mutation_test,
)


def _proc(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


def test_score_counts_every_non_skipped_outcome_and_rejects_zero():
    assert compute_score(6, 1, 1, 1, 1) == 60
    assert compute_score(0, 0, 0, 0, 0) is None


@pytest.mark.parametrize("bad", ["12,45", "mutant-12", "12\n45", "12  45 extra"])
def test_result_id_parser_is_strict(bad):
    with pytest.raises(ValueError):
        _parse_result_ids(bad)
    assert _parse_result_ids("12 45\n") == ["12", "45"]


def test_changed_selection_uses_merge_base_and_handles_renames_and_deletes(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/new.py").write_text("")
    diff = "R100\tsrc/old.py\tsrc/new.py\nD\tsrc/gone.py\nM\ttests/test_app.py\n"
    with patch("fettle.mutation_test.subprocess.run", side_effect=[_proc(out="abc\n"), _proc(out=diff)]) as run:
        result = _get_changed_py_files(str(tmp_path), ["src/"], "origin/main")
    assert result["files"] == ["src/new.py"]
    assert result["deleted"] == ["src/gone.py"]
    assert run.call_args_list[0].args[0] == ["git", "merge-base", "origin/main", "HEAD"]


def test_merge_base_failure_is_unknown():
    with patch("fettle.mutation_test.subprocess.run", return_value=_proc(128, err="bad revision")):
        result = _get_changed_py_files(".", ["src/"], "missing")
    assert result["status"] == "unknown"
    assert result["passed"] is False


def test_full_selection_finds_python_only(tmp_path):
    (tmp_path / "src/nested").mkdir(parents=True)
    (tmp_path / "src/app.py").write_text("")
    (tmp_path / "src/nested/no.txt").write_text("")
    assert _get_all_py_files(str(tmp_path), ["src/"]) == ["src/app.py"]


def test_shards_are_deterministic_balanced_and_complete(tmp_path):
    files = ["src/a.py", "src/b.py", "src/c.py"]
    for path, size in zip(files, (100, 60, 20), strict=True):
        target = tmp_path / path
        target.parent.mkdir(exist_ok=True)
        target.write_text("x" * size)

    shards = [_shard_files(str(tmp_path), files, index, 2) for index in range(2)]

    assert shards == [["src/a.py"], ["src/b.py", "src/c.py"]]
    assert sorted(path for shard in shards for path in shard) == files


def test_shards_reject_empty_scope(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        _shard_files(str(tmp_path), [], 0, 1)


def test_engine_collects_all_states_and_exit_evidence():
    outputs = ["1 2", "3", "4", "5", "6", "7"]
    calls = [_proc(out="mutmut version 2.5.1\n"), _proc(14), _proc(), *[_proc(out=item) for item in outputs]]
    with (
        patch("fettle.mutation_test.subprocess.run", side_effect=calls),
        patch("fettle.mutation_test.time.monotonic", side_effect=[10.0, 12.5]),
    ):
        result = _run_mutmut(".", ["src/app.py"], 600)
    assert result["status"] == "completed"
    assert [result[state] for state in ("killed", "survived", "timeout", "suspicious", "untested", "skipped")] == [2, 1, 1, 1, 1, 1]
    assert result["run_exit_code"] == 14
    assert result["survivors"] == ["3"]
    assert result["duration_ms"] == 2500
    assert result["test_runner"] == "python -m pytest -x --assert=plain --testmon"


def test_fatal_run_exit_is_bounded_tool_error():
    with patch("fettle.mutation_test.subprocess.run", side_effect=[_proc(out="mutmut version 2.5.1\n"), _proc(1, err="x" * 5000)]):
        result = _run_mutmut(".", ["src/app.py"], 600)
    assert result["status"] == "tool_error"
    assert len(result["stderr"]) == 2000


def test_wrong_version_and_parser_drift_cannot_pass():
    with patch("fettle.mutation_test.subprocess.run", return_value=_proc(out="mutmut version 3.0.0\n")):
        wrong = _run_mutmut(".", ["src/app.py"], 600)
    calls = [_proc(out="mutmut version 2.5.1\n"), _proc(), _proc(), _proc(out="bad")]
    with patch("fettle.mutation_test.subprocess.run", side_effect=calls):
        drift = _run_mutmut(".", ["src/app.py"], 600)
    assert wrong["status"] == "tool_error"
    assert drift["status"] == "unknown"
    assert drift["score"] is None


def test_timeout_is_tool_error():
    with patch("fettle.mutation_test.subprocess.run", side_effect=[_proc(out="mutmut version 2.5.1\n"), subprocess.TimeoutExpired([], 600)]):
        result = _run_mutmut(".", ["src/app.py"], 600)
    assert result["status"] == "tool_error"


def test_zero_mutants_is_unknown_not_perfect():
    engine = {"status": "completed", "engine_version": "2.5.1", "run_exit_code": 0, "results_exit_code": 0,
              "killed": 0, "survived": 0, "timeout": 0, "suspicious": 0, "untested": 0, "skipped": 0,
              "survivors": []}
    selection = {"status": "completed", "merge_base": "abc", "files": ["src/app.py"], "deleted": []}
    with patch("fettle.mutation_test._has_mutmut", return_value=True), patch("fettle.mutation_test._get_changed_py_files", return_value=selection), patch("fettle.mutation_test._run_mutmut", return_value=engine):
        result = run_mutation_test(".", {"paths": ["src/"]})
    assert result["status"] == "unknown"
    assert result["passed"] is False


def test_no_files_is_distinct_from_missing_tool():
    with patch("fettle.mutation_test._has_mutmut", return_value=False):
        assert run_mutation_test(".", {})["status"] == "tool_error"
    selection = {"status": "completed", "merge_base": "abc", "files": [], "deleted": []}
    with patch("fettle.mutation_test._has_mutmut", return_value=True), patch("fettle.mutation_test._get_changed_py_files", return_value=selection):
        result = run_mutation_test(".", {})
    assert result["status"] == "not_applicable"
    assert result["passed"] is True


@pytest.mark.parametrize("failure", [OSError("git missing"), subprocess.TimeoutExpired([], 10)])
def test_revision_resolution_failure_is_tool_error(failure):
    with (
        patch("fettle.mutation_test._has_mutmut", return_value=True),
        patch("fettle.mutation_test._run", side_effect=failure),
    ):
        result = run_mutation_test(".", {})

    assert result["status"] == "tool_error"
    assert result["passed"] is False


def test_cli_returns_two_for_unknown(monkeypatch):
    monkeypatch.setattr("fettle.mutation_test.run_mutation_test", lambda root, cfg: {"status": "unknown", "score": None, "passed": False})
    monkeypatch.setattr("sys.argv", ["mutation_test", "--json"])
    assert main() == 2


def _stable_report(**changes):
    report = {
        "schema_version": "1",
        "status": "completed",
        "engine_version": "2.5.1",
        "test_runner": "python -m pytest -x --assert=plain --testmon",
        "revision": "a" * 40,
        "selection": "all",
        "files_tested": ["fettle/a.py"],
        "killed": 8,
        "survived": 1,
        "timeout": 0,
        "suspicious": 0,
        "untested": 1,
        "skipped": 0,
        "score": 80.0,
        "duration_ms": 1000,
    }
    report.update(changes)
    return report


def _shard_report(index, files, **changes):
    report = _stable_report(
        selection="shard",
        shard_index=index,
        shard_count=2,
        files_tested=files,
        duration_ms=1000 + index,
    )
    report.update(changes)
    return report


def test_aggregate_shards_proves_complete_non_overlapping_scope(tmp_path):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "fettle/a.py").write_text("a")
    (tmp_path / "fettle/b.py").write_text("b")

    with patch("fettle.mutation_test._run", return_value=_proc(out="a" * 40 + "\n")):
        result = aggregate_shards(
            str(tmp_path),
            [_shard_report(0, ["fettle/a.py"]), _shard_report(1, ["fettle/b.py"])],
            ["fettle/"],
            [],
            2,
            70,
        )

    assert result["status"] == "completed"
    assert result["selection"] == "all"
    assert result["files_tested"] == ["fettle/a.py", "fettle/b.py"]
    assert result["killed"] == 16
    assert result["score"] == 80.0
    assert result["duration_ms"] == 1001
    assert result["total_duration_ms"] == 2001


@pytest.mark.parametrize(
    "reports,message",
    [
        ([_shard_report(0, ["fettle/a.py"])], "exactly 2"),
        ([_shard_report(0, ["fettle/a.py"]), _shard_report(1, ["fettle/a.py"])], "overlap"),
        ([_shard_report(0, ["fettle/a.py"]), _shard_report(1, [])], "no tested files"),
        ([_shard_report(0, ["fettle/a.py"]), _shard_report(1, ["fettle/b.py"], status="tool_error")], "not completed"),
    ],
)
def test_aggregate_shards_rejects_incomplete_evidence(tmp_path, reports, message):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "fettle/a.py").write_text("a")
    (tmp_path / "fettle/b.py").write_text("b")

    result = aggregate_shards(str(tmp_path), reports, ["fettle/"], [], 2, 70)

    assert result["status"] in {"unknown", "tool_error"}
    assert message in result["message"]


def test_aggregate_shards_rejects_wrong_checkout_revision(tmp_path):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "fettle/a.py").write_text("a")
    (tmp_path / "fettle/b.py").write_text("b")
    reports = [_shard_report(0, ["fettle/a.py"]), _shard_report(1, ["fettle/b.py"])]

    with patch("fettle.mutation_test._run", return_value=_proc(out="b" * 40 + "\n")):
        result = aggregate_shards(str(tmp_path), reports, ["fettle/"], [], 2, 70)

    assert result["status"] == "unknown"
    assert "checkout" in result["message"]


def test_stability_requires_three_identical_completed_full_reports():
    result = evaluate_stability(
        [_stable_report(duration_ms=value) for value in (900, 1000, 2_100_000)],
        run_ids=["1", "2", "3"],
    )

    assert result["status"] == "stable"
    assert result["baseline"]["score"] == 80.0
    assert result["baseline"]["run_ids"] == ["1", "2", "3"]
    assert result["baseline"]["max_duration_ms"] == 2_100_000


@pytest.mark.parametrize(
    "reports,error",
    [
        ([_stable_report()] * 2, "exactly three"),
        ([_stable_report(), _stable_report(status="tool_error"), _stable_report()], "not completed"),
        ([_stable_report(), _stable_report(killed=7, survived=2, score=70.0), _stable_report()], "outcomes differ"),
        ([_stable_report(), _stable_report(revision="b" * 40), _stable_report()], "revisions differ"),
        ([_stable_report(), _stable_report(test_runner="pytest"), _stable_report()], "unsupported test runner"),
        ([_stable_report(), _stable_report(duration_ms=2_100_001), _stable_report()], "runtime bound"),
    ],
)
def test_stability_rejects_incomplete_or_inconsistent_evidence(reports, error):
    result = evaluate_stability(reports, run_ids=["1", "2", "3"])

    assert result["status"] == "unstable"
    assert error in result["errors"][0]
