"""P77 reproducible scorer for retained seeded-defect UAT evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_MANIFEST = Path(__file__).with_name("parity-seeds.json")


def load_seed_manifest(path: str | Path | None = None) -> dict:
    """Load the canonical seed set. The threshold remains unset until agreed."""
    return json.loads(Path(path or _MANIFEST).read_text(encoding="utf-8"))


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _actor_metrics(runs: list[dict], actor: str) -> dict:
    selected = [run for run in runs if run["actor"] == actor]
    total = len(selected)
    observed = sum(run["coverage_observed"] for run in selected)
    coverage_total = sum(run["coverage_total"] for run in selected)
    return {
        "seeds": total,
        "discovered": sum(bool(run["discovered"]) for run in selected),
        "discovery_rate": round(
            sum(bool(run["discovered"]) for run in selected) / total, 6,
        ) if total else None,
        "false_verdicts": sum(bool(run["false_verdict"]) for run in selected),
        "false_verdict_rate": round(
            sum(bool(run["false_verdict"]) for run in selected) / total, 6,
        ) if total else None,
        "coverage_observed": observed,
        "coverage_total": coverage_total,
        "coverage_rate": round(observed / coverage_total, 6) if coverage_total else None,
    }


def score_benchmark(
    evidence_path: str | Path,
    *,
    manifest_path: str | Path | None = None,
    evidence_root: str | Path | None = None,
) -> dict:
    """Validate retained evidence and reproduce P77 metrics without live runs."""
    manifest = load_seed_manifest(manifest_path)
    seed_ids = {seed["id"] for seed in manifest.get("seeds", [])}
    path = Path(evidence_path)
    root = Path(evidence_root or path.parent).resolve()
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_runs = payload["runs"]
        if not isinstance(raw_runs, list):
            raise TypeError("runs must be a list")
    except (KeyError, OSError, TypeError, ValueError) as exc:
        return {"status": "invalid", "errors": [f"invalid evidence: {exc}"],
                "metrics": {}, "canonical_identity": "",
                "graduation": {"ready": False, "blockers": ["valid evidence"]}}

    runs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for index, run in enumerate(raw_runs):
        if not isinstance(run, dict):
            errors.append(f"run {index}: expected object")
            continue
        seed_id = str(run.get("seed_id") or "")
        actor = str(run.get("actor") or "")
        key = (seed_id, actor)
        if seed_id not in seed_ids or actor not in {"agent", "human"} or key in seen:
            errors.append(f"run {index}: unknown or duplicate seed/actor")
            continue
        seen.add(key)
        artifact = run.get("artifact") or {}
        artifact_path = (root / str(artifact.get("path") or "")).resolve()
        if root not in artifact_path.parents:
            errors.append(f"run {index}: artifact path escapes evidence root")
            continue
        try:
            digest = "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        except OSError as exc:
            errors.append(f"run {index}: artifact unavailable: {exc}")
            continue
        if digest != artifact.get("digest"):
            errors.append(f"run {index}: artifact digest mismatch")
            continue
        observed = run.get("coverage_observed")
        total = run.get("coverage_total")
        if (not isinstance(observed, int) or isinstance(observed, bool)
                or not isinstance(total, int) or isinstance(total, bool)
                or observed < 0 or total < 0 or observed > total
                or not isinstance(run.get("discovered"), bool)
                or not isinstance(run.get("false_verdict"), bool)):
            errors.append(f"run {index}: invalid metric values")
            continue
        runs.append({
            "seed_id": seed_id, "actor": actor,
            "discovered": run["discovered"], "false_verdict": run["false_verdict"],
            "coverage_observed": observed, "coverage_total": total,
            "artifact_digest": digest,
        })

    metrics = {actor: _actor_metrics(runs, actor) for actor in ("agent", "human")}
    blockers = []
    expected = len(seed_ids)
    if metrics["agent"]["seeds"] != expected:
        blockers.append(f"agent evidence for all {expected} seeds")
    if metrics["human"]["seeds"] != expected:
        blockers.append(f"human evidence for all {expected} seeds")
    threshold = manifest.get("discovery_threshold")
    if threshold is None:
        blockers.append("agreed discovery threshold")
    if metrics["agent"]["false_verdicts"]:
        blockers.append("zero agent false verdicts")
    if (threshold is not None and metrics["agent"]["discovery_rate"] is not None
            and metrics["agent"]["discovery_rate"] < threshold):
        blockers.append("agent discovery rate meets threshold")
    if errors:
        blockers.append("all retained artifacts validate")
    complete = not errors and all(metrics[actor]["seeds"] == expected
                                  for actor in ("agent", "human"))
    identity = {
        "manifest": manifest,
        "runs": sorted(runs, key=lambda run: (run["seed_id"], run["actor"])),
    }
    return {
        "status": "invalid" if errors else ("complete" if complete else "incomplete"),
        "errors": errors,
        "metrics": metrics,
        "canonical_identity": _canonical_digest(identity),
        "graduation": {"ready": not blockers, "blockers": blockers},
    }
