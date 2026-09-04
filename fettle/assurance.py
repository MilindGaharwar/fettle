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
import tempfile
import tomllib
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fettle import __version__
from fettle.graph_types import canonical_digest
from fettle.paths import classify_file, is_within_repo
from fettle.trace import read_tail
from fettle.work_items import load_claims

SCHEMA_VERSION = 1
EVIDENCE_RELPATH = ".fettle/assurance-record.evidence.json"

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


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    normalized = unicodedata.normalize("NFC", encoded).encode("utf-8")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _dimension(status: str, evidence: list[dict], reason: str = "") -> dict:
    out: dict = {"status": status, "evidence": evidence}
    if reason:
        out["reason"] = reason
    return out


def _stage_ref(stage: str, root: Path, relative: str) -> dict:
    path = root / relative
    digest = _digest_of(path)
    return {"stage": stage, "path": relative,
            "digest": digest, "present": digest is not None}


def _git_head(root: Path) -> str:
    try:
        import subprocess
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root),
                              capture_output=True, text=True, timeout=5)
        if done.returncode == 0:
            return done.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def _verify_stamp_state(root: Path, config: dict, tests: dict | None) -> tuple[str, str]:
    """Judge the verify stamp: ('pass'|'fail'|'unbound'|'absent', reason).

    A stamp only counts as evidence of green behavior when it records a
    passing run (`ok is True`) AND is bound to this session and revision —
    a hand-written or stale stamp must never promote the dimension.
    """
    if tests is None:
        return "absent", "no verify stamp retained"
    from fettle.evidence import ResultState, Validity
    from fettle.verify_gate import validate_canonical_evidence

    result = validate_canonical_evidence(str(root), config, tests)
    if result.validity != Validity.VALID:
        return "unbound", (
            f"canonical verification evidence is {result.validity.value}; "
            f"run {result.recovery_action}"
        )
    if result.result_state == ResultState.PASS:
        return "pass", ""
    if result.result_state == ResultState.VIOLATION:
        return "fail", "canonical verification reported a violation"
    return "unbound", (
        f"canonical verification result is {result.result_state.value}; "
        f"run {result.recovery_action}"
    )


def _behavior_dimension(root: Path, config: dict) -> dict:
    evidence: list[dict] = []
    mutation = _read_json(root / "mutation-report.json")
    tests = _read_json(root / ".fettle" / "verify.json")
    if tests is not None:
        evidence.append({"path": ".fettle/verify.json",
                         "digest": _digest_of(root / ".fettle" / "verify.json")})
    stamp_state, stamp_reason = _verify_stamp_state(root, config, tests)
    if stamp_state in ("pass", "fail"):
        evidence.append({"path": ".fettle/verify-evidence.json",
                         "digest": _digest_of(root / ".fettle" / "verify-evidence.json")})
    if mutation is not None:
        evidence.append({"path": "mutation-report.json",
                         "digest": _digest_of(root / "mutation-report.json")})
        from fettle.evidence import ResultState, Validity
        from fettle.mutation_test import validate_canonical_evidence

        result = validate_canonical_evidence(str(root), config.get("mutation", {}), mutation)
        if result.validity != Validity.VALID:
            if stamp_state == "fail":
                return _dimension("FAIL", evidence, reason=stamp_reason)
            return _dimension(
                "UNKNOWN", evidence,
                reason=f"canonical mutation evidence is {result.validity.value}; "
                       f"run {result.recovery_action}",
            )
        if result.result_state == ResultState.VIOLATION:
            return _dimension("FAIL", evidence,
                              reason="canonical mutation reported a violation")
        if result.result_state != ResultState.PASS:
            if stamp_state == "fail":
                return _dimension("FAIL", evidence, reason=stamp_reason)
            return _dimension(
                "UNKNOWN", evidence,
                reason=f"canonical mutation result is {result.result_state.value}; "
                       f"run {result.recovery_action}",
            )
        if stamp_state == "fail":
            return _dimension("FAIL", evidence, reason=stamp_reason)
        if stamp_state in ("pass", "absent"):
            return _dimension("PASS", evidence)
        return _dimension("UNKNOWN", evidence, reason=stamp_reason)
    if stamp_state == "pass":
        return _dimension("PASS", evidence)
    if stamp_state == "fail":
        return _dimension("FAIL", evidence, reason=stamp_reason)
    if stamp_state == "unbound":
        return _dimension("UNKNOWN", evidence, reason=stamp_reason)
    return _dimension("UNKNOWN", [],
                      reason="no verify stamp or mutation report retained")


