"""Tests for scripts/ci_ingest.py — WP-90: CI failure ingestion."""

import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.ci_ingest import (
    classify_failure,
    FailureClass,
    CIFailure,
    store_failure,
    load_history,
    classify_mutation_advisory_corpus,
)


FIXTURES = Path(__file__).parent / "fixtures"


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


def test_mutation_advisory_ground_truth_corpus_is_deterministic():
    corpus = FIXTURES / "mutation-advisory-run-42991579234" / "corpus.json"

    first = classify_mutation_advisory_corpus(corpus)
    second = classify_mutation_advisory_corpus(corpus)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    counts = Counter(result["class"] for result in first["jobs"])
    assert counts == {
        "INFRA_UPLOAD": 8,
        "INFRA_DOWNLOAD": 10,
        "INFRA_LOST_RUNNER": 2,
        "ENGINE_TIMEOUT": 1,
    }
    assert first["passed"] is True
    assert first["rerun_eligible"] is True
    assert first["needs_diagnosis"] == [181]
    assert first["completed_failures"] == []
    assert first["malformed_reports"] == []
    assert all(result["evidence"]["path"] for result in first["jobs"])
    assert all(result["evidence"]["line"] >= 1 for result in first["jobs"])
    assert all(set(result["fetch_outcomes"]) == {
        "metadata", "log", "annotations", "shard_report",
    } for result in first["jobs"])
    assert all(result["malformed_sources"] == [] for result in first["jobs"])
    by_shard = {result["shard"]: result["class"] for result in first["jobs"]}
    assert by_shard == {
        158: "INFRA_LOST_RUNNER",
        169: "INFRA_UPLOAD",
        172: "INFRA_UPLOAD",
        173: "INFRA_UPLOAD",
        175: "INFRA_UPLOAD",
        177: "INFRA_UPLOAD",
        178: "INFRA_UPLOAD",
        180: "INFRA_UPLOAD",
        181: "ENGINE_TIMEOUT",
        183: "INFRA_UPLOAD",
        189: "INFRA_DOWNLOAD",
        190: "INFRA_DOWNLOAD",
        191: "INFRA_DOWNLOAD",
        194: "INFRA_DOWNLOAD",
        195: "INFRA_DOWNLOAD",
        196: "INFRA_DOWNLOAD",
        197: "INFRA_DOWNLOAD",
        201: "INFRA_DOWNLOAD",
        202: "INFRA_DOWNLOAD",
        203: "INFRA_DOWNLOAD",
        205: "INFRA_LOST_RUNNER",
    }


def test_mutation_advisory_matches_operation_family_without_enumerating_operation():
    corpus = FIXTURES / "mutation-advisory-run-42991579234" / "corpus.json"

    result = classify_mutation_advisory_corpus(corpus)

    by_shard = {job["shard"]: job for job in result["jobs"]}
    assert by_shard[194]["class"] == "INFRA_DOWNLOAD"
    assert "Failed to ListArtifacts:" in by_shard[194]["evidence"]["matched_line"]
    assert by_shard[194]["failing_step"].startswith("Run actions/download-artifact@")
    assert by_shard[158]["failing_step"] is None
    assert by_shard[158]["mutation_executed"] is None
    assert by_shard[205]["mutation_executed"] is False


def test_mutation_step_failure_with_valid_report_is_never_infra():
    corpus = FIXTURES / "mutation-advisory-negative-cases" / "corpus.json"

    result = classify_mutation_advisory_corpus(corpus)

    by_shard = {job["shard"]: job for job in result["jobs"]}
    assert by_shard["mutation-artifact-string"]["class"] == "UNKNOWN"
    assert by_shard["survivors"]["class"] == "UNKNOWN"
    assert result["passed"] is False
    assert result["rerun_eligible"] is False
    assert result["needs_diagnosis"] == []
    assert result["completed_failures"] == [
        "mutation-artifact-string", "survivors",
    ]


def test_structural_verdict_is_independent_of_failure_log_text(tmp_path):
    (tmp_path / "job.json").write_text(json.dumps({
        "conclusion": "failure",
        "steps": [{
            "name": "Execute one manifest-bound advisory attempt",
            "conclusion": "failure",
        }],
    }))
    (tmp_path / "log.txt").write_text("Mutation score below threshold\n")
    (tmp_path / "report.json").write_text(json.dumps({
        "status": "tool_error",
        "passed": False,
        "message": "opaque engine interruption",
    }))
    (tmp_path / "corpus.json").write_text(json.dumps({
        "jobs": [{
            "shard": 7,
            "job_id": 7,
            "sources": {
                "metadata": {"outcome": "success", "http_status": 200, "path": "job.json"},
                "log": {"outcome": "success", "http_status": 200, "path": "log.txt"},
                "annotations": {"outcome": "not_provided", "http_status": None, "path": None},
                "shard_report": {"outcome": "success", "http_status": 200, "path": "report.json"},
            },
        }],
    }))

    result = classify_mutation_advisory_corpus(tmp_path / "corpus.json")

    assert result["jobs"][0]["class"] == "UNKNOWN"
    assert result["rerun_eligible"] is True
    assert result["needs_diagnosis"] == [7]
    assert result["completed_failures"] == []


