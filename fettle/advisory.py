"""WP-B — Normalized Advisory Contract.

Shared dataclass, persistent deduplication, and size-capped rendering for
all Fettle advisory output. One mechanism, one source of truth.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Advisory:
    rule_id: str
    category: str
    severity: Severity
    confidence: float
    summary: str
    recommended_action: str
    discipline_id: str | None = None
    discipline_version: str | None = None
    dedupe_key: str = ""
    provenance: str = ""

    def __post_init__(self) -> None:
        if not self.dedupe_key:
            raw = f"{self.rule_id}:{self.category}:{self.summary[:50]}"
            object.__setattr__(
                self, "dedupe_key", hashlib.sha256(raw.encode()).hexdigest()[:16]
            )


class AdvisoryDeduplicator:
    """Cooldown-based dedup with persistence across hook invocations.

    Hooks are short-lived processes — in-memory state resets every call.
    State is persisted to state_dir/session/advisory_state.json.
    Corrupt or missing state → treat as empty (fail-open).
    """

    def __init__(
        self,
        state_dir: Path | str,
        session_id: str,
        cooldown_s: float = 300.0,
        window_s: float = 900.0,
    ) -> None:
        self.cooldown_s = cooldown_s
        self.window_s = window_s
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_") or "unknown"
        self._state_path = Path(state_dir) / safe_id / "advisory_state.json"
        self._state: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            if self._state_path.is_file():
                with open(self._state_path) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = str(self._state_path) + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self._state, f, separators=(",", ":"))
            os.replace(tmp, self._state_path)
        except OSError:
            pass

    def should_emit(self, advisory: Advisory) -> bool:
        now = time.time()
        key = advisory.dedupe_key
        entry = self._state.get(key)
        if isinstance(entry, dict):
            last = entry.get("last_emitted", 0.0)
            if now - last < self.cooldown_s:
                return False
        return True

    def record(self, advisory: Advisory) -> None:
        now = time.time()
        key = advisory.dedupe_key
        entry = self._state.get(key)
        if isinstance(entry, dict):
            entry["last_emitted"] = now
            entry["count"] = entry.get("count", 0) + 1
        else:
            self._state[key] = {"last_emitted": now, "count": 1}
        self._prune(now)
        self._save()

    def _prune(self, now: float) -> None:
        expired = [
            k for k, v in self._state.items()
            if isinstance(v, dict) and now - v.get("last_emitted", 0) > self.window_s
        ]
        for k in expired:
            del self._state[k]


def format_advisories(advisories: list[Advisory], max_total_bytes: int = 2048) -> str:
    """Render advisories as additionalContext string, respecting size cap."""
    lines: list[str] = []
    total = 0
    for i, a in enumerate(advisories):
        line = f"[{a.severity.value.upper()}] {a.rule_id}: {a.summary}"
        if a.recommended_action:
            line += f"\n  → {a.recommended_action}"
        if a.discipline_id:
            line += f"\n  (see: {a.discipline_id})"
        encoded_len = len(line.encode("utf-8"))
        if total + encoded_len > max_total_bytes:
            remaining = len(advisories) - i
            lines.append(f"  ... ({remaining} more suppressed by size cap)")
            break
        lines.append(line)
        total += encoded_len
    return "\n".join(lines)
