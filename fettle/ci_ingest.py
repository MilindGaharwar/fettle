"""Fettle v0.5.0 — WP-90: CI failure ingestion.

Read CI failures, classify, store in history.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class FailureClass(StrEnum):
    TEST = "test"
    LINT = "lint"
    TYPE = "type"
    DEPENDENCY = "dependency"
    BUILD = "build"
    ENVIRONMENT = "environment"
    FLAKY = "flaky"
    UNKNOWN = "unknown"


class MutationAdvisoryClass(StrEnum):
    """Fail-closed classes for pull-request mutation-advisory jobs."""

    INFRA_UPLOAD = "INFRA_UPLOAD"
    INFRA_DOWNLOAD = "INFRA_DOWNLOAD"
    INFRA_LOST_RUNNER = "INFRA_LOST_RUNNER"
    ENGINE_TIMEOUT = "ENGINE_TIMEOUT"
    UNKNOWN = "UNKNOWN"


_SECRET_RE = re.compile(r"(ghp_|gho_|ghu_|sk-|AKIA)[a-zA-Z0-9_-]{10,}")

_CLASSIFIERS: list[tuple[FailureClass, re.Pattern]] = [
    (FailureClass.FLAKY, re.compile(r"RERUN.*PASSED|flaky|retry.*pass", re.IGNORECASE)),
    (FailureClass.TEST, re.compile(r"FAILED\s+tests/|AssertionError|pytest|test.*failed", re.IGNORECASE)),
    (FailureClass.LINT, re.compile(r"[A-Z]\d{3}\s|Found \d+ error|ruff|eslint|flake8", re.IGNORECASE)),
    (FailureClass.TYPE, re.compile(r"error:.*incompatible type|type.*error|pyright|mypy", re.IGNORECASE)),
    (FailureClass.DEPENDENCY, re.compile(r"Could not find.*version|ModuleNotFoundError|No matching distribution|dependency.*not found", re.IGNORECASE)),
    (FailureClass.ENVIRONMENT, re.compile(r"ModuleNotFoundError|command not found|No such file|Permission denied", re.IGNORECASE)),
    (FailureClass.BUILD, re.compile(r"build failed|compilation error|cargo.*error|go build.*error", re.IGNORECASE)),
]

_ARTIFACT_SERVICE_ERROR = re.compile(
    r"Failed to [^:\r\n]+:.*(?:Received non-retryable error|"
    r"Failed to make request after \d+ attempts)",
    re.IGNORECASE,
)
_LOST_RUNNER = re.compile(r"lost communication with the server", re.IGNORECASE)
_ENGINE_TIMEOUT = re.compile(r"mutation run timed out after \d+s", re.IGNORECASE)
_MUTATION_STEP = "Execute one manifest-bound advisory attempt"
_SOURCE_NAMES = ("metadata", "log", "annotations", "shard_report")


@dataclass
class CIFailure:
    """A classified CI failure."""

    run_id: str
    classification: FailureClass
    summary: str
    commit: str

    @property
    def redacted_summary(self) -> str:
        return _SECRET_RE.sub("***REDACTED***", self.summary)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "classification": self.classification.value,
            "summary": self.redacted_summary,
            "commit": self.commit,
        }


def classify_failure(log_text: str) -> FailureClass:
    """Classify a CI failure log into a category."""
    for cls, pattern in _CLASSIFIERS:
        if pattern.search(log_text):
            return cls
    return FailureClass.UNKNOWN


def _line_number(text: str, value: str) -> int:
    """Return the first 1-based source line containing a semantic value."""
    encoded = json.dumps(value, ensure_ascii=False)[1:-1]
    for number, line in enumerate(text.splitlines(), 1):
        if value in line or encoded in line:
            return number
    return 1


def _load_source(
    corpus_root: Path,
    source_name: str,
    outcome: dict[str, Any],
) -> tuple[Any | None, str | None, Path | None]:
    if outcome.get("outcome") != "success":
        return None, None, None
    relative = outcome.get("path")
    if not isinstance(relative, str) or not relative:
        return None, None, None
    path = (corpus_root / relative).resolve()
    try:
        path.relative_to(corpus_root.resolve())
    except ValueError:
        return None, None, None
    try:
        text = path.read_text(encoding="utf-8")
        if source_name == "log":
            return text, text, path
        return json.loads(text), text, path
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None, None, path


def _source_is_malformed(
    source_name: str,
    outcome: dict[str, Any],
    value: Any | None,
) -> bool:
    if outcome.get("outcome") not in {"success", "http_error", "not_provided"}:
        return True
    if outcome.get("outcome") != "success":
        return False
    if source_name == "metadata":
        return not isinstance(value, dict)
    if source_name == "log":
        return not isinstance(value, str)
    if source_name == "annotations":
        return not isinstance(value, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("message"), str)
            for item in value
        )
    return not isinstance(value, dict)


def _failing_step(metadata: dict[str, Any]) -> tuple[str | None, int]:
    steps = metadata.get("steps")
    if not isinstance(steps, list):
        return None, 1
    for step in steps:
        if isinstance(step, dict) and step.get("conclusion") == "failure":
            name = step.get("name")
            return (name if isinstance(name, str) else None), 1
    return None, 1


def _artifact_step_family(step: str | None) -> str | None:
    normalized = (step or "").lower()
    if "download-artifact" in normalized or "download artifact" in normalized:
        return MutationAdvisoryClass.INFRA_DOWNLOAD
    if (
        "upload-artifact" in normalized
        or "upload artifact" in normalized
        or normalized == "retain shard report"
    ):
        return MutationAdvisoryClass.INFRA_UPLOAD
    return None


def _evidence(
    source: str,
    path: Path,
    corpus_root: Path,
    text: str,
    matched_line: str,
) -> dict[str, Any]:
    return {
        "source": source,
        "path": path.relative_to(corpus_root).as_posix(),
        "line": _line_number(text, matched_line),
        "matched_line": matched_line,
    }


def _classify_mutation_advisory_job(
    corpus_root: Path,
    job: dict[str, Any],
) -> dict[str, Any]:
    outcomes = job.get("sources") if isinstance(job.get("sources"), dict) else {}
    fetch_outcomes = {
        name: dict(outcomes.get(name, {"outcome": "not_provided", "http_status": None, "path": None}))
        for name in _SOURCE_NAMES
    }
    loaded = {
        name: _load_source(corpus_root, name, fetch_outcomes[name])
        for name in _SOURCE_NAMES
    }
    malformed_sources = [
        name for name in _SOURCE_NAMES
        if _source_is_malformed(name, fetch_outcomes[name], loaded[name][0])
    ]
    metadata, metadata_text, metadata_path = loaded["metadata"]
    if not isinstance(metadata, dict):
        metadata = {}
    failing_step, _ = _failing_step(metadata)
    steps = metadata.get("steps") if isinstance(metadata.get("steps"), list) else []
    mutation_step = next(
        (step for step in steps if isinstance(step, dict) and step.get("name") == _MUTATION_STEP),
        None,
    )
    if mutation_step and mutation_step.get("conclusion") in {"success", "failure"}:
        mutation_executed = True
    elif mutation_step and mutation_step.get("conclusion") is None:
        mutation_executed = None
    else:
        mutation_executed = False

    classification = MutationAdvisoryClass.UNKNOWN
    evidence = None
    report, report_text, report_path = loaded["shard_report"]
    valid_report = (
        isinstance(report, dict)
        and isinstance(report.get("status"), str)
        and isinstance(report.get("message"), str)
        and isinstance(report.get("passed"), bool)
    )

    if (
        valid_report
        and failing_step == _MUTATION_STEP
        and report.get("status") == "tool_error"
        and isinstance(report.get("message"), str)
        and _ENGINE_TIMEOUT.search(report["message"])
        and report_text is not None
        and report_path is not None
    ):
        classification = MutationAdvisoryClass.ENGINE_TIMEOUT
        evidence = _evidence(
            "shard_report", report_path, corpus_root, report_text, report["message"]
        )
    elif failing_step == _MUTATION_STEP and valid_report:
        message = report.get("message") if isinstance(report.get("message"), str) else "valid shard report"
        if report_text is not None and report_path is not None:
            evidence = _evidence("shard_report", report_path, corpus_root, report_text, message)
    else:
        family = _artifact_step_family(failing_step)
        if family:
            for source_name in ("log", "annotations"):
                value, source_text, source_path = loaded[source_name]
                lines = value.splitlines() if isinstance(value, str) else [
                    item.get("message", "")
                    for item in value or []
                    if isinstance(item, dict) and isinstance(item.get("message"), str)
                ]
                match = next((line for line in lines if _ARTIFACT_SERVICE_ERROR.search(line)), None)
                if match and source_text is not None and source_path is not None:
                    classification = family
                    evidence = _evidence(
                        source_name, source_path, corpus_root, source_text, match
                    )
                    break

        if classification == MutationAdvisoryClass.UNKNOWN:
            annotations, annotation_text, annotation_path = loaded["annotations"]
            annotation_lines = [
                item.get("message", "")
                for item in annotations or []
                if isinstance(item, dict) and isinstance(item.get("message"), str)
            ]
            match = next((line for line in annotation_lines if _LOST_RUNNER.search(line)), None)
            if match and annotation_text is not None and annotation_path is not None:
                classification = MutationAdvisoryClass.INFRA_LOST_RUNNER
                evidence = _evidence(
                    "annotations", annotation_path, corpus_root, annotation_text, match
                )
            elif (
                steps
                and all(isinstance(step, dict) and step.get("conclusion") is None for step in steps)
                and fetch_outcomes["log"].get("outcome") != "success"
                and metadata_text is not None
                and metadata_path is not None
            ):
                classification = MutationAdvisoryClass.INFRA_LOST_RUNNER
                matched = next(
                    line.strip()
                    for line in metadata_text.splitlines()
                    if '"conclusion": null' in line
                )
                evidence = _evidence(
                    "metadata", metadata_path, corpus_root, metadata_text,
                    matched,
                )

    if evidence is None and metadata_text is not None and metadata_path is not None:
        matched = failing_step or "no failing step recorded"
        evidence = _evidence("metadata", metadata_path, corpus_root, metadata_text, matched)

    if malformed_sources:
        classification = MutationAdvisoryClass.UNKNOWN

    return {
        "shard": job.get("shard"),
        "job_id": job.get("job_id"),
        "class": classification,
        "failing_step": failing_step,
        "evidence": evidence,
        "mutation_executed": mutation_executed,
        "fetch_outcomes": fetch_outcomes,
        "malformed_sources": malformed_sources,
    }


def _structural_mutation_advisory_verdict(
    corpus_root: Path,
    jobs: list[Any],
) -> dict[str, Any]:
    """Derive rerun safety only from retained shard-report structure."""
    needs_diagnosis = []
    completed_failures = []
    malformed_reports = []
    for job in jobs:
        if not isinstance(job, dict):
            malformed_reports.append(None)
            continue
        shard = job.get("shard")
        sources = job.get("sources")
        report_outcome = (
            sources.get("shard_report")
            if isinstance(sources, dict)
            and isinstance(sources.get("shard_report"), dict)
            else {"outcome": "not_provided"}
        )
        outcome = report_outcome.get("outcome")
        if outcome == "not_provided":
            continue
        if outcome != "success":
            malformed_reports.append(shard)
            continue
        report, _text, _path = _load_source(
            corpus_root, "shard_report", report_outcome
        )
        if (
            not isinstance(report, dict)
            or not isinstance(report.get("status"), str)
            or not isinstance(report.get("passed"), bool)
        ):
            malformed_reports.append(shard)
            continue
        if report["status"] != "completed":
            needs_diagnosis.append(shard)
        elif report["passed"] is not True:
            completed_failures.append(shard)
    return {
        "rerun_eligible": not completed_failures and not malformed_reports,
        "needs_diagnosis": needs_diagnosis,
        "completed_failures": completed_failures,
        "malformed_reports": malformed_reports,
    }


def classify_mutation_advisory_corpus(corpus_path: str | Path) -> dict[str, Any]:
    """Classify retained mutation-advisory evidence without provider access."""
    path = Path(corpus_path).resolve()
    corpus = json.loads(path.read_text(encoding="utf-8"))
    jobs = corpus.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("mutation-advisory corpus must contain a jobs list")
    results = [
        _classify_mutation_advisory_job(path.parent, job)
        for job in jobs
        if isinstance(job, dict)
    ]
    structural_verdict = _structural_mutation_advisory_verdict(path.parent, jobs)
    return {
        "schema_version": 1,
        "run_id": corpus.get("run_id"),
        "head_sha": corpus.get("head_sha"),
        "passed": len(results) == len(jobs) and all(
            result["class"] != MutationAdvisoryClass.UNKNOWN for result in results
        ),
        **structural_verdict,
        "jobs": results,
    }


def store_failure(history_path: str, failure: CIFailure) -> None:
    """Append failure to JSONL history, deduplicating by run_id."""
    p = Path(history_path)
    existing_ids: set[str] = set()
    if p.is_file():
        for line in p.read_text().splitlines():
            try:
                data = json.loads(line)
                existing_ids.add(data.get("run_id", ""))
            except json.JSONDecodeError:
                continue

    if failure.run_id in existing_ids:
        return

    with open(p, "a") as f:
        f.write(json.dumps(failure.to_dict()) + "\n")


def load_history(history_path: str) -> list[CIFailure]:
    """Load CI failure history from JSONL."""
    p = Path(history_path)
    if not p.is_file():
        return []
    failures: list[CIFailure] = []
    for line in p.read_text().splitlines():
        try:
            data = json.loads(line)
            failures.append(CIFailure(
                run_id=data["run_id"],
                classification=FailureClass(data["classification"]),
                summary=data["summary"],
                commit=data.get("commit", ""),
            ))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return failures
