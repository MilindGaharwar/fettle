"""Fettle v0.5.0 — WP-90: CI failure ingestion.

Read CI failures, classify, store in history.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class FailureClass(StrEnum):
    TEST = "test"
    LINT = "lint"
    TYPE = "type"
    DEPENDENCY = "dependency"
    BUILD = "build"
    ENVIRONMENT = "environment"
    FLAKY = "flaky"
    UNKNOWN = "unknown"


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