def _security_dimension(root: Path, config: dict) -> dict:
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
    if not isinstance(report.get("canonical_evidence"), dict):
        findings = report.get("findings")
        if not isinstance(findings, list):
            return _dimension("UNKNOWN", evidence,
                              reason="security review has malformed findings")
        if findings:
            suffix = "finding" if len(findings) == 1 else "findings"
            return _dimension(
                "UNKNOWN", evidence,
                reason=f"{len(findings)} security {suffix} retained in a raw, "
                       "non-canonical review",
            )
        complete = (
            isinstance(report.get("tools_used"), list)
            and bool(report["tools_used"])
            and isinstance(report.get("tools_missing"), list)
            and report.get("tools_missing") == []
            and isinstance(report.get("tool_errors"), list)
            and report.get("tool_errors") == []
        )
        reason = (
            "security review is complete but not canonical or bound to the "
            "assessed source, policy, and scope"
            if complete else "security review coverage is incomplete"
        )
        return _dimension("UNKNOWN", evidence, reason=reason)
    from fettle.evidence import ResultState, Validity
    from fettle.security_review import validate_canonical_evidence

    result = validate_canonical_evidence(str(root), config, report)
    if result.validity != Validity.VALID:
        return _dimension(
            "UNKNOWN", evidence,
            reason=f"canonical security evidence is {result.validity.value}; "
                   f"run {result.recovery_action}",
        )
    evidence.append({
        "path": ".fettle/security-review.evidence.json",
        "digest": _digest_of(root / ".fettle" / "security-review.evidence.json"),
    })
    if result.result_state == ResultState.PASS:
        return _dimension("PASS", evidence)
    if result.result_state == ResultState.VIOLATION:
        findings = report.get("blocking_findings", [])
        suffix = "finding" if len(findings) == 1 else "findings"
        return _dimension("FAIL", evidence,
                          reason=f"canonical security review reported {len(findings)} {suffix}")
    return _dimension(
        "UNKNOWN", evidence,
        reason=f"canonical security result is {result.result_state.value}; "
               f"run {result.recovery_action}",
    )


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


def _provenance_dimension(root: Path, assessed_commit: str | None) -> dict:
    evidence: list[dict] = []
    ledger = root / ".fettle" / "governance-ledger.jsonl"
    anchor = root / ".fettle" / "ledger-anchor.json"
    if ledger.is_file():
        evidence.append({"path": ".fettle/governance-ledger.jsonl",
                         "digest": _digest_of(ledger)})
    if anchor.is_file():
        evidence.append({"path": ".fettle/ledger-anchor.json",
                         "digest": _digest_of(anchor)})
        from fettle.evidence_ledger import verify_anchor

        state = verify_anchor(str(root))
        if state.get("status") != "anchored":
            return _dimension(
                "UNKNOWN", evidence,
                reason=f"governance ledger or anchor is invalid: "
                       f"{state.get('reason', state.get('status', 'unknown'))}",
            )
        if not assessed_commit or state.get("anchored_commit") != assessed_commit:
            return _dimension(
                "UNKNOWN", evidence,
                reason="governance anchor is bound to a different commit",
            )
        if state.get("coverage") != "known":
            return _dimension(
                "UNKNOWN", evidence,
                reason="governance anchor coverage is unknown",
            )
        if state.get("records_since_anchor") != 0:
            return _dimension(
                "UNKNOWN", evidence,
                reason="governance ledger has post-anchor records",
            )
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
        from fettle.evidence import ResultState, Validity
        from fettle.uat.reconcile import validate_canonical_evidence

        result = validate_canonical_evidence(str(root), report)
        if result.validity != Validity.VALID:
            return _dimension(
                "UNKNOWN", evidence,
                reason=f"canonical UAT evidence is {result.validity.value}; "
                       f"run {result.recovery_action}",
            )
        evidence.append({"path": ".fettle/uat-report.evidence.json",
                         "digest": _digest_of(root / ".fettle" / "uat-report.evidence.json")})
        confirmed = sum(1 for v in report.get("verdicts", [])
                         if v.get("verdict") == "CONFIRMED")
        total = len(report.get("verdicts", []))
        if result.result_state == ResultState.PASS:
            return _dimension("PASS", evidence)
        if result.result_state == ResultState.VIOLATION:
            return _dimension("FAIL", evidence,
                               reason=f"{confirmed}/{total} scenarios confirmed")
        return _dimension(
            "UNKNOWN", evidence,
            reason=f"canonical UAT result is {result.result_state.value}; "
                   f"run {result.recovery_action}",
        )
    return _dimension("UNKNOWN", [], reason="no UAT report retained")


