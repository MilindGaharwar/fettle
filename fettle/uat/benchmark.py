"""P77 reproducible scorer for retained seeded-defect UAT evidence."""

from __future__ import annotations

import hashlib
import json
import math
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
    path = Path(evidence_path)
    root = Path(evidence_root or path.parent).resolve()
    errors: list[str] = []
    try:
        manifest = load_seed_manifest(manifest_path)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("seeds"), list):
            raise ValueError("manifest requires a seed list")
        seeds = manifest["seeds"]
        if (len(seeds) < 10 or any(not isinstance(seed, dict)
                                 or not isinstance(seed.get("id"), str)
                                 or not seed["id"].strip() for seed in seeds)):
            raise ValueError("manifest requires at least ten named seeds")
        seed_ids = {seed["id"] for seed in seeds}
        if len(seed_ids) != len(seeds):
            raise ValueError("manifest contains duplicate seeds")
        threshold = manifest.get("discovery_threshold")
        if threshold is not None and (
                type(threshold) not in (int, float) or not math.isfinite(threshold)
                or not 0 < threshold <= 1):
            raise ValueError("discovery threshold must be in (0, 1]")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("schema_version") == 2:
            return _score_controller_reports(payload, manifest)
        raw_runs = payload["runs"]
        if not isinstance(raw_runs, list):
            raise TypeError("runs must be a list")
    except (KeyError, OSError, TypeError, ValueError) as exc:
        return {"status": "invalid", "errors": [f"invalid evidence: {exc}"],
                "metrics": {}, "canonical_identity": "",
                "graduation": {"ready": False, "blockers": ["valid evidence"]}}

    runs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    artifact_digests: set[str] = set()
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
        if not isinstance(artifact, dict):
            errors.append(f"run {index}: artifact must be an object")
            continue
        artifact_path = (root / str(artifact.get("path") or "")).resolve()
        if root not in artifact_path.parents:
            errors.append(f"run {index}: artifact path escapes evidence root")
            continue
        try:
            content = artifact_path.read_bytes()
            digest = "sha256:" + hashlib.sha256(content).hexdigest()
        except OSError as exc:
            errors.append(f"run {index}: artifact unavailable: {exc}")
            continue
        if digest != artifact.get("digest"):
            errors.append(f"run {index}: artifact digest mismatch")
            continue
        if not content.strip() or digest in artifact_digests:
            errors.append(f"run {index}: empty or reused observation artifact")
            continue
        artifact_digests.add(digest)
        observed = run.get("coverage_observed")
        total = run.get("coverage_total")
        if (not isinstance(observed, int) or isinstance(observed, bool)
                or not isinstance(total, int) or isinstance(total, bool)
                or observed < 0 or total <= 0 or observed > total
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
    blockers = ["independently captured benchmark observations and validated contract oracles"]
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


def _score_controller_reports(payload: dict, manifest: dict) -> dict:
    from fettle.uat.reconcile import validate_canonical_evidence

    errors: list[str] = []
    seeds = {seed["id"]: seed.get("expected_state") for seed in manifest["seeds"]}
    valid_states = {"pass", "violation", "unknown"}
    if (any(state not in valid_states for state in seeds.values())
            or set(payload) != {"schema_version", "manifest_digest", "runs"}
            or payload["manifest_digest"] != _canonical_digest(manifest)
            or not isinstance(payload["runs"], list)):
        return {"status": "invalid", "errors": ["invalid frozen controller calibration manifest or runs"],
                "metrics": {}, "canonical_identity": "",
                "graduation": {"ready": False, "blockers": ["valid controller calibration evidence"]}}
    seen: set[str] = set()
    sessions: set[str] = set()
    rows = []
    for index, run in enumerate(payload["runs"]):
        try:
            if (not isinstance(run, dict) or set(run) != {"seed_id", "product_root", "report_digest"}
                    or not isinstance(run["seed_id"], str) or run["seed_id"] not in seeds
                    or run["seed_id"] in seen or not isinstance(run["product_root"], str)):
                raise ValueError("invalid or repeated seed report")
            seen.add(run["seed_id"])
            root = Path(run["product_root"]).resolve()
            path = root / ".fettle/uat-report.json"
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1048576:
                raise ValueError("report must be a bounded regular file")
            content = path.read_bytes()
            if "sha256:" + hashlib.sha256(content).hexdigest() != run["report_digest"]:
                raise ValueError("retained report digest mismatch")
            report = json.loads(content)
            if not isinstance(report, dict):
                raise ValueError("malformed report")
            result = validate_canonical_evidence(str(root), report)
            state = result.result_state.value
            if result.validity.value != "valid" or state not in valid_states:
                raise ValueError("canonical controller evidence is unavailable or invalid")
            session_path = root / ".fettle/uat-session.json"
            session = json.loads(session_path.read_text())
            session_id = session.get("session_id")
            if not session.get("capture_mode") or not session_id or session_id in sessions:
                raise ValueError("missing or reused independent controller capture")
            sessions.add(session_id)
            verdicts = report.get("verdicts", [])
            required = session.get("scenario_ids", [])
            observed = sum(item.get("verdict") in {"CONFIRMED", "CONTRADICTED"}
                           and item.get("scenario_id") in required for item in verdicts)
            rows.append({"seed_id": run["seed_id"], "state": state,
                         "expected_state": seeds[run["seed_id"]],
                         "report_digest": run["report_digest"], "session_id": session_id,
                         "coverage_observed": observed, "coverage_total": len(required)})
        except (KeyError, OSError, TypeError, ValueError) as exception:
            errors.append(f"run {index}: {exception}")
    defects = [row for row in rows if row["expected_state"] == "violation"]
    discovered = sum(row["state"] == "violation" for row in defects)
    false_passes = sum(row["state"] == "pass" and row["expected_state"] != "pass" for row in rows)
    false_verdicts = sum(row["state"] != row["expected_state"] for row in rows)
    observed = sum(row["coverage_observed"] for row in rows)
    total = sum(row["coverage_total"] for row in rows)
    complete = not errors and len(rows) == len(seeds)
    metrics = {"seeds": len(rows), "discovered": discovered,
               "discovery_rate": discovered / len(defects) if defects else None,
               "false_verdicts": false_verdicts, "false_passes": false_passes,
               "coverage_observed": observed, "coverage_total": total,
               "coverage_rate": observed / total if total else None}
    return {"status": "invalid" if errors else "complete" if complete else "incomplete",
            "errors": errors, "metrics": {"controller": metrics},
            "expected_states_matched": complete and false_verdicts == 0,
            "calibration_passed": complete and false_verdicts == 0 and total > 0 and observed == total,
            "canonical_identity": _canonical_digest({"manifest": manifest, "rows": rows}),
            "graduation": {"ready": False, "blockers": [
                "deterministic controller calibration does not establish native-agent discovery or human parity",
                "independently held-out qualification and explicit enforcement promotion remain required"]}}
