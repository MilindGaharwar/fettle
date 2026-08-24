"""P72-A — per-scenario observation artifacts for UAT sessions."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

ARTIFACTS_DIR = ".fettle/uat-artifacts"


def _safe_name(scenario_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", scenario_id)


def block_sha(block: dict) -> str:
    canonical = json.dumps(block, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def write_scenario_artifacts(
    worktree: str,
    transcript: str,
    scenarios: list[dict],
    surface: str,
) -> str:
    """Write one observation artifact per reported scenario.

    The artifact captures the raw SCENARIO block (verbatim transcript slice)
    plus a content hash, giving the reconciler an independent capture to
    verify against. Returns the artifacts directory path.
    """
    from fettle.uat.reconcile import parse_transcript

    blocks = parse_transcript(transcript)
    base = Path(worktree) / ARTIFACTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    for s in scenarios:
        sid = s["id"]
        block = blocks.get(sid)
        if block is None:
            continue
        record = {
            "schema_version": 1,
            "scenario_id": sid,
            "surface": surface,
            "captured_at": round(time.time(), 3),
            "block": block,
            "block_sha": block_sha(block),
            "steps": list(s.get("steps", [])),
        }
        target = base / f"{_safe_name(sid)}.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(target)
    return str(base)


def load_scenario_artifacts(worktree_or_dir: str) -> dict[str, dict]:
    """Load {scenario_id: artifact} from a session's artifact bundle.

    Accepts either the session worktree or the artifacts directory returned
    by :func:`write_scenario_artifacts`.
    """
    location = Path(worktree_or_dir)
    base = location / ARTIFACTS_DIR
    if not base.is_dir():
        base = location
    out: dict[str, dict] = {}
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sid = record.get("scenario_id")
        if sid:
            out[sid] = record
    return out
