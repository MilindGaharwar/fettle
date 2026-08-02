"""Fettle evolution — failure-signature sensing (WP-163, C1).

Read-only detectors over existing evidence stores. Two signals:

1. Rule-less trace clusters — the same (hook, finding code) blocking or
   firing as a violation repeatedly, with no rule file already covering the
   code in rules/proposed/, rules/learned/, or the bundled packs.
2. Recurring CI failure classes — the same ci_ingest FailureClass appearing
   repeatedly in .fettle/ci-failures.json.

This module never writes anything and never talks to a network: it is the
sensing half of governed self-evolution (design doc 13, D-C1/D-C6).
Drafting (C2) and promotion (C3) live elsewhere; promotion is human-gated.
"""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from fettle.ci_ingest import _SECRET_RE, FailureClass, load_history

MIN_OCCURRENCES = 3  # D-C1: constant, not config — no tuning surface yet
_MAX_SAMPLES = 3

# Trace statuses that represent friction worth learning from.
_FRICTION_STATUSES = {"blocked", "block", "violation"}

# CI failure classes where the log tail plausibly yields a semgrep-able
# code pattern. Process/infra classes are surfaced but not draftable (D-C6).
_DRAFTABLE_CI_CLASSES = {FailureClass.TEST, FailureClass.LINT, FailureClass.TYPE}

_RULE_ID_RE = re.compile(r"^\s*-?\s*id:\s*['\"]?([\w./-]+)", re.MULTILINE)

FAILURE_HISTORY_RELPATH = os.path.join(".fettle", "ci-failures.json")


@dataclass
class Signature:
    """A repeated failure pattern worth a rule proposal or a human look."""

    kind: str  # "trace-cluster" | "ci-class"
    key: str  # "<hook>/<code>" or the FailureClass value
    count: int
    first_ts: float = 0.0
    last_ts: float = 0.0
    sample_evidence: list[str] = field(default_factory=list)
    draftable: bool = False

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "key": self.key,
            "count": self.count,
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "sample_evidence": self.sample_evidence,
            "draftable": self.draftable,
        }


def _redact(text: str) -> str:
    return _SECRET_RE.sub("***REDACTED***", text)


def _rule_ids_in_dir(rules_path: Path) -> set[str]:
    """Rule ids declared in a directory of semgrep YAML files.

    An id is the filename stem or any `id:` entry inside the YAML —
    read with a regex so the runtime stays stdlib (no YAML parser).
    """
    ids: set[str] = set()
    if not rules_path.is_dir():
        return ids
    for yml in rules_path.glob("*.yml"):
        ids.add(yml.stem)
        try:
            ids.update(_RULE_ID_RE.findall(yml.read_text(encoding="utf-8")))
        except OSError:
            continue
    return ids


def covered_rule_ids(root: Path) -> set[str]:
    """All rule ids a signature could already be covered by.

    Proposed + learned project rules plus the bundled packs — a code that
    fires *because* a bundled rule exists is not a gap.
    """
    from fettle._resources import rules_dir

    covered = _rule_ids_in_dir(root / "rules" / "proposed")
    covered |= _rule_ids_in_dir(root / "rules" / "learned")
    covered |= _rule_ids_in_dir(rules_dir())
    return covered


def _detect_trace_clusters(root: Path, days: int) -> list[Signature]:
    from fettle.trace import get_recent_decisions

    cutoff = time.time() - days * 86400
    covered = covered_rule_ids(root)

    clusters: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for entry in get_recent_decisions(limit=10000):
        if entry.get("ts", 0) <= cutoff:
            continue
        if entry.get("status", "") not in _FRICTION_STATUSES:
            continue
        hook = entry.get("hook", "unknown")
        for finding in entry.get("findings", []):
            code = finding.get("code", "")
            if not code or code in covered:
                continue
            clusters[(hook, code)].append(
                {"ts": entry.get("ts", 0.0),
                 "message": finding.get("message", "") or code},
            )

    signatures = []
    for (hook, code), hits in clusters.items():
        if len(hits) < MIN_OCCURRENCES:
            continue
        timestamps = [h["ts"] for h in hits]
        samples = []
        for h in hits:
            sample = _redact(h["message"])
            if sample not in samples:
                samples.append(sample)
            if len(samples) >= _MAX_SAMPLES:
                break
        signatures.append(Signature(
            kind="trace-cluster",
            key=f"{hook}/{code}",
            count=len(hits),
            first_ts=min(timestamps),
            last_ts=max(timestamps),
            sample_evidence=samples,
            draftable=True,
        ))
    return signatures


def _detect_ci_classes(root: Path) -> list[Signature]:
    """Recurring CI failure classes from the ingested history.

    History entries carry no timestamp, so the window is the whole
    (run-id-deduplicated, ci_gate-rotated) file rather than `days`.
    """
    by_class: dict[FailureClass, list[str]] = defaultdict(list)
    for failure in load_history(str(root / FAILURE_HISTORY_RELPATH)):
        by_class[failure.classification].append(failure.redacted_summary)

    signatures = []
    for cls, summaries in by_class.items():
        if len(summaries) < MIN_OCCURRENCES:
            continue
        samples = [s[-200:].strip() for s in summaries[:_MAX_SAMPLES] if s]
        signatures.append(Signature(
            kind="ci-class",
            key=cls.value,
            count=len(summaries),
            sample_evidence=samples,
            draftable=cls in _DRAFTABLE_CI_CLASSES and bool(samples),
        ))
    return signatures


def detect_signatures(root: Path, days: int = 30) -> list[Signature]:
    """All repeated failure signatures, most frequent first."""
    signatures = _detect_trace_clusters(root, days) + _detect_ci_classes(root)
    signatures.sort(key=lambda s: (-s.count, s.key))
    return signatures
