"""P34 mutation evidence integrity contracts."""

import json
from pathlib import Path
import subprocess
import sqlite3
from unittest.mock import patch

import pytest

from fettle.mutation_test import (
    _shard_files,
    _shard_ranges,
    _patch_for_ranges,
    _mapped_tests,
    aggregate_shards,
    _get_all_py_files,
    _get_changed_py_files,
    _parse_result_ids,
    _collect_range_results,
    _canonical_mutant,
    _collect_mutant_records,
    _parse_show_all,
    _validate_report_schema,
    _rerun_mutant,
    _run_mutmut,
    _run_shard_modules,
    evaluate_stability,
    evaluate_policy,
    compute_score,
    format_report,
    main,
    run_mutation_test,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mutation"


def _proc(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


def test_score_counts_every_non_skipped_outcome_and_rejects_zero():
    assert compute_score(6, 1, 1, 1, 1) == pytest.approx(85.7142857)
    assert compute_score(0, 0, 0, 0, 0) is None


@pytest.mark.parametrize(
    "mode,budget,count,passed,reason",
    [
        ("advisory", None, 1, True, "uncalibrated"),
        ("enforce", 0, 0, True, None),
        ("enforce", 2, 2, True, None),
        ("enforce", 2, 3, False, "timeout budget exceeded"),
    ],
)
def test_policy_timeout_budget_boundaries(mode, budget, count, passed, reason):
    cfg = {
        "mode": mode, "score_target": 70, "max_untested": 0,
        "max_mutant_timeouts": budget, "max_suspicious_mutants": 0,
    }
    result = evaluate_policy(
        {"killed": 8, "survived": 2, "timeout": count, "suspicious": 0, "untested": 0}, cfg
    )
    assert result["passed"] is passed
    assert (reason is None) == (not result["reasons"])
    if reason:
        assert reason in result["reasons"][0]


@pytest.mark.parametrize(
    "mode,budget,count,passed,reason",
    [
        ("advisory", None, 1, True, "uncalibrated"),
        ("enforce", 0, 0, True, None),
        ("enforce", 2, 2, True, None),
        ("enforce", 2, 3, False, "suspicious budget exceeded"),
    ],
)
def test_policy_suspicious_budget_boundaries(mode, budget, count, passed, reason):
    cfg = {
        "mode": mode, "score_target": 70, "max_untested": 0,
        "max_mutant_timeouts": 0, "max_suspicious_mutants": budget,
    }
    result = evaluate_policy(
        {"killed": 8, "survived": 2, "timeout": 0, "suspicious": count, "untested": 0}, cfg
    )
    assert result["passed"] is passed
    assert (reason is None) == (not result["reasons"])
    if reason:
        assert reason in result["reasons"][0]


def test_policy_suppresses_only_tiny_scope_score_decision():
    result = evaluate_policy(
        {"killed": 1, "survived": 1, "timeout": 0, "suspicious": 0, "untested": 0},
        {
            "mode": "enforce", "score_target": 80, "minimum_scored_mutants": 3,
            "max_untested": 0, "max_mutant_timeouts": 0, "max_suspicious_mutants": 0,
        },
    )

    assert result["score"] == 50.0
    assert result["score_eligible"] is False
    assert result["passed"] is True
    assert "minimum" in result["reasons"][0]


@pytest.mark.parametrize("bad", ["12,45", "mutant-12", "12\n45", "12  45 extra"])
def test_result_id_parser_is_strict(bad):
    with pytest.raises(ValueError):
        _parse_result_ids(bad)
    assert _parse_result_ids("12 45\n") == ["12", "45"]


def test_canonical_identity_ignores_engine_id_and_unrelated_line_movement(tmp_path):
    source = "def eligible_for_discount(total: int) -> bool:\n    return total >= 100\n"
    moved = "def eligible_for_discount(total: int) -> bool:\n    notice = 'unrelated'\n    return total >= 100\n"
    original_path = tmp_path / "original.py"
    moved_path = tmp_path / "moved.py"
    original_path.write_text(source)
    moved_path.write_text(moved)
    diff = json.loads((FIXTURES / "mutmut-show.json").read_text())["records"][0]["diff"]

    first = _canonical_mutant(str(tmp_path), "src/calculator.py", source, diff, "41", "survived", [])
    second = _canonical_mutant(str(tmp_path), "src/calculator.py", moved, diff, "999", "survived", [])

    assert first["fingerprint"] == second["fingerprint"]
    assert first["engine_id"] != second["engine_id"]
    assert first["source_context_digest"] != second["source_context_digest"]
    assert first["line"] == 2
    assert second["line"] == 3


def test_canonical_identity_distinguishes_transformations_on_one_line(tmp_path):
    source = "def eligible_for_discount(total: int) -> bool:\n    return total >= 100\n"
    records = json.loads((FIXTURES / "mutmut-show.json").read_text())["records"]

    mutants = [
        _canonical_mutant(str(tmp_path), "src/calculator.py", source, item["diff"], item["engine_id"], item["state"], [])
        for item in records
    ]

    assert mutants[0]["fingerprint"] != mutants[1]["fingerprint"]
    assert mutants[0]["before"] == "total >= 100"
    assert mutants[0]["after"] == "total > 100"
    assert mutants[1]["after"] == "101"


@pytest.mark.parametrize(
    "diff",
    [
        "",
        "not a diff",
        "--- /tmp/outside.py\n+++ /tmp/outside.py\n@@ -1 +1 @@\n-x\n+y\n",
        "--- src/a.py\n+++ src/b.py\n@@ -1 +1 @@\n-x\n+y\n",
        "--- src/a.py\n+++ src/a.py\n@@ -1 +1 @@\n x\n",
    ],
)
def test_malformed_mutation_details_fail_closed(tmp_path, diff):
    with pytest.raises(ValueError):
        _canonical_mutant(str(tmp_path), "src/a.py", "x\n", diff, "1", "survived", [])


def test_show_all_parser_rejects_duplicate_missing_and_oversized_records():
    diff = "--- src/a.py\n+++ src/a.py\n@@ -1 +1 @@\n-x\n+y\n"
    with pytest.raises(ValueError, match="duplicate"):
        _parse_show_all(f"# mutant 1\n{diff}# mutant 1\n{diff}", {"1"})
    with pytest.raises(ValueError, match="missing"):
        _parse_show_all(f"# mutant 1\n{diff}", {"1", "2"})
    with pytest.raises(ValueError, match="large"):
        _parse_show_all("x" * 100, set(), max_bytes=10)


def test_collect_records_is_complete_and_rejects_fingerprint_collision(tmp_path):
    (tmp_path / "src").mkdir()
    source = "def eligible_for_discount(total: int) -> bool:\n    return total >= 100\n"
    (tmp_path / "src/calculator.py").write_text(source)
    fixtures = json.loads((FIXTURES / "mutmut-show.json").read_text())["records"]
    output = "".join(f"# mutant {item['engine_id']}\n{item['diff']}" for item in fixtures)
    ids = {state: [] for state in ("killed", "survived", "timeout", "suspicious", "untested", "skipped")}
    ids["survived"] = ["41"]
    ids["suspicious"] = ["42"]

    with patch("fettle.mutation_test._run", return_value=_proc(out=output)):
        records, error = _collect_mutant_records(str(tmp_path), ids, ["tests/test_calculator.py"])
    assert error is None
    assert records is not None and [record["engine_id"] for record in records] == ["41", "42"]
    assert all(record["rerun_command"] for record in records)

    with (
        patch("fettle.mutation_test._run", return_value=_proc(out=output)),
        patch("fettle.mutation_test._fingerprint_digest", return_value="same"),
    ):
        records, error = _collect_mutant_records(str(tmp_path), ids, ["tests/test_calculator.py"])
    assert records is None and error["status"] == "unknown"
    assert "fingerprint" in error["message"]


def test_collect_records_includes_skipped_mutants(tmp_path):
    (tmp_path / "src").mkdir()
    source = "def eligible_for_discount(total: int) -> bool:\n    return total >= 100\n"
    (tmp_path / "src/calculator.py").write_text(source)
    fixture = json.loads((FIXTURES / "mutmut-show.json").read_text())["records"][0]
    output = f"# mutant {fixture['engine_id']}\n{fixture['diff']}"
    ids = {state: [] for state in ("killed", "survived", "timeout", "suspicious", "untested", "skipped")}
    ids["skipped"] = [fixture["engine_id"]]

    with patch("fettle.mutation_test._run", return_value=_proc(out=output)):
        records, error = _collect_mutant_records(str(tmp_path), ids, ["tests/test_calculator.py"])

    assert error is None
    assert records is not None and records[0]["state"] == "skipped"


def test_collect_records_rejects_detail_outside_selected_scope(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/calculator.py").write_text(
        "def eligible_for_discount(total: int) -> bool:\n    return total >= 100\n"
    )
    fixture = json.loads((FIXTURES / "mutmut-show.json").read_text())["records"][0]
    output = f"# mutant {fixture['engine_id']}\n{fixture['diff']}"
    ids = {state: [] for state in ("killed", "survived", "timeout", "suspicious", "untested", "skipped")}
    ids["survived"] = [fixture["engine_id"]]

    with patch("fettle.mutation_test._run", return_value=_proc(out=output)):
        records, error = _collect_mutant_records(
            str(tmp_path), ids, ["tests/test_calculator.py"], ["src/other.py"]
        )

    assert records is None and error["status"] == "unknown"
    assert "selected scope" in error["message"]


@pytest.mark.parametrize(
    "source",
    [
        "def eligible_for_discount(total):\n    return total > 100\n",
        "def eligible_for_discount(total):\n    return total >= 100\n    return total >= 100\n",
    ],
)
def test_canonical_identity_rejects_missing_or_ambiguous_source_match(tmp_path, source):
    diff = json.loads((FIXTURES / "mutmut-show.json").read_text())["records"][0]["diff"]

    with pytest.raises(ValueError, match="located uniquely"):
        _canonical_mutant(str(tmp_path), "src/calculator.py", source, diff, "1", "survived", [])


def test_canonical_identity_normalizes_path_and_unicode(tmp_path):
    source = "def café(value):\n    return value == 'é'\n"
    decomposed = "def cafe\u0301(value):\n    return value == 'e\u0301'\n"
    diff = "--- src/café.py\n+++ src/café.py\n@@ -1,2 +1,2 @@\n def café(value):\n-    return value == 'é'\n+    return value != 'é'\n"
    moved_diff = diff.replace("café", "cafe\u0301").replace("é", "e\u0301")

    first = _canonical_mutant(str(tmp_path), "src/café.py", source, diff, "1", "survived", [])
    second = _canonical_mutant(str(tmp_path), "src\\cafe\u0301.py", decomposed, moved_diff, "2", "survived", [])

    assert first["fingerprint"] == second["fingerprint"]
    assert second["file"] == "src/café.py"


def test_schema_v2_requires_complete_unique_non_killed_records():
    report = _stable_report(schema_version="2", non_killed=[])
    report["survived"] = 1

    with pytest.raises(ValueError, match="complete"):
        _validate_report_schema(report)
    with pytest.raises(ValueError, match="schema version 1"):
        _validate_report_schema(_stable_report(schema_version="1"))
    malformed = _stable_report()
    malformed["non_killed"][0] = {**malformed["non_killed"][0], "line": 0}
    with pytest.raises(ValueError, match="malformed"):
        _validate_report_schema(malformed)
    with pytest.raises(ValueError, match="outcome counts"):
        _validate_report_schema(_stable_report(survived="1"))


def test_rerun_mutant_executes_exact_current_engine_id_and_rejects_stale_id():
    record = {"engine_id": "42", "state": "survived"}
    rerun_ids = {state: [] for state in ("killed", "survived", "timeout", "suspicious", "untested", "skipped")}
    rerun_ids["survived"] = ["42"]
    with (
        patch("fettle.mutation_test._run", return_value=_proc(2)) as run,
        patch("fettle.mutation_test._collect_results", return_value=(rerun_ids, None)),
    ):
        result = _rerun_mutant(".", record, {"survived": ["42"]}, 60)
    assert result["status"] == "completed"
    assert result["state"] == "survived"
    assert run.call_args.args[0] == ["mutmut", "run", "42"]

    with patch("fettle.mutation_test._run") as run:
        result = _rerun_mutant(".", record, {"survived": ["99"]}, 60)
    assert result["status"] == "unknown"
    assert result["passed"] is False
    run.assert_not_called()


def test_completed_report_includes_policy_and_scope_identity_digests():
    engine = {
        "status": "completed", "engine_version": "2.5.1", "test_runner": "runner",
        "tests_run": ["tests/test_app.py"], "line_ranges": [], "run_exit_code": 0,
        "results_exit_code": 0, "killed": 8, "survived": 2, "timeout": 0,
        "suspicious": 0, "untested": 0, "skipped": 0, "non_killed": [],
        "survivor_preview": [], "survivors": [], "stderr": "", "duration_ms": 1,
    }
    selection = {"status": "completed", "merge_base": "abc", "files": ["src/app.py"], "deleted": []}
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("fettle.mutation_test._has_mutmut", lambda: True)
        monkeypatch.setattr("fettle.mutation_test._get_changed_py_files", lambda *args: selection)
        monkeypatch.setattr("fettle.mutation_test._mapped_tests", lambda *args: {"src/app.py": ["tests/test_app.py"]})
        monkeypatch.setattr("fettle.mutation_test._run_mutmut", lambda *args, **kwargs: engine)
        monkeypatch.setattr("fettle.mutation_test._run", lambda *args: _proc(out="a" * 40 + "\n"))
        monkeypatch.setattr(Path, "read_bytes", lambda self: b"source")
        monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: "x = 1\n")
        result = run_mutation_test(".", {"paths": ["src/"]})
    assert all(len(result[field]) == 64 for field in (
        "policy_digest", "source_scope_digest", "test_mapping_digest", "line_range_digest"
    ))


def test_human_report_uses_bounded_survivor_preview():
    report = {
        **_stable_report(),
        "threshold": 70,
        "passed": False,
        "survivors": [f"fingerprint-{index}" for index in range(100)],
        "survivor_preview": [{
            "file": "src/a.py", "line": 3, "before": "a == b", "after": "a != b",
            "rerun_command": "mutmut run 9",
        }],
    }

    output = format_report(report)

    assert "src/a.py:3 a == b -> a != b" in output
    assert "fingerprint-99" not in output


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


def test_line_ranges_split_large_files_and_cover_every_line_once(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("\n".join(["x = 1"] * 300))
    (tmp_path / "src/b.py").write_text("\n".join(["y = 1"] * 200))

    shards = [_shard_ranges(str(tmp_path), ["src/a.py", "src/b.py"], index, 2) for index in range(2)]
    covered = [(item["file"], line) for shard in shards for item in shard for line in range(item["start"], item["end"] + 1)]

    assert len(covered) == len(set(covered)) == 500
    assert {file for file, _ in covered} == {"src/a.py", "src/b.py"}


def test_line_ranges_use_smaller_chunks_for_measured_hot_module(tmp_path):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "fettle/quality_scan.py").write_text("\n".join(["x = 1"] * 61))
    (tmp_path / "tests/test_quality_scan.py").write_text("import fettle.quality_scan\n")

    ranges = [item for index in range(4) for item in _shard_ranges(
        str(tmp_path), ["fettle/quality_scan.py"], index, 4,
        chunk_lines={"fettle/quality_scan.py": 20},
    )]

    assert [(item["start"], item["end"]) for item in sorted(ranges, key=lambda item: item["start"])] == [
        (1, 20), (21, 40), (41, 60), (61, 61)
    ]


def test_line_ranges_use_supplied_chunk_configuration(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/slow.py").write_text("\n".join(["x = 1"] * 11))
    (tmp_path / "tests/test_slow.py").write_text("import src.slow\n")

    ranges = [item for index in range(3) for item in _shard_ranges(
        str(tmp_path), ["src/slow.py"], index, 3,
        default_chunk_lines=5, chunk_lines={"src/slow.py": 4},
    )]

    assert [(item["start"], item["end"]) for item in sorted(ranges, key=lambda item: item["start"])] == [
        (1, 4), (5, 8), (9, 11)
    ]


def test_patch_for_ranges_marks_only_selected_lines_as_added(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("one\ntwo\nthree\n")

    patch_text = _patch_for_ranges(str(tmp_path), [{"file": "src/a.py", "start": 2, "end": 3}])

    assert patch_text == "--- a/src/a.py\n+++ b/src/a.py\n@@ -2,0 +2,2 @@\n+two\n+three\n"


def test_range_results_exclude_mutants_outside_shard_lines(tmp_path):
    connection = sqlite3.connect(tmp_path / ".mutmut-cache")
    connection.executescript(
        "CREATE TABLE SourceFile (id INTEGER PRIMARY KEY, filename TEXT, hash TEXT);"
        "CREATE TABLE Line (id INTEGER PRIMARY KEY, sourcefile INTEGER, line TEXT, line_number INTEGER);"
        "CREATE TABLE Mutant (id INTEGER PRIMARY KEY, line INTEGER, idx INTEGER, tested_against_hash TEXT, status TEXT);"
        "INSERT INTO SourceFile VALUES (1, 'src/app.py', 'hash');"
        "INSERT INTO Line VALUES (1, 1, 'a', 10), (2, 1, 'b', 11);"
        "INSERT INTO Mutant VALUES (1, 1, 0, 'tests', 'ok_killed'), (2, 2, 0, 'tests', 'untested');"
    )
    connection.commit()
    connection.close()

    ids, error = _collect_range_results(
        str(tmp_path), [{"file": "src/app.py", "start": 10, "end": 10}], "2.5.1", 0
    )

    assert error is None
    assert ids == {"killed": ["1"], "survived": [], "timeout": [], "suspicious": [], "untested": [], "skipped": []}


def test_mapped_tests_combines_filename_and_direct_imports(tmp_path):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "fettle/widget.py").write_text("")
    (tmp_path / "tests/test_widget.py").write_text("from fettle.widget import run\n")
    (tmp_path / "tests/test_integration.py").write_text("from fettle import widget\n")

    assert _mapped_tests(str(tmp_path), ["fettle/widget.py"]) == {
        "fettle/widget.py": ["tests/test_integration.py", "tests/test_widget.py"]
    }


def test_mapped_tests_leaves_unmapped_modules_visible(tmp_path):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "fettle/orphan.py").write_text("")

    assert _mapped_tests(str(tmp_path), ["fettle/orphan.py"]) == {"fettle/orphan.py": []}


def test_mapped_tests_uses_supplied_project_mapping(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/shared.py").write_text("")
    (tmp_path / "tests/test_behavior.py").write_text("")

    assert _mapped_tests(
        str(tmp_path), ["src/shared.py"],
        {"src/shared.py": ["tests/test_behavior.py"]},
    ) == {"src/shared.py": ["tests/test_behavior.py"]}


def test_every_production_module_has_targeted_tests():
    files = _get_all_py_files(".", ["fettle/"])
    mappings = {
        "fettle/__main__.py": ["tests/test_cli.py"],
        "fettle/agents/claude_code.py": ["tests/test_agents.py"],
        "fettle/agents/codex.py": ["tests/test_agents.py"],
        "fettle/agents/gemini.py": ["tests/test_agents.py"],
        "fettle/agents/opencode.py": ["tests/test_agents.py"],
        "fettle/runners/_subprocess.py": ["tests/test_runners.py"],
        "fettle/uat/__init__.py": ["tests/test_uat_surfaces.py"],
    }

    assert [file for file, tests in _mapped_tests(".", files, mappings).items() if not tests] == []


def test_engine_collects_all_states_and_exit_evidence():
    outputs = ["1 2", "3", "4", "5", "6", "7"]
    calls = [_proc(out="mutmut version 2.5.1\n"), _proc(14), _proc(), *[_proc(out=item) for item in outputs]]
    with (
        patch("fettle.mutation_test._run", side_effect=calls) as run,
        patch("fettle.mutation_test._collect_mutant_records", return_value=(
            [{"fingerprint": "survivor", "state": "survived"}], None,
        )),
        patch("fettle.mutation_test.time.monotonic", side_effect=[10.0, 12.5]),
    ):
        result = _run_mutmut(".", ["src/app.py"], ["tests/test_app.py"], 600)
    assert result["status"] == "completed"
    assert [result[state] for state in ("killed", "survived", "timeout", "suspicious", "untested", "skipped")] == [2, 1, 1, 1, 1, 1]
    assert result["run_exit_code"] == 14
    assert result["survivors"] == ["survivor"]
    assert result["duration_ms"] == 2500
    assert result["test_runner"] == "python -m pytest -x --assert=plain {mapped_tests}"
    assert result["tests_run"] == ["tests/test_app.py"]
    assert result["line_ranges"] == []
    assert run.call_args_list[1].args[0][0:2] == ["mutmut", "run"]


def test_engine_rejects_overlapping_outcome_ids():
    calls = [
        _proc(out="mutmut version 2.5.1\n"), _proc(), _proc(),
        _proc(out="1"), _proc(out="1"), *[_proc() for _ in range(4)],
    ]

    with patch("fettle.mutation_test._run", side_effect=calls):
        result = _run_mutmut(".", ["src/app.py"], ["tests/test_app.py"], 600)

    assert result["status"] == "unknown"
    assert "overlapping" in result["message"]


def test_engine_rejects_empty_tests_without_running_mutmut():
    with patch("fettle.mutation_test._run") as run:
        result = _run_mutmut(".", ["src/app.py"], [], 600)

    assert result["status"] == "unknown"
    run.assert_not_called()


def test_shard_runs_each_module_with_only_its_mapped_tests():
    ranges = [
        {"file": "src/a.py", "start": 1, "end": 10},
        {"file": "src/b.py", "start": 1, "end": 5},
    ]
    engine = {
        "status": "completed", "engine_version": "2.5.1", "test_runner": "runner",
        "run_exit_code": 2, "results_exit_code": 0, "killed": 2, "survived": 1,
        "timeout": 0, "suspicious": 0, "untested": 0, "skipped": 0,
        "survivors": ["3"], "stderr": "", "duration_ms": 10,
    }
    with (
        patch("fettle.mutation_test._run_mutmut", side_effect=[engine, engine]) as run,
        patch("fettle.mutation_test.time.monotonic", side_effect=[10.0, 11.0, 12.0, 13.0]),
    ):
        result = _run_shard_modules(
            ".", {"src/a.py": ["tests/test_a.py"], "src/b.py": ["tests/test_b.py"]}, ranges, 600
        )

    assert run.call_args_list[0].args == (
        ".", ["src/a.py"], ["tests/test_a.py"], 599, [ranges[0]], {"src/a.py": ["tests/test_a.py"]},
    )
    assert run.call_args_list[1].args == (
        ".", ["src/b.py"], ["tests/test_b.py"], 598, [ranges[1]], {"src/b.py": ["tests/test_b.py"]},
    )
    assert result["killed"] == 4
    assert result["survived"] == 2
    assert result["tests_run"] == ["tests/test_a.py", "tests/test_b.py"]


def test_fatal_run_exit_is_bounded_tool_error():
    with patch("fettle.mutation_test.subprocess.run", side_effect=[_proc(out="mutmut version 2.5.1\n"), _proc(1, err="x" * 5000)]):
        result = _run_mutmut(".", ["src/app.py"], ["tests/test_app.py"], 600)
    assert result["status"] == "tool_error"
    assert len(result["stderr"]) == 2000


def test_wrong_version_and_parser_drift_cannot_pass():
    with patch("fettle.mutation_test.subprocess.run", return_value=_proc(out="mutmut version 3.0.0\n")):
        wrong = _run_mutmut(".", ["src/app.py"], ["tests/test_app.py"], 600)
    calls = [_proc(out="mutmut version 2.5.1\n"), _proc(), _proc(), _proc(out="bad")]
    with patch("fettle.mutation_test.subprocess.run", side_effect=calls):
        drift = _run_mutmut(".", ["src/app.py"], ["tests/test_app.py"], 600)
    assert wrong["status"] == "tool_error"
    assert drift["status"] == "unknown"
    assert drift["score"] is None


def test_timeout_is_tool_error():
    with patch("fettle.mutation_test.subprocess.run", side_effect=[_proc(out="mutmut version 2.5.1\n"), subprocess.TimeoutExpired([], 600)]):
        result = _run_mutmut(".", ["src/app.py"], ["tests/test_app.py"], 600)
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


def test_zero_mutant_line_shard_is_completed_for_aggregate_coverage():
    engine = {
        "status": "completed", "engine_version": "2.5.1", "run_exit_code": 0, "results_exit_code": 0,
        "test_runner": "python -m pytest -x --assert=plain {mapped_tests}", "tests_run": ["tests/test_app.py"],
        "line_ranges": [{"file": "src/app.py", "start": 1, "end": 1}],
        "killed": 0, "survived": 0, "timeout": 0, "suspicious": 0, "untested": 0, "skipped": 0,
        "survivors": [], "duration_ms": 1,
    }
    selection = {"status": "completed", "merge_base": None, "files": ["src/app.py"], "deleted": []}
    with (
        patch("fettle.mutation_test._has_mutmut", return_value=True),
        patch("fettle.mutation_test._get_all_py_files", return_value=selection["files"]),
        patch("fettle.mutation_test._shard_ranges", return_value=engine["line_ranges"]),
        patch("fettle.mutation_test._mapped_tests", return_value={"src/app.py": engine["tests_run"]}),
        patch("fettle.mutation_test._run_mutmut", return_value=engine),
        patch("pathlib.Path.read_bytes", return_value=b"source"),
        patch("pathlib.Path.read_text", return_value="x = 1\n"),
    ):
        result = run_mutation_test(".", {"paths": ["src/"], "all": True, "shard_index": 0, "shard_count": 1})

    assert result["status"] == "completed"
    assert result["score"] is None
    assert result["passed"] is True


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


def test_cli_loads_effective_mutation_config_and_allows_flag_overrides(monkeypatch, tmp_path):
    captured = {}
    mutation = {
        "paths": ["configured/"],
        "exclude": ["generated/"],
        "base": "configured-base",
        "timeout_s": 111,
        "full_timeout_s": 222,
        "score_target": 80.0,
        "default_chunk_lines": 12,
        "test_mappings": {"configured/a.py": ["tests/test_a.py"]},
        "chunk_lines": {"configured/a.py": 4},
    }

    def capture(root, cfg):
        captured.update(cfg)
        return {"status": "not_applicable", "score": None, "passed": True}

    monkeypatch.setattr("fettle.config.load_config", lambda root: {"mutation": mutation})
    monkeypatch.setattr("fettle.mutation_test.run_mutation_test", capture)
    monkeypatch.setattr("sys.argv", [
        "mutation_test", "--root", str(tmp_path), "--paths", "override/", "--all", "--json",
    ])

    assert main() == 0
    assert captured["paths"] == ["override/"]
    assert captured["exclude"] == ["generated/"]
    assert captured["timeout_s"] == 222
    assert captured["test_mappings"] == mutation["test_mappings"]
    assert captured["chunk_lines"] == mutation["chunk_lines"]


def _stable_report(**changes):
    report = {
        "schema_version": "2",
        "status": "completed",
        "engine_version": "2.5.1",
        "test_runner": "python -m pytest -x --assert=plain {mapped_tests}",
        "tests_run": ["tests/test_a.py"],
        "line_ranges": [{"file": "fettle/a.py", "start": 1, "end": 1}],
        "revision": "a" * 40,
        "selection": "all",
        "files_tested": ["fettle/a.py"],
        "killed": 8,
        "survived": 1,
        "timeout": 0,
        "suspicious": 0,
        "untested": 1,
        "skipped": 0,
        "score": 88.9,
        "duration_ms": 1000,
        "non_killed": [
            {
                "fingerprint": "a" * 64,
                "engine_id": "9",
                "state": "survived",
                "file": "fettle/a.py",
                "line": 1,
                "operator": "Compare",
                "before": "a == b",
                "after": "a != b",
                "mapped_tests": ["tests/test_a.py"],
                "source_context_digest": "c" * 64,
                "rerun_command": "mutmut run 9",
            },
            {
                "fingerprint": "b" * 64,
                "engine_id": "10",
                "state": "untested",
                "file": "fettle/a.py",
                "line": 1,
                "operator": "Compare",
                "before": "a < b",
                "after": "a <= b",
                "mapped_tests": ["tests/test_a.py"],
                "source_context_digest": "d" * 64,
                "rerun_command": "mutmut run 10",
            },
        ],
    }
    report.update(changes)
    return report


def _shard_report(index, files, **changes):
    report = _stable_report(
        selection="shard",
        shard_index=index,
        shard_count=2,
        files_tested=files,
        tests_run=sorted({f"tests/test_{file.rsplit('/', 1)[-1][:-3]}.py" for file in files}),
        line_ranges=[{"file": file, "start": 1, "end": 1} for file in files],
        duration_ms=1000 + index,
        non_killed=[
            {
                **record,
                "fingerprint": ("c" if record["state"] == "survived" else "d") * 63 + str(index),
                "engine_id": str(int(record["engine_id"]) + index * 10),
                "file": files[0] if files else record["file"],
                "mapped_tests": sorted({f"tests/test_{file.rsplit('/', 1)[-1][:-3]}.py" for file in files}),
            }
            for record in _stable_report()["non_killed"]
        ],
    )
    report.update(changes)
    return report


def test_aggregate_shards_proves_complete_non_overlapping_scope(tmp_path):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "fettle/a.py").write_text("a")
    (tmp_path / "fettle/b.py").write_text("b")
    (tmp_path / "tests/test_a.py").write_text("import fettle.a\n")
    (tmp_path / "tests/test_b.py").write_text("import fettle.b\n")

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
    assert result["score"] == 88.9
    assert result["duration_ms"] == 1001
    assert result["total_duration_ms"] == 2001


def test_aggregate_shards_uses_configured_test_mappings(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/a.py").write_text("a")
    (tmp_path / "src/b.py").write_text("b")
    (tmp_path / "tests/test_behavior.py").write_text("")
    reports = [
        _shard_report(0, ["src/a.py"], tests_run=["tests/test_behavior.py"]),
        _shard_report(1, ["src/b.py"], tests_run=["tests/test_behavior.py"]),
    ]

    with patch("fettle.mutation_test._run", return_value=_proc(out="a" * 40 + "\n")):
        result = aggregate_shards(
            str(tmp_path), reports, ["src/"], [], 2, 70,
            {
                "src/a.py": ["tests/test_behavior.py"],
                "src/b.py": ["tests/test_behavior.py"],
            },
        )

    assert result["status"] == "completed"


@pytest.mark.parametrize(
    "reports,message",
    [
        ([_shard_report(0, ["fettle/a.py"])], "exactly 2"),
        ([_shard_report(0, ["fettle/a.py"]), _shard_report(1, ["fettle/a.py"])], "file scope"),
        ([_shard_report(0, ["fettle/a.py"]), _shard_report(1, [])], "no tested files"),
        ([_shard_report(0, ["fettle/a.py"]), _shard_report(1, ["fettle/b.py"], status="tool_error")], "not completed"),
    ],
)
def test_aggregate_shards_rejects_incomplete_evidence(tmp_path, reports, message):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "fettle/a.py").write_text("a")
    (tmp_path / "fettle/b.py").write_text("b")
    (tmp_path / "tests/test_a.py").write_text("import fettle.a\n")
    (tmp_path / "tests/test_b.py").write_text("import fettle.b\n")

    result = aggregate_shards(str(tmp_path), reports, ["fettle/"], [], 2, 70)

    assert result["status"] in {"unknown", "tool_error"}
    assert message in result["message"]


def test_aggregate_shards_rejects_overlapping_source_ranges(tmp_path):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "fettle/a.py").write_text("a\nb\n")
    (tmp_path / "tests/test_a.py").write_text("import fettle.a\n")
    reports = [_shard_report(0, ["fettle/a.py"]), _shard_report(1, ["fettle/a.py"])]
    reports[0]["line_ranges"] = [{"file": "fettle/a.py", "start": 1, "end": 2}]
    reports[1]["line_ranges"] = [{"file": "fettle/a.py", "start": 2, "end": 2}]

    result = aggregate_shards(str(tmp_path), reports, ["fettle/"], [], 2, 70)

    assert result["status"] == "unknown"
    assert "exactly cover" in result["message"]


