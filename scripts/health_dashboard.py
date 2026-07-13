"""Fettle v0.5.0 — WP-101+102: Health dashboard — metrics + drift detection."""

from __future__ import annotations

import json
from pathlib import Path


class HealthMetrics:
    """Track quality metrics per run and detect drift."""

    def __init__(self, path: str, max_entries: int = 200):
        self._path = Path(path)
        self._max_entries = max_entries

    def record(
        self,
        findings: int,
        duration_ms: float,
        tier: str,
        commit: str,
    ) -> None:
        """Record a check run's metrics."""
        entry = {
            "findings": findings,
            "duration_ms": duration_ms,
            "tier": tier,
            "commit": commit,
        }
        entries = self._load()
        entries.append(entry)
        if len(entries) > self._max_entries:
            entries = entries[-self._max_entries:]
        self._save(entries)

    def recent(self, n: int = 10) -> list[dict]:
        """Get the N most recent entries."""
        return self._load()[-n:]

    def trend(self, window: int = 5) -> str:
        """Detect findings trend: increasing, decreasing, stable, unknown."""
        entries = self._load()
        if len(entries) < window:
            return "unknown"

        recent = entries[-window:]
        counts = [e["findings"] for e in recent]

        if all(counts[i] <= counts[i + 1] for i in range(len(counts) - 1)) and counts[-1] > counts[0]:
            return "increasing"
        if all(counts[i] >= counts[i + 1] for i in range(len(counts) - 1)) and counts[-1] < counts[0]:
            return "decreasing"
        if max(counts) - min(counts) <= 1:
            return "stable"
        return "fluctuating"

    def _load(self) -> list[dict]:
        if not self._path.is_file():
            return []
        entries: list[dict] = []
        for line in self._path.read_text().splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def _save(self, entries: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
