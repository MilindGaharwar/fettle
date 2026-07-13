"""Fettle v0.5.0 — WP-91+92+93: CI diagnosis, learning loop, result history.

Explain failures, suggest gates, persist run results.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ci_ingest import CIFailure, FailureClass


_REPRODUCTION_COMMANDS: dict[FailureClass, str] = {
    FailureClass.TEST: "python3 -m pytest --tb=short",
    FailureClass.LINT: "ruff check .",
    FailureClass.TYPE: "pyright .",
    FailureClass.DEPENDENCY: "pip install -e . && pip check",
    FailureClass.BUILD: "pip install -e .",
    FailureClass.ENVIRONMENT: "fettle doctor",
    FailureClass.FLAKY: "python3 -m pytest --count=3",
}

_GATE_SUGGESTIONS: dict[FailureClass, str] = {
    FailureClass.TEST: "Enable test gate: fettle check --changed runs targeted tests before push",
    FailureClass.LINT: "Enable lint in enforce mode: [gates.lint].mode = 'enforce'",
    FailureClass.TYPE: "Add type checking: install pyright and enable in [checks.pyright]",
    FailureClass.DEPENDENCY: "Enable dependency validation: fettle check --changed includes deptry",
    FailureClass.BUILD: "Enable build validation in full tier: fettle check --full runs pip install",
}


@dataclass
class Diagnosis:
    """Explanation of a CI failure with reproduction steps."""

    explanation: str
    reproduction_command: str
    local_check: str = ""


def diagnose_failure(failure: CIFailure) -> Diagnosis:
    """Explain a CI failure and suggest reproduction."""
    explanations: dict[FailureClass, str] = {
        FailureClass.TEST: f"Test failure: {failure.summary}. Run tests locally to reproduce.",
        FailureClass.LINT: f"Lint failure: {failure.summary}. Run linter to see violations.",
        FailureClass.TYPE: f"Type error: {failure.summary}. Run type checker on affected files.",
        FailureClass.DEPENDENCY: f"Dependency issue: {failure.summary}. Check declared deps match imports.",
        FailureClass.BUILD: f"Build failure: {failure.summary}. Try installing the package locally.",
        FailureClass.ENVIRONMENT: f"Environment issue: {failure.summary}. CI environment differs from local.",
        FailureClass.FLAKY: f"Flaky test: {failure.summary}. Re-run to confirm; consider marking as flaky.",
        FailureClass.UNKNOWN: f"Unknown failure: {failure.summary}. Check CI logs for details.",
    }

    repro = _REPRODUCTION_COMMANDS.get(failure.classification, "fettle check --full")

    return Diagnosis(
        explanation=explanations.get(failure.classification, failure.summary),
        reproduction_command=repro,
        local_check="fettle check --changed",
    )


def compare_coverage(ci_checks: list[str], local_checks: list[str]) -> list[str]:
    """Show what CI checks are not covered locally."""
    return [c for c in ci_checks if c not in local_checks]


def suggest_new_gates(
    failures: list[CIFailure],
    threshold: int = 3,
) -> list[str]:
    """Suggest new gates after repeated same-class failures."""
    if not failures:
        return []

    counts = Counter(f.classification for f in failures)
    suggestions: list[str] = []
    for cls, count in counts.most_common():
        if count >= threshold and cls in _GATE_SUGGESTIONS:
            suggestions.append(_GATE_SUGGESTIONS[cls])

    return suggestions


class ResultHistory:
    """Persistent JSONL storage for check run results."""

    def __init__(self, path: str, max_entries: int = 100):
        self._path = Path(path)
        self._max_entries = max_entries

    def record(
        self,
        tier: str,
        findings_count: int,
        duration_ms: float,
        commit: str,
        workspace: str | None = None,
    ) -> None:
        """Append a run result."""
        entry = {
            "tier": tier,
            "findings_count": findings_count,
            "duration_ms": duration_ms,
            "commit": commit,
        }
        if workspace:
            entry["workspace"] = workspace

        entries = self._load_all()
        entries.append(entry)
        if len(entries) > self._max_entries:
            entries = entries[-self._max_entries:]
        self._save_all(entries)

    def recent(self, n: int = 10) -> list[dict]:
        """Get the N most recent entries."""
        entries = self._load_all()
        return entries[-n:]

    def _load_all(self) -> list[dict]:
        if not self._path.is_file():
            return []
        entries: list[dict] = []
        for line in self._path.read_text().splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def _save_all(self, entries: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
