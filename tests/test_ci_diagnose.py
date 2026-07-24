"""Tests for scripts/ci_diagnose.py — WP-91+92+93: CI diagnosis, learning, history."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.ci_diagnose import (
    diagnose_failure,
    compare_coverage,
    suggest_new_gates,
    ResultHistory,
)
from fettle.ci_ingest import CIFailure, FailureClass


def test_diagnose_explains_test_failure():
    failure = CIFailure(run_id="1", classification=FailureClass.TEST, summary="FAILED tests/test_app.py::test_login", commit="abc")
    diag = diagnose_failure(failure)
    assert "test" in diag.explanation.lower()
    assert diag.reproduction_command


def test_diagnose_suggests_reproduction_command():
    failure = CIFailure(run_id="1", classification=FailureClass.TEST, summary="FAILED tests/test_app.py::test_login", commit="abc")
    diag = diagnose_failure(failure)
    assert "pytest" in diag.reproduction_command or "test" in diag.reproduction_command


def test_compare_shows_uncovered_ci_checks():
    ci_checks = ["lint", "type", "test", "format"]
    local_checks = ["lint", "test"]
    gaps = compare_coverage(ci_checks, local_checks)
    assert "type" in gaps
    assert "format" in gaps


def test_compare_shows_fully_covered():
    ci_checks = ["lint", "test"]
    local_checks = ["lint", "test", "type"]
    gaps = compare_coverage(ci_checks, local_checks)
    assert gaps == []


def test_handles_no_ci_history():
    suggestions = suggest_new_gates([])
    assert suggestions == []


def test_suggests_after_3_repeated_failures():
    failures = [
        CIFailure(run_id="1", classification=FailureClass.TYPE, summary="type error", commit="a"),
        CIFailure(run_id="2", classification=FailureClass.TYPE, summary="type error", commit="b"),
        CIFailure(run_id="3", classification=FailureClass.TYPE, summary="type error", commit="c"),
    ]
    suggestions = suggest_new_gates(failures)
    assert any("type" in s.lower() for s in suggestions)


def test_no_suggestion_below_threshold():
    failures = [
        CIFailure(run_id="1", classification=FailureClass.TYPE, summary="type error", commit="a"),
        CIFailure(run_id="2", classification=FailureClass.TYPE, summary="type error", commit="b"),
    ]
    suggestions = suggest_new_gates(failures)
    assert suggestions == []


def test_result_history_stores_and_retrieves(tmp_path):
    history = ResultHistory(str(tmp_path / "history.jsonl"))
    history.record(tier="fast", findings_count=3, duration_ms=120, commit="abc123")
    history.record(tier="changed", findings_count=0, duration_ms=450, commit="def456")
    entries = history.recent(10)
    assert len(entries) == 2
    assert entries[0]["commit"] == "abc123"


def test_result_history_prunes_old(tmp_path):
    history = ResultHistory(str(tmp_path / "history.jsonl"), max_entries=3)
    for i in range(5):
        history.record(tier="fast", findings_count=i, duration_ms=100, commit=f"commit{i}")
    entries = history.recent(10)
    assert len(entries) == 3


def test_result_history_handles_corrupt_file(tmp_path):
    path = tmp_path / "history.jsonl"
    path.write_text("not json\n{bad\n")
    history = ResultHistory(str(path))
    entries = history.recent(10)
    assert entries == []