def _ci_dimension(root: Path, config: dict) -> dict:
    path = root / ".fettle" / "ci-status.json"
    ci = _read_json(path)
    evidence: list[dict] = []
    if ci is not None:
        evidence.append({"path": ".fettle/ci-status.json",
                         "digest": _digest_of(path)})
        from fettle.ci_gate import validate_canonical_evidence
        from fettle.evidence import ResultState, Validity

        result = validate_canonical_evidence(str(root), config, ci)
        if result.validity != Validity.VALID:
            return _dimension(
                "UNKNOWN", evidence,
                reason=f"canonical CI evidence is {result.validity.value}; "
                       f"run {result.recovery_action}",
            )
        evidence.append({"path": ".fettle/ci-evidence.json",
                         "digest": _digest_of(root / ".fettle" / "ci-evidence.json")})
        if result.result_state == ResultState.PASS:
            return _dimension("PASS", evidence)
        if result.result_state == ResultState.VIOLATION:
            return _dimension("FAIL", evidence,
                              reason="canonical CI reported a violation")
        return _dimension("UNKNOWN", evidence,
                          reason=f"canonical CI result is {result.result_state.value}; "
                                 f"run {result.recovery_action}")
    return _dimension("NOT_APPLICABLE", [],
                      reason="no retained CI status (bind with fettle ci wait)")


def _authorization_dimension(root: Path) -> dict:
    import os

    from fettle.policy_capsule import ENV_VAR, resolve_env_capsule

    asserted = os.environ.get(ENV_VAR, "").strip()
    if not asserted:
        return _dimension("NOT_APPLICABLE", [],
                          reason="solo session — no delegation capsule")
    capsule = Path(asserted)
    evidence = [{"path": f"env:{ENV_VAR}", "digest": _digest_of(capsule)}]
    capsule_data, problem = resolve_env_capsule()
    if problem or capsule_data is None:
        return _dimension("FAIL", evidence,
                          reason=f"delegation capsule invalid: {problem}")
    return _dimension("PASS", evidence)


def _policy_integrity_dimension(policy_digest: str) -> dict:
    return _dimension(
        "PASS", [{"path": "effective-policy", "digest": policy_digest}],
    )


def _scope_dimension(scope_digest: str) -> dict:
    return _dimension("PASS",
                      [{"path": "git:changed-files", "digest": scope_digest}])