def test_aggregate_shards_rejects_wrong_checkout_revision(tmp_path):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "fettle/a.py").write_text("a")
    (tmp_path / "fettle/b.py").write_text("b")
    (tmp_path / "tests/test_a.py").write_text("import fettle.a\n")
    (tmp_path / "tests/test_b.py").write_text("import fettle.b\n")
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
    assert result["baseline"]["score"] == 88.9
    assert result["baseline"]["run_ids"] == ["1", "2", "3"]
    assert result["baseline"]["max_duration_ms"] == 2_100_000


@pytest.mark.parametrize(
    "reports,error",
    [
        ([_stable_report()] * 2, "exactly three"),
        ([_stable_report(), _stable_report(status="tool_error"), _stable_report()], "not completed"),
        ([_stable_report(), _stable_report(killed=7, survived=2, score=77.8, non_killed=[
            {**_stable_report()["non_killed"][0], "fingerprint": "e" * 64},
            _stable_report()["non_killed"][1],
            {**_stable_report()["non_killed"][0], "fingerprint": "f" * 64, "engine_id": "11"},
        ]), _stable_report()], "outcomes differ"),
        ([_stable_report(), _stable_report(revision="b" * 40), _stable_report()], "revisions differ"),
        ([_stable_report(), _stable_report(test_runner="pytest"), _stable_report()], "unsupported test runner"),
        ([_stable_report(), _stable_report(tests_run=["tests/test_b.py"]), _stable_report()], "execution scopes differ"),
        ([_stable_report(), _stable_report(tests_run=[]), _stable_report()], "invalid targeted tests"),
        ([_stable_report(), _stable_report(line_ranges=[{"file": "fettle/a.py", "start": 2, "end": 2}]), _stable_report()], "execution scopes differ"),
        ([_stable_report(), _stable_report(duration_ms=2_100_001), _stable_report()], "runtime bound"),
    ],
)
def test_stability_rejects_incomplete_or_inconsistent_evidence(reports, error):
    result = evaluate_stability(reports, run_ids=["1", "2", "3"])

    assert result["status"] == "unstable"
    assert error in result["errors"][0]
