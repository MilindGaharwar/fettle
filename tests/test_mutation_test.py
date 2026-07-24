"""WP-X4 — Mutation Testing Command tests."""

from unittest.mock import patch

from fettle.mutation_test import compute_score, run_mutation_test, _parse_results, format_report


def test_compute_score_all_killed():
    assert compute_score(10, 0) == 100.0


def test_compute_score_mixed():
    assert compute_score(7, 3) == 70.0


def test_compute_score_none():
    assert compute_score(0, 0) == 100.0


def test_parse_results_with_survivors():
    output = "Survived:\n- mutant 1 in app.py\n- mutant 2 in app.py\nKilled:\n- mutant 3\n- mutant 4\n- mutant 5\n"
    result = _parse_results(output)
    assert result["survived"] == 2
    assert len(result["survivors"]) == 2


def test_parse_results_summary_line():
    output = "Summary: 8 killed, 2 survived\n"
    result = _parse_results(output)
    assert result["killed"] == 8
    assert result["survived"] == 2


def test_tool_missing():
    with patch("fettle.mutation_test._has_mutmut", return_value=False):
        report = run_mutation_test(".", {"paths": ["src/"]})
    assert report["status"] == "tool_missing"
    assert "mutmut" in report["message"]


def test_nothing_to_mutate():
    with (patch("fettle.mutation_test._has_mutmut", return_value=True),
          patch("fettle.mutation_test._get_changed_py_files", return_value=[])):
        report = run_mutation_test(".", {"paths": ["src/"]})
    assert report["status"] == "nothing_to_mutate"


def test_completed_below_threshold():
    mock_results = {"status": "completed", "survivors": ["mutant 1"], "killed": 5, "survived": 5}
    with (patch("fettle.mutation_test._has_mutmut", return_value=True),
          patch("fettle.mutation_test._get_changed_py_files", return_value=["src/app.py"]),
          patch("fettle.mutation_test._run_mutmut", return_value=mock_results)):
        report = run_mutation_test(".", {"paths": ["src/"], "threshold": 70, "timeout_s": 60})
    assert report["status"] == "completed"
    assert report["score"] == 50.0
    assert report["passed"] is False


def test_completed_above_threshold():
    mock_results = {"status": "completed", "survivors": [], "killed": 9, "survived": 1}
    with (patch("fettle.mutation_test._has_mutmut", return_value=True),
          patch("fettle.mutation_test._get_changed_py_files", return_value=["src/app.py"]),
          patch("fettle.mutation_test._run_mutmut", return_value=mock_results)):
        report = run_mutation_test(".", {"paths": ["src/"], "threshold": 70, "timeout_s": 60})
    assert report["passed"] is True
    assert report["score"] == 90.0


def test_format_report_completed():
    report = {"status": "completed", "score": 75.0, "killed": 9, "survived": 3,
              "survivors": ["mutant in line 5"], "threshold": 70, "passed": True}
    output = format_report(report)
    assert "75.0%" in output
    assert "PASS" in output
    assert "mutant" in output


def test_format_report_tool_missing():
    report = {"status": "tool_missing", "message": "mutmut not found", "score": None}
    output = format_report(report)
    assert "mutmut not found" in output
