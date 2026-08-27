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
import tomllib
from pathlib import Path

from fettle.graph_types import canonical_digest
from fettle.paths import classify_file, is_within_repo
from fettle.trace import read_tail
from fettle.work_items import load_claims

SCHEMA_VERSION = 1

STAGES = (
    "requirements", "plan", "agent_actions", "files", "commit",
    "tests", "mutation", "ci", "release",
)

_DIMENSIONS = (
    "authorization", "policy_integrity", "scope", "behavior",
    "security", "independence", "provenance", "uat", "ci",
)

_DIMENSION_STATUSES = {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"}
_PROVENANCE_STATUSES = {"COMPLETE", "PARTIAL"}


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


def _security_dimension(root: Path) -> dict:
    path = root / ".fettle" / "security-review.json"
    report = _read_json(path)
    if not isinstance(report, dict):
        reason = ("security review is malformed" if path.exists()
                  else "no security review retained; run "
                       "python -m fettle.security_review --path . --json > "
                       ".fettle/security-review.json")
        return _dimension("UNKNOWN", [], reason=reason)
    evidence = [{"path": ".fettle/security-review.json",
                 "digest": _digest_of(path)}]
    findings = report.get("findings")
    if not isinstance(findings, list):
        return _dimension("UNKNOWN", evidence,
                          reason="security review has malformed findings")
    if findings:
        suffix = "finding" if len(findings) == 1 else "findings"
        return _dimension("FAIL", evidence,
                          reason=f"{len(findings)} security {suffix} retained")
    complete = (
        isinstance(report.get("tools_used"), list)
        and bool(report["tools_used"])
        and isinstance(report.get("tools_missing"), list)
        and report.get("tools_missing") == []
        and isinstance(report.get("tool_errors"), list)
        and report.get("tool_errors") == []
    )
    if complete:
        return _dimension("PASS", evidence)
    return _dimension("UNKNOWN", evidence,
                      reason="security review coverage is incomplete")


def _independence_dimension(root: Path) -> dict:
    trace = read_tail(max_bytes=1024 * 1024)
    verify_path = root / ".fettle" / "verify.json"
    verify = _read_json(verify_path)
    authors: dict[str, set[str]] = {"implementation": set(), "test": set()}
    parents: dict[str, str] = {}

    for entry in trace:
        if entry.get("hook") != "authorship_gate" or entry.get("status") != "pass":
            continue
        session = entry.get("session_id")
        role = entry.get("role")
        path = entry.get("file")
        if not all(isinstance(value, str) and value for value in (session, role, path)):
            continue
        if not is_within_repo(path, root):
            continue
        kind = classify_file(path)
        if (role, kind) not in {("implementer", "implementation"), ("tester", "test")}:
            continue
        authors[kind].add(session)
        parent = entry.get("parent_session_id")
        if isinstance(parent, str) and parent:
            parents[session] = parent

    implementers = authors["implementation"]
    testers = authors["test"]
    evidence = []
    if implementers or testers:
        evidence.append({"path": "trace:authorship_gate", "digest": "sha256:" + canonical_digest([
            entry for entry in trace if entry.get("hook") == "authorship_gate"
        ])})
    if verify is not None:
        evidence.append({"path": ".fettle/verify.json", "digest": _digest_of(verify_path)})

    if not implementers and not testers:
        return {**_dimension("UNKNOWN", evidence,
                             reason="no retained role-bound authorship decisions"),
                "grade": "UNKNOWN"}
    if not implementers or not testers:
        return {**_dimension("UNKNOWN", evidence,
                             reason="both implementation and test authorship are required"),
                "grade": "UNKNOWN"}
    if implementers & testers:
        return {**_dimension("FAIL", evidence,
                             reason="the same session authored implementation and tests"),
                "grade": "LOW"}

    verifier = verify.get("session_id") if isinstance(verify, dict) and verify.get("ok") is True else ""
    all_authors = implementers | testers
    shared_parents = {parents.get(session) for session in all_authors}
    separated = len(implementers) == 1 and len(testers) == 1
    same_lineage = separated and len(shared_parents) == 1 and None not in shared_parents
    claims = load_claims(str(root))
    claimed_sessions = {
        record.get("session_id") for record in claims.values()
        if isinstance(record, dict) and Path(str(record.get("worktree", ""))).resolve() == root.resolve()
    }
    claim_matches = bool(shared_parents & claimed_sessions)

    if same_lineage and isinstance(verifier, str) and verifier and verifier not in all_authors \
            and verifier in shared_parents and claim_matches:
        return {**_dimension("PASS", evidence), "grade": "HIGH"}
    return {**_dimension("PASS", evidence,
                         reason="code and tests have separate authors; independent verification or claim lineage is incomplete"),
            "grade": "MEDIUM"}


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


def evaluate_assurance_policy(record: dict, root: str, policy: str) -> dict:
    """Evaluate one named release policy against a completed assurance vector."""
    path = Path(root) / ".fettle.toml"
    try:
        with path.open("rb") as handle:
            config = tomllib.load(handle)
    except FileNotFoundError:
        return {"name": policy, "status": "CONFIG_ERROR", "criteria": [],
                "errors": [f"no .fettle.toml found for policy {policy}"]}
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {"name": policy, "status": "CONFIG_ERROR", "criteria": [],
                "errors": [f"could not parse .fettle.toml: {exc}"]}

    assurance = config.get("assurance", {})
    release = assurance.get("release", {}) if isinstance(assurance, dict) else {}
    rules = release.get(policy) if isinstance(release, dict) else None
    if not isinstance(rules, dict) or not rules:
        return {"name": policy, "status": "CONFIG_ERROR", "criteria": [],
                "errors": [f"missing [assurance.release.{policy}] policy"]}

    dimensions = record.get("dimensions", {})
    errors: list[str] = []
    criteria: list[dict] = []
    for name, requirement in sorted(rules.items()):
        if name not in _DIMENSIONS:
            errors.append(f"unknown dimension {name}")
            continue
        if not isinstance(requirement, str):
            errors.append(f"{name} requirement must be a status string")
            continue
        expected = [value.strip() for value in requirement.split("|")]
        allowed = (_PROVENANCE_STATUSES if name == "provenance"
                   else _DIMENSION_STATUSES)
        if not expected or any(value not in allowed for value in expected):
            errors.append(f"{name} has unsupported status requirement {requirement!r}")
            continue
        dimension = dimensions.get(name, {})
        dimension_status = dimension.get("status", "UNKNOWN")
        actual = dimension_status
        if name == "provenance" and dimension_status in _DIMENSION_STATUSES:
            actual = "COMPLETE" if dimension_status == "PASS" else "PARTIAL"
        criteria.append({
            "dimension": name,
            "actual": actual,
            "expected": expected,
            "passed": actual in expected,
            "reason": dimension.get("reason", ""),
            "evidence": dimension.get("evidence", []),
        })

    if errors:
        status = "CONFIG_ERROR"
    else:
        status = "PASS" if all(item["passed"] for item in criteria) else "FAIL"
    return {"name": policy, "status": status, "criteria": criteria,
            "errors": errors}


def build_assurance_record(root: str = ".",
                           changed_files: list[str] | None = None) -> dict:
    """Aggregate existing artifacts into the canonical Assurance Record."""
    root_path = Path(root)
    dimensions = {
        "authorization": _authorization_dimension(root_path),
        "policy_integrity": _policy_integrity_dimension(root_path),
        "scope": _scope_dimension(root_path, changed_files),
        "behavior": _behavior_dimension(root_path),
        "security": _security_dimension(root_path),
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