def test_mutation_advisory_uses_each_available_evidence_source():
    corpus = FIXTURES / "mutation-advisory-negative-cases" / "corpus.json"

    result = classify_mutation_advisory_corpus(corpus)

    by_shard = {job["shard"]: job for job in result["jobs"]}
    assert by_shard["log-only"]["class"] == "INFRA_DOWNLOAD"
    assert by_shard["log-only"]["evidence"]["source"] == "log"
    assert by_shard["log-only"]["fetch_outcomes"]["annotations"]["http_status"] == 404
    assert by_shard["annotations-only"]["class"] == "INFRA_DOWNLOAD"
    assert by_shard["annotations-only"]["evidence"]["source"] == "annotations"
    assert by_shard["annotations-only"]["fetch_outcomes"]["log"]["http_status"] == 404


def test_mutation_timeout_report_does_not_override_non_mutation_step(tmp_path):
    (tmp_path / "job.json").write_text(json.dumps({
        "conclusion": "failure",
        "steps": [{"name": "Retain shard report", "conclusion": "failure"}],
    }))
    (tmp_path / "report.json").write_text(json.dumps({
        "status": "tool_error", "message": "Mutation run timed out after 30s",
        "passed": False,
    }))
    (tmp_path / "corpus.json").write_text(json.dumps({
        "jobs": [{
            "shard": 1,
            "job_id": 1,
            "sources": {
                "metadata": {"outcome": "success", "http_status": 200, "path": "job.json"},
                "log": {"outcome": "http_error", "http_status": 404, "path": None},
                "annotations": {"outcome": "http_error", "http_status": 404, "path": None},
                "shard_report": {"outcome": "success", "http_status": 200, "path": "report.json"},
            },
        }],
    }))

    result = classify_mutation_advisory_corpus(tmp_path / "corpus.json")

    assert result["jobs"][0]["class"] == "UNKNOWN"
    assert result["passed"] is False


def test_malformed_mutation_report_does_not_suppress_unknown(tmp_path):
    (tmp_path / "job.json").write_text(json.dumps({
        "conclusion": "failure",
        "steps": [{
            "name": "Execute one manifest-bound advisory attempt",
            "conclusion": "failure",
        }],
    }))
    (tmp_path / "report.json").write_text(json.dumps({
        "status": "tool_error", "message": "Mutation run timed out after 30s",
    }))
    (tmp_path / "corpus.json").write_text(json.dumps({
        "jobs": [{
            "shard": 1,
            "job_id": 1,
            "sources": {
                "metadata": {"outcome": "success", "http_status": 200, "path": "job.json"},
                "log": {"outcome": "not_provided", "http_status": None, "path": None},
                "annotations": {"outcome": "not_provided", "http_status": None, "path": None},
                "shard_report": {"outcome": "success", "http_status": 200, "path": "report.json"},
            },
        }],
    }))

    result = classify_mutation_advisory_corpus(tmp_path / "corpus.json")

    assert result["jobs"][0]["class"] == "UNKNOWN"
    assert result["jobs"][0]["malformed_sources"] == []
    assert result["passed"] is False
    assert result["rerun_eligible"] is False
    assert result["malformed_reports"] == [1]


def test_malformed_successful_source_forces_unknown(tmp_path):
    (tmp_path / "job.json").write_text(json.dumps({
        "conclusion": "failure",
        "steps": [{"name": "Retain shard report", "conclusion": "failure"}],
    }))
    (tmp_path / "log.txt").write_text(
        "Failed to CreateArtifact: Received non-retryable error: unavailable\n"
    )
    (tmp_path / "annotations.json").write_text("{not-json\n")
    (tmp_path / "corpus.json").write_text(json.dumps({
        "jobs": [{
            "shard": 1,
            "job_id": 1,
            "sources": {
                "metadata": {"outcome": "success", "http_status": 200, "path": "job.json"},
                "log": {"outcome": "success", "http_status": 200, "path": "log.txt"},
                "annotations": {"outcome": "success", "http_status": 200, "path": "annotations.json"},
                "shard_report": {"outcome": "not_provided", "http_status": None, "path": None},
            },
        }],
    }))

    result = classify_mutation_advisory_corpus(tmp_path / "corpus.json")

    assert result["jobs"][0]["class"] == "UNKNOWN"
    assert result["jobs"][0]["malformed_sources"] == ["annotations"]
    assert result["passed"] is False


def test_all_null_steps_without_log_is_lost_runner(tmp_path):
    (tmp_path / "job.json").write_text(json.dumps({
        "conclusion": "failure",
        "steps": [{"name": "Set up job", "conclusion": None}],
    }, indent=2))
    (tmp_path / "corpus.json").write_text(json.dumps({
        "jobs": [{
            "shard": 1,
            "job_id": 1,
            "sources": {
                "metadata": {"outcome": "success", "http_status": 200, "path": "job.json"},
                "log": {"outcome": "http_error", "http_status": 404, "path": None},
                "annotations": {"outcome": "http_error", "http_status": 404, "path": None},
                "shard_report": {"outcome": "not_provided", "http_status": None, "path": None},
            },
        }],
    }))

    result = classify_mutation_advisory_corpus(tmp_path / "corpus.json")

    job = result["jobs"][0]
    assert job["class"] == "INFRA_LOST_RUNNER"
    assert job["evidence"]["source"] == "metadata"
    assert job["evidence"]["line"] == 6


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