def _assessment_context(root: Path) -> dict:
    from fettle.changeset import get_changed_files
    from fettle.config import resolve_with_provenance
    from fettle.source_snapshot import working_snapshot

    source_result = working_snapshot(str(root))
    if source_result.get("status") != "completed":
        return {
            "status": "tool_error",
            "message": str(source_result.get("message") or "cannot identify working source"),
        }
    snapshot = source_result["snapshot"]
    config, layers = resolve_with_provenance(str(root))
    policy_digest = _json_digest(config)
    changed = get_changed_files(str(root))
    scope_rows = sorted({(item.path.replace("\\", "/"), item.status.value) for item in changed})
    scope_digest = _json_digest(scope_rows)
    return {
        "status": "completed",
        "source": {
            "kind": snapshot["kind"],
            "snapshot_digest": "sha256:" + snapshot["digest"],
            "revision": _git_head(root) or None,
        },
        "policy": {
            "digest": policy_digest,
            "layers": [layer.name for layer in layers],
        },
        "config": config,
        "scope": {
            "digest": scope_digest,
            "paths": [path for path, _status in scope_rows],
        },
    }


def evaluate_assurance_policy(record: dict, root: str, policy: str) -> dict:
    """Evaluate one named release policy against a completed assurance vector.

    The effective policy comes from the WP-20 resolver (defaults → org →
    remote → repo → capsule), so a repo-level .fettle.toml cannot silently
    replace org-mandated release criteria (2026-08 audit).
    """
    path = Path(root) / ".fettle.toml"
    if path.is_file():
        # The resolver skips corrupt layers fail-visible; a release decision
        # must instead refuse outright on an unparseable repo policy.
        try:
            with path.open("rb") as handle:
                tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return {"name": policy, "status": "CONFIG_ERROR", "criteria": [],
                    "errors": [f"could not parse .fettle.toml: {exc}"]}

    from fettle.config import load_config
    config = load_config(str(root))

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
    context = _assessment_context(root_path)
    if context["status"] != "completed":
        return context
    dimensions = {
        "authorization": _authorization_dimension(root_path),
        "policy_integrity": _policy_integrity_dimension(context["policy"]["digest"]),
        "scope": _scope_dimension(context["scope"]["digest"]),
        "behavior": _behavior_dimension(root_path, context["config"]),
        "security": _security_dimension(root_path, context["config"]),
        "independence": _independence_dimension(root_path),
        "provenance": _provenance_dimension(root_path, context["source"]["revision"]),
        "uat": _uat_dimension(root_path),
        "ci": _ci_dimension(root_path, context["config"]),
    }

    commit = context["source"]["revision"]

    stages = [
        _stage_ref("requirements", root_path, "specs"),
        _stage_ref("agent_actions", root_path, ".fettle/trace.jsonl"),
        _stage_ref("mutation", root_path, "mutation-report.json"),
        _stage_ref("uat", root_path, ".fettle/uat-report.json"),
        _stage_ref("ledger", root_path, ".fettle/governance-ledger.jsonl"),
        _stage_ref("anchor", root_path, ".fettle/ledger-anchor.json"),
    ]

    complete = all(d["status"] not in ("UNKNOWN",) for d in dimensions.values())
    record = {
        "schema_version": 1,
        "subject": {
            "commit": commit,
            "root": str(root_path.resolve()),
            "kind": context["source"]["kind"],
            "snapshot_digest": context["source"]["snapshot_digest"],
        },
        "policy": context["policy"],
        "scope": context["scope"],
        "generated_at": None,
        "stages": stages,
        "dimensions": dimensions,
        "completeness": "COMPLETE" if complete else "PARTIAL",
    }
    import time
    record["generated_at"] = round(time.time(), 3)
    digest_record = {k: v for k, v in record.items() if k not in ("digest", "generated_at")}
    digest_record["subject"] = {
        key: value for key, value in record["subject"].items() if key != "root"
    }
    record["digest"] = canonical_digest(digest_record)
    return {"status": "completed", "record": record}


def invalidate_evidence(root: str) -> dict:
    """Remove any prior assessment before attempting to publish a replacement."""
    path = Path(root) / EVIDENCE_RELPATH
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        return {"status": "tool_error",
                "message": f"cannot invalidate prior assurance record: {exc}"}
    return {"status": "completed"}


