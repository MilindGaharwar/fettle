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


def capture_web_page(app_url: str, dest_dir: str) -> dict:
    """Full-page screenshot + accessibility tree for one web state (P74).

    Best-effort by contract: any failure — including playwright being
    absent entirely — returns a tool_error envelope instead of raising,
    so session completion is never masked.
    """
    try:
        from playwright.sync_api import sync_playwright

        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        shot = Path(dest_dir) / "_page.png"
        a11y_path = Path(dest_dir) / "_a11y.json"
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(app_url, wait_until="networkidle", timeout=30_000)
            page.screenshot(path=str(shot), full_page=True)
            a11y_path.write_text(json.dumps(page.accessibility.snapshot(),
                                            indent=2), encoding="utf-8")
            url = page.url
            browser.close()
        return {"status": "completed", "screenshot": str(shot),
                "a11y": str(a11y_path), "url": url}
    except Exception as exc:  # noqa: BLE001 - bounded best-effort by contract
        import logging
        logging.warning("web capture failed: %s: %s", type(exc).__name__, exc)
        return {"status": "tool_error",
                "message": f"web capture failed: {type(exc).__name__}: {exc}"}
