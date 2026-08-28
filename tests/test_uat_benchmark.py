"""P77 canonical seeded-defect UAT benchmark contracts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from fettle.uat.benchmark import load_seed_manifest, score_benchmark


def _write_evidence(root: Path, seed_ids: list[str], actors=("agent", "human")) -> Path:
    runs = []
    for seed_id in seed_ids:
        for actor in actors:
            artifact = root / "artifacts" / f"{seed_id}-{actor}.json"
            artifact.parent.mkdir(exist_ok=True)
            artifact.write_text(json.dumps({"seed_id": seed_id, "actor": actor}))
            runs.append({
                "seed_id": seed_id,
                "actor": actor,
                "discovered": True,
                "false_verdict": False,
                "coverage_observed": 3,
                "coverage_total": 4,
                "artifact": {
                    "path": str(artifact.relative_to(root)),
                    "digest": "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest(),
                },
            })
    path = root / "evidence.json"
    path.write_text(json.dumps({"schema_version": 1, "runs": runs}))
    return path


def test_canonical_manifest_has_ten_unique_seeds():
    manifest = load_seed_manifest()
    assert len(manifest["seeds"]) == 10
    assert len({seed["id"] for seed in manifest["seeds"]}) == 10
    assert manifest["discovery_threshold"] is None
    documented = Path("docs/uat/parity-seeds.json")
    assert manifest == load_seed_manifest(documented)


def test_complete_evidence_reproduces_metrics_but_unset_threshold_blocks(tmp_path):
    seed_ids = [seed["id"] for seed in load_seed_manifest()["seeds"]]
    result = score_benchmark(_write_evidence(tmp_path, seed_ids), evidence_root=tmp_path)
    assert result["status"] == "complete"
    assert result["metrics"]["agent"]["discovery_rate"] == 1.0
    assert result["metrics"]["human"]["coverage_rate"] == 0.75
    assert result["graduation"]["ready"] is False
    assert "agreed discovery threshold" in result["graduation"]["blockers"]
    assert result["canonical_identity"].startswith("sha256:")


def test_missing_human_baseline_remains_non_pass(tmp_path):
    seed_ids = [seed["id"] for seed in load_seed_manifest()["seeds"]]
    result = score_benchmark(
        _write_evidence(tmp_path, seed_ids, actors=("agent",)), evidence_root=tmp_path,
    )
    assert result["status"] == "incomplete"
    assert result["graduation"]["ready"] is False
    assert "human evidence for all 10 seeds" in result["graduation"]["blockers"]


def test_tampered_artifact_is_invalid_and_never_counted(tmp_path):
    seed_ids = [seed["id"] for seed in load_seed_manifest()["seeds"]]
    evidence = _write_evidence(tmp_path, seed_ids)
    payload = json.loads(evidence.read_text())
    artifact = tmp_path / payload["runs"][0]["artifact"]["path"]
    artifact.write_text("tampered")

    result = score_benchmark(evidence, evidence_root=tmp_path)
    assert result["status"] == "invalid"
    assert result["graduation"]["ready"] is False
    assert any("digest mismatch" in error for error in result["errors"])


def test_same_evidence_has_stable_canonical_identity(tmp_path):
    seed_ids = [seed["id"] for seed in load_seed_manifest()["seeds"]]
    evidence = _write_evidence(tmp_path, seed_ids)
    first = score_benchmark(evidence, evidence_root=tmp_path)
    second = score_benchmark(evidence, evidence_root=tmp_path)
    assert first["canonical_identity"] == second["canonical_identity"]


def test_cli_reports_real_evidence_as_blocked_until_threshold_agreed(tmp_path):
    (tmp_path / ".git").mkdir()
    seed_ids = [seed["id"] for seed in load_seed_manifest()["seeds"]]
    evidence = _write_evidence(tmp_path, seed_ids)
    result = subprocess.run(
        [sys.executable, "-m", "fettle.cli", "uat", "benchmark",
         "--evidence", str(evidence), "--json"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output["status"] == "complete"
    assert output["graduation"]["ready"] is False


def test_cli_rejects_malformed_evidence(tmp_path):
    (tmp_path / ".git").mkdir()
    evidence = tmp_path / "bad.json"
    evidence.write_text("not json")
    result = subprocess.run(
        [sys.executable, "-m", "fettle.cli", "uat", "benchmark",
         "--evidence", str(evidence), "--json"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "invalid"
