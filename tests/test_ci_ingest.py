"""Tests for scripts/ci_ingest.py — WP-90: CI failure ingestion."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.ci_ingest import (
    classify_failure,
    FailureClass,
    CIFailure,
    store_failure,
    load_history,
)


def test_classifies_pytest_failure():
    log = "FAILED tests/test_app.py::test_login - AssertionError: assert 200 == 401"
    cls = classify_failure(log)
    assert cls == FailureClass.TEST


def test_classifies_lint_failure():
    log = "src/app.py:10:1: F401 'os' imported but unused\nFound 3 errors."
    cls = classify_failure(log)
    assert cls == FailureClass.LINT


def test_classifies_type_error():
    log = 'src/app.py:15: error: Argument 1 to "func" has incompatible type "str"; expected "int"'
    cls = classify_failure(log)
    assert cls == FailureClass.TYPE


def test_classifies_install_failure():
    log = "ERROR: Could not find a version that satisfies the requirement nonexistent-pkg"
    cls = classify_failure(log)
    assert cls == FailureClass.DEPENDENCY


def test_classifies_env_specific():
    log = "Permission denied: /opt/runner/setup.sh"
    cls = classify_failure(log)
    assert cls == FailureClass.ENVIRONMENT


def test_classifies_flaky_test():
    log = "FAILED tests/test_flaky.py::test_timing - TimeoutError\nRERUN tests/test_flaky.py::test_timing PASSED"
    cls = classify_failure(log)
    assert cls == FailureClass.FLAKY


def test_stores_to_history(tmp_path):
    history_path = tmp_path / "ci-history.jsonl"
    failure = CIFailure(
        run_id="12345",
        classification=FailureClass.TEST,
        summary="test_login failed",
        commit="abc123",
    )
    store_failure(str(history_path), failure)
    assert history_path.exists()
    data = json.loads(history_path.read_text().strip())
    assert data["run_id"] == "12345"
    assert data["classification"] == "test"


def test_deduplicates_repeated_failures(tmp_path):
    history_path = tmp_path / "ci-history.jsonl"
    failure = CIFailure(run_id="12345", classification=FailureClass.TEST, summary="fail", commit="abc")
    store_failure(str(history_path), failure)
    store_failure(str(history_path), failure)
    lines = history_path.read_text().strip().splitlines()
    assert len(lines) == 1


def test_handles_missing_history(tmp_path):
    history = load_history(str(tmp_path / "nonexistent.jsonl"))
    assert history == []


def test_redacts_secrets_from_logs():
    log = "Error: token ghp_abc123def456ghi789jkl012mno345pqr expired"
    failure = CIFailure(run_id="1", classification=FailureClass.ENVIRONMENT, summary=log, commit="x")
    assert "ghp_" not in failure.redacted_summary