def _accepted_parent_references(root: Path, record: dict) -> tuple:
    from fettle.evidence import EvidenceReference, Validity, parse_artifact

    references: list[EvidenceReference] = []
    sidecars = {
        ".fettle/verify-evidence.json",
        ".fettle/ci-evidence.json",
        ".fettle/uat-report.evidence.json",
        ".fettle/security-review.evidence.json",
    }
    dimensions = record.get("dimensions", {})
    for dimension in dimensions.values():
        if not isinstance(dimension, dict):
            continue
        for item in dimension.get("evidence", []):
            relative = item.get("path") if isinstance(item, dict) else None
            if relative not in sidecars:
                continue
            path = root / relative
            if item.get("digest") != _digest_of(path):
                continue
            artifact = parse_artifact(path.read_bytes())
            references.append(EvidenceReference(
                artifact_digest=artifact.artifact_digest,
                kind=artifact.kind,
                expected={
                    "source_snapshot_digest": artifact.source["snapshot_digest"],
                    "policy_digest": artifact.policy_digest,
                    "scope_digest": artifact.scope_digest,
                    "producer_id": artifact.producer["id"],
                },
            ))

    mutation_path = root / "mutation-report.json"
    mutation = _read_json(mutation_path)
    if isinstance(mutation, dict):
        from fettle.config import load_config
        from fettle.mutation_test import (
            build_mutation_report_artifact,
            validate_canonical_evidence,
        )

        result = validate_canonical_evidence(
            str(root), load_config(str(root)).get("mutation", {}), mutation,
        )
        if result.validity == Validity.VALID:
            report_digest = "sha256:" + canonical_digest(mutation)
            artifact = build_mutation_report_artifact(
                mutation, "mutation-report.json",
                run_ids=mutation.get("run_ids") or [report_digest],
                calibration_ids=(
                    [mutation["calibration_id"]] if mutation.get("calibration_id") else []
                ),
            )
            references.append(EvidenceReference(
                artifact_digest=artifact.artifact_digest,
                kind=artifact.kind,
                expected={
                    "source_snapshot_digest": artifact.source["snapshot_digest"],
                    "policy_digest": artifact.policy_digest,
                    "scope_digest": artifact.scope_digest,
                    "producer_id": artifact.producer["id"],
                },
            ))
    return tuple(references)


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def write_evidence(root: str, record: dict) -> dict:
    """Atomically persist a portable canonical Assurance Record artifact."""
    from fettle.evidence import EvidenceArtifact

    invalidated = invalidate_evidence(root)
    if invalidated["status"] != "completed":
        return invalidated
    path = Path(root) / EVIDENCE_RELPATH
    try:
        subject = record["subject"]
        portable_record = {
            key: value for key, value in record.items()
            if key not in {"generated_at"}
        }
        portable_record["subject"] = {
            key: value for key, value in subject.items() if key != "root"
        }
        dimensions = record["dimensions"]
        if any(value.get("status") == "FAIL" for value in dimensions.values()):
            result_state = "violation"
        elif record.get("completeness") == "COMPLETE":
            result_state = "pass"
        else:
            result_state = "unknown"
        source = {"snapshot_digest": subject["snapshot_digest"]}
        if subject.get("commit"):
            source["revision"] = subject["commit"]
        artifact = EvidenceArtifact.create(
            kind="fettle.assurance.record",
            producer={
                "id": "fettle.assurance",
                "version": __version__,
                "implementation_digest": "sha256:" + hashlib.sha256(
                    Path(__file__).read_bytes(),
                ).hexdigest(),
            },
            result_state=result_state,
            completeness=(
                "complete" if record.get("completeness") == "COMPLETE" else "partial"
            ),
            trust_class="derived",
            source=source,
            policy_digest=record["policy"]["digest"],
            scope_digest=record["scope"]["digest"],
            observation_id="assurance-" + uuid.uuid4().hex,
            observed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            payload={"record": portable_record},
            parents=_accepted_parent_references(Path(root), record),
        )
        _write_bytes_atomic(path, artifact.to_bytes())
    except (KeyError, OSError, TypeError, ValueError) as exc:
        invalidate_evidence(root)
        return {"status": "tool_error", "message": str(exc) or type(exc).__name__}
    return {"status": "completed", "path": str(path),
            "evidence_id": artifact.observation_id}
