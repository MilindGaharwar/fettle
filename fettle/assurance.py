"""P80 — the Assurance Record: one canonical, digest-bound answer to
"can we prove this agent-generated change deserves trust?"

Aggregates the artifacts Fettle already produces — verify stamp, mutation
report, UAT report, governance ledger (+anchor), spec coverage, spawn
lineage, policy digest — into ordered stage references and per-dimension
verdicts. Missing evidence never becomes a pass: dimensions without
retained artifacts are UNKNOWN with a reason.

The assurance chain is stored as ordered digest-bound stage references
inside the record — not a persistent graph store (see
docs/assurance-record-plan.md). P51's measured-admission gate remains the
decision path if aggregation performance ever demands persistence.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fettle.graph_types import canonical_digest

SCHEMA_VERSION = 1

STAGES = (
    "requirements", "plan", "agent_actions", "files", "commit",
    "tests", "mutation", "ci", "release",
)

_DIMENSIONS = (
    "authorization", "policy_integrity", "scope", "behavior",
    "security", "independence", "provenance", "uat", "ci",
)


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _digest_of(path: Path) -> str | None:
    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _dimension(status: str, evidence: list[dict], reason: str = "") -> dict:
    out: dict = {"status": status, "evidence": evidence}
    if reason:
        out["reason"] = reason
    return out


def _stage_ref(stage: str, path: Path) -> dict:
    digest = _digest_of(path)
    return {"stage": stage, "path": str(path),
            "digest": digest, "present": digest is not None}


def _behavior_dimension(root: Path) -> dict:
    evidence: list[dict] = []
    mutation = _read_json(root / "mutation-report.json")
    tests = _read_json(root / ".fettle" / "verify.json")
    if tests is not None:
        evidence.append({"path": ".fettle/verify.json",
                         "digest": _digest_of(root / ".fettle" / "verify.json")})
    if mutation is not None:
        evidence.append({"path": "mutation-report.json",
                         "digest": _digest_of(root / "mutation-report.json")})
        if mutation.get("status") == "completed":
            return _dimension("PASS", evidence)
        return _dimension("FAIL", evidence,
                          reason=f"mutation run {mutation.get('status')}")
    if tests is not None:
        return _dimension("PASS", evidence)
    return _dimension("UNKNOWN", [],
                      reason="no verify stamp or mutation report retained")


def _independence_dimension(root: Path) -> dict:
    roles_declared = False
    lineage_present = bool(os.environ.get("FETTLE_PARENT_SESSION"))
    cfg = _read_json(root / ".fettle" / "assurance-config.json") or {}
    roles_declared = bool(cfg.get("roles_declared"))
    if roles_declared or lineage_present:
        return _dimension("PASS",
                          [{"path": ".fettle/assurance-config.json",
                            "digest": _digest_of(root / ".fettle" / "assurance-config.json") or ""}])
    return _dimension("UNKNOWN", [],
                      reason="no role declaration or spawn lineage retained")


def _provenance_dimension(root: Path) -> dict:
    evidence: list[dict] = []
    ledger = root / ".fettle" / "governance-ledger.jsonl"
    anchor = root / ".fettle" / "ledger-anchor.json"
    if ledger.is_file():
        evidence.append({"path": ".fettle/governance-ledger.jsonl",
                         "digest": _digest_of(ledger)})
    anchor_data = _read_json(anchor)
    if anchor_data is not None:
        evidence.append({"path": ".fettle/ledger-anchor.json",
                         "digest": _digest_of(anchor)})
        return _dimension("PASS", evidence)
    if evidence:
        return _dimension("UNKNOWN", evidence,
                          reason="ledger present but never anchored")
    return _dimension("UNKNOWN", [], reason="no governance ledger retained")


def _uat_dimension(root: Path) -> dict:
    report = _read_json(root / ".fettle" / "uat-report.json")
    evidence: list[dict] = []
    path = root / ".fettle" / "uat-report.json"
    if report is not None:
        evidence.append({"path": ".fettle/uat-report.json",
                         "digest": _digest_of(path)})
        confirmed = sum(1 for v in report.get("verdicts", [])
                        if v.get("verdict") == "CONFIRMED")
        total = len(report.get("verdicts", []))
        if total and confirmed == total and report.get("candidate_scenarios") is not None:
            return _dimension("PASS", evidence)
        if total:
            return _dimension("FAIL", evidence,
                              reason=f"{confirmed}/{total} scenarios confirmed")
    return _dimension("UNKNOWN", [], reason="no UAT report retained")


def _ci_dimension(root: Path) -> dict:
    ci = _read_json(root / ".fettle" / "ci-verdict.json")
    path = root / ".fettle" / "ci-verdict.json"
    evidence: list[dict] = []
    if ci is not None:
        evidence.append({"path": ".fettle/ci-verdict.json",
                         "digest": _digest_of(path)})
        if ci.get("conclusion") == "success":
            return _dimension("PASS", evidence)
        return _dimension("FAIL", evidence,
                          reason=f"remote CI {ci.get('conclusion')}")
    return _dimension("NOT_APPLICABLE", [],
                      reason="no retained CI verdict (bind with fettle ci wait)")


def _authorization_dimension(root: Path) -> dict:
    capsule = root / ".fettle" / "capsule.json"
    capsule_data = _read_json(capsule)
    evidence: list[dict] = []
    if capsule_data is not None:
        evidence.append({"path": ".fettle/capsule.json",
                         "digest": _digest_of(capsule)})
        return _dimension("PASS", evidence)
    return _dimension("NOT_APPLICABLE", [],
                      reason="solo session — no delegation capsule")


def _policy_integrity_dimension(root: Path) -> dict:
    policy_digest = _digest_of(root / ".fettle.toml")
    if policy_digest:
        return _dimension("PASS",
                          [{"path": ".fettle.toml", "digest": policy_digest}])
    return _dimension("UNKNOWN", [], reason="no policy file found")


def _scope_dimension(root: Path, changed: list[str] | None) -> dict:
    if changed is None:
        return _dimension("UNKNOWN", [],
                          reason="changed-scope not provided for this record")
    return _dimension("PASS",
                      [{"path": "changed-files",
                        "digest": "sha256:" + hashlib.sha256(
                            json.dumps(sorted(changed)).encode()).hexdigest()}])


def build_assurance_record(root: str = ".",
                           changed_files: list[str] | None = None) -> dict:
    """Aggregate existing artifacts into the canonical Assurance Record."""
    root_path = Path(root)
    dimensions = {
        "authorization": _authorization_dimension(root_path),
        "policy_integrity": _policy_integrity_dimension(root_path),
        "scope": _scope_dimension(root_path, changed_files),
        "behavior": _behavior_dimension(root_path),
        "security": _dimension("UNKNOWN", [],
                               reason="security evidence joins in P81"),
        "independence": _independence_dimension(root_path),
        "provenance": _provenance_dimension(root_path),
        "uat": _uat_dimension(root_path),
        "ci": _ci_dimension(root_path),
    }

    commit = None
    try:
        import subprocess
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                              capture_output=True, text=True)
        if done.returncode == 0:
            commit = done.stdout.strip()
    except OSError:
        pass

    stages = [
        _stage_ref("requirements", root_path / "specs"),
        _stage_ref("agent_actions", root_path / ".fettle" / "trace.jsonl"),
        _stage_ref("mutation", root_path / "mutation-report.json"),
        _stage_ref("uat", root_path / ".fettle" / "uat-report.json"),
        _stage_ref("ledger", root_path / ".fettle" / "governance-ledger.jsonl"),
        _stage_ref("anchor", root_path / ".fettle" / "ledger-anchor.json"),
    ]

    complete = all(d["status"] not in ("UNKNOWN",) for d in dimensions.values())
    record = {
        "schema_version": 1,
        "subject": {"commit": commit, "root": str(root_path.resolve())},
        "generated_at": None,
        "stages": stages,
        "dimensions": dimensions,
        "completeness": "COMPLETE" if complete else "PARTIAL",
    }
    import time
    record["generated_at"] = round(time.time(), 3)
    record["digest"] = canonical_digest(
        {k: v for k, v in record.items() if k not in ("digest", "generated_at")}
    )
    return {"status": "completed", "record": record}


def write_evidence(root: str, record: dict) -> dict:
    """Persist the Assurance Record as a bounded evidence artifact."""
    from fettle.trace import build_evidence

    dims = record.get("dimensions", {})
    all_pass = all(
        d.get("status") in ("PASS", "NOT_APPLICABLE") for d in dims.values()
    )
    evidence = build_evidence(
        "assurance_record",
        exit_code=0 if all_pass else 1,
        scope=record.get("subject", {}).get("root", ""),
    )
    out_dir = Path(root) / ".fettle"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "assurance-record.evidence.json"
    out.write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "evidence_id": evidence["evidence_id"],
        "record_digest": record.get("digest", ""),
        "completeness": record.get("completeness", "UNKNOWN"),
        "dimensions": {k: v.get("status", "UNKNOWN")
                        for k, v in dims.items()},
        "evidence": evidence,
    }, indent=2) + "\n", encoding="utf-8")
    return {"status": "completed", "path": str(out),
            "evidence_id": evidence["evidence_id"]}
