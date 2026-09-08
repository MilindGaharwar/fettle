"""Reproducible prior-v1 versus hardened Assurance shadow comparison."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from fettle import __version__
from fettle.changeset import get_changed_files
from fettle.config import resolve_with_provenance
from fettle.source_snapshot import working_snapshot
from fettle.work_items import _claims_path

PROTOCOL_VERSION = "1"
BASELINE_COMMIT = "29fad420040ddee2201aea8b5b3838f7eb2a8a74"
FIRST_EXCLUDED_COMMIT = "f911f0eb88da0e026bca575d02ebc8e9432c3a04"
POLICY_NAME = "production"
ASSURANCE_SIDECAR = ".fettle/assurance-record.evidence.json"

_DIMENSIONS = (
    "authorization", "policy_integrity", "scope", "behavior", "security",
    "independence", "provenance", "uat", "ci",
)
_STATUSES = {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"}
_PROVENANCE_STATUSES = {"COMPLETE", "PARTIAL"}
_RETAINED_INPUTS = (
    ".fettle/ci-evidence.json",
    ".fettle/ci-status.json",
    ".fettle/ci-verdict.json",
    ".fettle/governance-ledger.jsonl",
    ".fettle/ledger-anchor.json",
    ".fettle/security-review.evidence.json",
    ".fettle/security-review.json",
    ".fettle/uat-report.evidence.json",
    ".fettle/uat-report.json",
    ".fettle/verify-evidence.json",
    ".fettle/verify.json",
    ".fettle/capsule.json",
    ".fettle.toml",
    "mutation-report.json",
)
_AUTHORITY_ENV = (
    "FETTLE_CONFIG", "FETTLE_GATE_MODE", "FETTLE_POLICY_CAPSULE",
    "FETTLE_PARENT_SESSION_ID", "FETTLE_ROLE", "FETTLE_SESSION_ID",
)


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _json_digest(value: object) -> str:
    content = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _digest_bytes(content)


def _capture_digest(capture: dict) -> str:
    identity = {
        key: value for key, value in capture.items()
        if key not in {"captured_at", "capture_manifest_digest"}
    }
    return _digest_bytes(_canonical_bytes(identity))


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, timeout=30,
    )


def _git_text(root: Path, *args: str) -> str:
    result = _run(root, *args)
    if result.returncode:
        message = result.stderr.decode(errors="replace").strip()
        raise ValueError(message or f"git {' '.join(args)} failed")
    return result.stdout.decode(errors="strict").strip()


def _implementation(root: Path, revision: str | None = None) -> tuple[str, str]:
    if revision:
        result = _run(root, "show", f"{revision}:fettle/assurance.py")
        if result.returncode:
            raise ValueError(f"baseline commit {revision} is unavailable")
        content = result.stdout
        commit = _git_text(root, "rev-parse", revision)
    else:
        path = Path(__file__).with_name("assurance.py")
        content = path.read_bytes()
        commit = _git_text(root, "rev-parse", "HEAD")
    return commit, _digest_bytes(content)


def _changed_files(root: Path) -> list[dict]:
    rows: dict[str, dict] = {}
    for item in get_changed_files(str(root)):
        relative = item.path.replace("\\", "/")
        candidate = root / relative
        try:
            candidate.resolve(strict=False).relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"changed path escapes repository: {relative}") from exc
        status = item.status.value
        digest = "deleted" if status == "deleted" else _digest_file(candidate)
        current = rows.get(relative)
        if current and current != {"path": relative, "status": status, "digest": digest}:
            raise ValueError(f"changed path has ambiguous staged and working states: {relative}")
        rows[relative] = {"path": relative, "status": status, "digest": digest}
    return [rows[path] for path in sorted(rows)]


def _status_digest(root: Path) -> str:
    result = _run(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if result.returncode:
        raise ValueError("cannot capture Git status")
    return _digest_bytes(result.stdout)


def _retained_inputs(root: Path) -> list[dict]:
    rows = []
    for relative in _RETAINED_INPUTS:
        path = root / relative
        if path.exists() and not path.is_file():
            raise ValueError(f"retained input is not a readable file: {relative}")
        if path.is_file():
            try:
                rows.append({"path": relative, "digest": _digest_file(path)})
            except OSError as exc:
                raise ValueError(f"retained input is unreadable: {relative}") from exc
    return rows


def _state_identity(root: Path) -> dict:
    trace, claims = _portable_state(root)
    return {
        "trace_digest": _digest_bytes(trace) if trace else None,
        "claims_digest": _digest_bytes(claims) if claims else None,
    }


def portable_value(value: object, root: Path) -> object:
    """Replace candidate-root path strings with portable repository-relative paths."""
    if isinstance(value, dict):
        return {key: portable_value(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_value(item, root) for item in value]
    if isinstance(value, str):
        root_text = str(root.resolve())
        if value == root_text:
            return "."
        prefix = root_text + os.sep
        if value.startswith(prefix):
            return value[len(prefix):].replace(os.sep, "/")
    return value


def _portable_state(root: Path) -> tuple[bytes, bytes]:
    state_home = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
    trace_path = state_home / "fettle" / "trace.jsonl"
    trace_rows = []
    if trace_path.is_file():
        try:
            for line in trace_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("trace record is not an object")
                path = row.get("file")
                if row.get("hook") != "authorship_gate" or row.get("status") != "pass" \
                        or not isinstance(path, str):
                    continue
                candidate_path = Path(path)
                if not candidate_path.is_absolute():
                    candidate_path = root / candidate_path
                try:
                    relative = candidate_path.resolve().relative_to(root.resolve())
                except ValueError:
                    continue
                portable = portable_value(row, root)
                portable["file"] = relative.as_posix()
                trace_rows.append(portable)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("trace state is unreadable or malformed") from exc
    claims_path = _claims_path(str(root))
    claims = {}
    if claims_path and claims_path.is_file():
        try:
            content = json.loads(claims_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("claim state is unreadable or malformed") from exc
        if not isinstance(content, dict):
            raise ValueError("claim state is malformed")
        claims = {
            key: portable_value(value, root) for key, value in content.items()
            if isinstance(value, dict)
            and Path(str(value.get("worktree", ""))).resolve() == root.resolve()
        }
    trace = b"".join(_canonical_bytes(row) for row in trace_rows)
    claim_bytes = _canonical_bytes(claims) if claims else b""
    return trace, claim_bytes


def _reject_unstable_repository(root: Path) -> None:
    if _run(root, "ls-files", "-u", "-z").stdout:
        raise ValueError("repository has unresolved merge entries")
    submodules = _run(root, "submodule", "status", "--recursive")
    if submodules.returncode:
        raise ValueError("cannot inspect submodules")
    for line in submodules.stdout.decode(errors="replace").splitlines():
        if line[:1] in {"+", "-", "U"}:
            raise ValueError("repository has a dirty or unavailable submodule")


def capture_candidate(root: Path) -> dict:
    """Capture the portable semantic identity of one non-empty candidate change."""
    root = root.resolve()
    if not (root / ".git").exists():
        raise ValueError("candidate is not a Git worktree")
    _reject_unstable_repository(root)
    changed = _changed_files(root)
    if not changed:
        raise ValueError("candidate has no changed files")
    snapshot_result = working_snapshot(str(root))
    if snapshot_result.get("status") != "completed":
        raise ValueError(str(snapshot_result.get("message") or "cannot capture source snapshot"))
    config, layers = resolve_with_provenance(str(root))
    release = config.get("assurance", {}).get("release", {})
    policy = release.get(POLICY_NAME) if isinstance(release, dict) else None
    if not isinstance(policy, dict) or not policy:
        raise ValueError(f"missing [assurance.release.{POLICY_NAME}] policy")
    baseline_commit, baseline_digest = _implementation(root, BASELINE_COMMIT)
    hardened_commit, hardened_digest = _implementation(root)
    environment = []
    for name in _AUTHORITY_ENV:
        if name in os.environ:
            environment.append({"name": name, "value_digest": _digest_bytes(os.environ[name].encode())})
    candidate = {
        "head": _git_text(root, "rev-parse", "HEAD"),
        "source_snapshot_digest": "sha256:" + snapshot_result["snapshot"]["digest"],
        "policy_digest": _json_digest(config),
        "scope_digest": _json_digest([
            [row["path"], row["status"]] for row in changed
        ]),
        "status_digest": _status_digest(root),
    }
    capture = {
        "protocol_version": PROTOCOL_VERSION,
        "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "baseline": {"commit": baseline_commit, "implementation_digest": baseline_digest},
        "hardened": {"commit": hardened_commit, "implementation_digest": hardened_digest},
        "first_excluded_commit": FIRST_EXCLUDED_COMMIT,
        "candidate": candidate,
        "policy_name": POLICY_NAME,
        "policy": policy,
        "policy_layers": [layer.name for layer in layers],
        "changed_files": changed,
        "retained_inputs": _retained_inputs(root),
        "state": _state_identity(root),
        "environment": environment,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "hardened_fettle": __version__,
            "baseline_fettle": "1.12.1",
        },
    }
    capture["capture_manifest_digest"] = _capture_digest(capture)
    return capture


def verify_capture(root: Path, capture: dict) -> list[str]:
    """Return every way the candidate or authority-bearing state moved."""
    root = root.resolve()
    problems = []
    try:
        if _git_text(root, "rev-parse", "HEAD") != capture["candidate"]["head"]:
            problems.append("HEAD differs from capture")
        if _status_digest(root) != capture["candidate"]["status_digest"]:
            problems.append("Git status differs from capture")
        if _changed_files(root) != capture["changed_files"]:
            problems.append("changed files differ from capture")
        if _retained_inputs(root) != capture["retained_inputs"]:
            problems.append("retained evidence differs from capture")
        if _state_identity(root) != capture["state"]:
            problems.append("trace or claim state differs from capture")
        snapshot = working_snapshot(str(root))
        digest = "sha256:" + snapshot.get("snapshot", {}).get("digest", "")
        if snapshot.get("status") != "completed" or digest != capture["candidate"]["source_snapshot_digest"]:
            problems.append("source snapshot differs from capture")
        environment = [
            {"name": name, "value_digest": _digest_bytes(os.environ[name].encode())}
            for name in _AUTHORITY_ENV if name in os.environ
        ]
        if environment != capture["environment"]:
            problems.append("authority-bearing environment differs from capture")
    except (KeyError, OSError, UnicodeError, ValueError) as exc:
        problems.append(f"capture verification failed: {exc}")
    return problems


def evaluate_frozen_policy(dimensions: dict, policy: dict) -> dict:
    """Evaluate a captured release policy without consulting either code version."""
    criteria = []
    errors = []
    for name, requirement in sorted(policy.items()):
        if name not in _DIMENSIONS:
            errors.append(f"unknown dimension {name}")
            continue
        if not isinstance(requirement, str):
            errors.append(f"{name} requirement must be a status string")
            continue
        expected = [value.strip() for value in requirement.split("|")]
        allowed = _PROVENANCE_STATUSES if name == "provenance" else _STATUSES
        if not expected or any(value not in allowed for value in expected):
            errors.append(f"{name} has unsupported status requirement {requirement!r}")
            continue
        raw = dimensions.get(name, {})
        actual = raw.get("status", "UNKNOWN") if isinstance(raw, dict) else "UNKNOWN"
        if actual not in _STATUSES:
            errors.append(f"{name} has unsupported actual status {actual!r}")
            continue
        if name == "provenance":
            actual = "COMPLETE" if actual == "PASS" else "PARTIAL"
        criteria.append({
            "dimension": name, "actual": actual, "expected": expected,
            "passed": actual in expected,
        })
    status = "CONFIG_ERROR" if errors else (
        "PASS" if all(item["passed"] for item in criteria) else "FAIL"
    )
    return {"name": POLICY_NAME, "status": status, "criteria": criteria, "errors": errors}


def normalize_decision(raw: dict, capture: dict, commit: str, implementation_digest: str) -> dict:
    """Project evaluator output onto the protocol's semantic decision schema."""
    if raw.get("status") != "completed" or not isinstance(raw.get("record"), dict):
        raise ValueError("evaluator did not return a completed Assurance Record")
    record = raw["record"]
    source_dimensions = record.get("dimensions")
    if not isinstance(source_dimensions, dict):
        raise ValueError("evaluator returned malformed dimensions")
    dimensions = {}
    for name in _DIMENSIONS:
        value = source_dimensions.get(name, {})
        status = value.get("status", "UNKNOWN") if isinstance(value, dict) else "UNKNOWN"
        if status not in _STATUSES:
            raise ValueError(f"unsupported {name} status {status!r}")
        dimensions[name] = status
    policy = evaluate_frozen_policy(source_dimensions, capture["policy"])
    candidate = capture["candidate"]
    projection = {
        "evaluator": {"commit": commit, "implementation_digest": implementation_digest},
        "subject": {
            "head": candidate["head"],
            "source_snapshot_digest": candidate["source_snapshot_digest"],
        },
        "policy": {
            "name": POLICY_NAME, "digest": candidate["policy_digest"],
            "status": policy["status"], "criteria": policy["criteria"],
            "errors": policy["errors"],
        },
        "scope": {
            "digest": candidate["scope_digest"],
            "paths": [row["path"] for row in capture["changed_files"]],
        },
        "dimensions": dimensions,
        "completeness": "COMPLETE" if dimensions["provenance"] == "PASS" else "PARTIAL",
    }
    projection["semantic_input_digest"] = _json_digest(projection)
    return projection


def compare_decisions(prior: dict, hardened: dict) -> list[dict]:
    """Return deterministic differences for protocol-comparable semantic fields."""
    differences = []
    fields = [("policy.status", prior["policy"]["status"], hardened["policy"]["status"])]
    for name in _DIMENSIONS:
        fields.append((f"dimensions.{name}", prior["dimensions"][name], hardened["dimensions"][name]))
    fields.append(("completeness", prior["completeness"], hardened["completeness"]))
    prior_criteria = {item["dimension"]: item for item in prior["policy"].get("criteria", [])}
    hardened_criteria = {item["dimension"]: item for item in hardened["policy"].get("criteria", [])}
    for name in sorted(set(prior_criteria) | set(hardened_criteria)):
        fields.append((f"policy.criteria.{name}", prior_criteria.get(name), hardened_criteria.get(name)))
    for path, before, after in fields:
        if before != after:
            differences.append({"path": path, "prior": before, "hardened": after})
    return differences


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(_canonical_bytes(value))


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not an object")
    return value


def _verify_bundle(bundle: Path) -> tuple[dict, dict, dict, dict]:
    bundle = bundle.expanduser().resolve()
    required = (
        "capture.json", "changed-files.json", "prior-v1.raw.json",
        "prior-v1.decision.json", "hardened.raw.json", "hardened.decision.json",
        "comparison.json",
    )
    missing = [name for name in required if not (bundle / name).is_file()]
    if missing:
        raise ValueError("assessment bundle is incomplete: " + ", ".join(missing))
    capture = _read_json(bundle / "capture.json")
    if capture.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("unsupported capture protocol version")
    capture_digest = capture.get("capture_manifest_digest")
    if capture_digest != _capture_digest(capture):
        raise ValueError("capture manifest digest mismatch")
    if bundle.name != str(capture_digest).removeprefix("sha256:"):
        raise ValueError("bundle name does not match capture digest")
    changed = json.loads((bundle / "changed-files.json").read_text(encoding="utf-8"))
    if changed != capture.get("changed_files"):
        raise ValueError("changed-files.json disagrees with capture")
    for row in changed:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("changed-files.json is malformed")
        if row.get("status") == "deleted":
            continue
        source = (bundle / "source" / row["path"]).resolve()
        try:
            source.relative_to((bundle / "source").resolve())
        except ValueError as exc:
            raise ValueError("retained source path escapes bundle") from exc
        if not source.is_file() or _digest_file(source) != row.get("digest"):
            raise ValueError(f"retained source digest mismatch: {row['path']}")
    prior_raw = _read_json(bundle / "prior-v1.raw.json")
    hardened_raw = _read_json(bundle / "hardened.raw.json")
    prior = _read_json(bundle / "prior-v1.decision.json")
    hardened = _read_json(bundle / "hardened.decision.json")
    comparison = _read_json(bundle / "comparison.json")
    if comparison.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("unsupported comparison protocol version")
    raw_digests = comparison.get("raw_digests", {})
    if raw_digests.get("prior_v1") != _digest_file(bundle / "prior-v1.raw.json") \
            or raw_digests.get("hardened") != _digest_file(bundle / "hardened.raw.json"):
        raise ValueError("raw output digest mismatch")
    for name, decision in (("prior-v1", prior), ("hardened", hardened)):
        identity = {
            key: value for key, value in decision.items() if key != "semantic_input_digest"
        }
        if decision.get("semantic_input_digest") != _json_digest(identity):
            raise ValueError(f"{name} semantic decision digest mismatch")
    expected_prior = normalize_decision(
        prior_raw, capture, capture["baseline"]["commit"],
        capture["baseline"]["implementation_digest"],
    )
    expected_hardened = normalize_decision(
        hardened_raw, capture, capture["hardened"]["commit"],
        capture["hardened"]["implementation_digest"],
    )
    if prior != expected_prior or hardened != expected_hardened:
        raise ValueError("normalized decision does not match retained raw output")
    if comparison.get("differences") != compare_decisions(prior, hardened):
        raise ValueError("comparison differences do not match retained decisions")
    if hardened.get("policy", {}).get("status") == "PASS":
        failed = [name for name, status in hardened.get("dimensions", {}).items() if status == "FAIL"]
        if failed:
            raise ValueError("hardened false pass is present")
    return capture, prior, hardened, comparison


def review_bundle(
    bundle: Path,
    *,
    change: str,
    reviewer: str,
    reviewer_email: str,
    classifications: list[dict],
) -> dict:
    """Validate and record one human review without mutating collected evidence."""
    bundle = bundle.expanduser().resolve()
    if not change.strip() or not reviewer.strip() or not reviewer_email.strip():
        raise ValueError("change, reviewer, and reviewer email are required")
    if (bundle / "review.json").exists():
        raise ValueError("assessment bundle is already reviewed")
    capture, prior, hardened, comparison = _verify_bundle(bundle)
    differences = comparison["differences"]
    by_path = {}
    for item in classifications:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("classification is malformed")
        if item["path"] in by_path:
            raise ValueError(f"duplicate classification for {item['path']}")
        kind = item.get("classification")
        evidence = item.get("evidence")
        if kind not in {"intentional_hardening", "defect", "unresolved"} \
                or not isinstance(evidence, str) or not evidence.strip():
            raise ValueError(f"classification for {item['path']} requires valid evidence")
        by_path[item["path"]] = {
            "path": item["path"], "classification": kind, "evidence": evidence.strip(),
        }
    paths = [item["path"] for item in differences]
    if sorted(by_path) != sorted(paths):
        raise ValueError("classification must cover every difference exactly once")
    accepted = all(item["classification"] == "intentional_hardening" for item in by_path.values())
    review = {
        "protocol_version": PROTOCOL_VERSION,
        "capture_manifest_digest": capture["capture_manifest_digest"],
        "reviewed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "change": change.strip(),
        "reviewer": {"name": reviewer.strip(), "email": reviewer_email.strip()},
        "prior_decision": prior["policy"]["status"],
        "hardened_decision": hardened["policy"]["status"],
        "classifications": [by_path[path] for path in paths],
        "accepted": accepted,
    }
    review["review_digest"] = _json_digest(review)
    _write_json(bundle / "review.json", review)
    return review


def summarize_store(store: Path, register: Path | None = None) -> dict:
    """Verify reviewed bundles and derive CS-6 progress from retained evidence."""
    store = store.expanduser().resolve()
    if not store.is_dir():
        raise ValueError("assessment store does not exist")
    rows = []
    decision_pairs: Counter[str] = Counter()
    changed_dimensions: Counter[str] = Counter()
    classifications: Counter[str] = Counter()
    accepted_subjects: set[str] = set()
    for bundle in sorted(path for path in store.iterdir() if path.is_dir()):
        review_path = bundle / "review.json"
        if not review_path.is_file():
            continue
        capture, prior, hardened, comparison = _verify_bundle(bundle)
        review = _read_json(review_path)
        review_identity = {
            key: value for key, value in review.items() if key != "review_digest"
        }
        if review.get("review_digest") != _json_digest(review_identity):
            raise ValueError(f"review digest mismatch: {bundle.name}")
        if review.get("capture_manifest_digest") != capture["capture_manifest_digest"]:
            raise ValueError(f"review does not match bundle {bundle.name}")
        review_paths = [item.get("path") for item in review.get("classifications", [])]
        difference_paths = [item["path"] for item in comparison["differences"]]
        if review_paths != difference_paths:
            raise ValueError(f"review classifications do not match bundle {bundle.name}")
        reviewed_accepted = bool(review.get("accepted"))
        if reviewed_accepted and any(
            item.get("classification") != "intentional_hardening"
            for item in review.get("classifications", [])
        ):
            raise ValueError(f"accepted review contains non-accepted classification: {bundle.name}")
        subject = capture.get("candidate", {}).get("source_snapshot_digest")
        if not isinstance(subject, str) or not subject:
            raise ValueError(f"bundle has no source snapshot identity: {bundle.name}")
        duplicate_subject = reviewed_accepted and subject in accepted_subjects
        accepted = reviewed_accepted and not duplicate_subject
        if accepted:
            accepted_subjects.add(subject)
        pair = f"{prior['policy']['status']}->{hardened['policy']['status']}"
        decision_pairs[pair] += 1
        for path in difference_paths:
            changed_dimensions[path] += 1
        for item in review.get("classifications", []):
            classifications[item["classification"]] += 1
        rows.append({
            "date": review["reviewed_at"][:10], "change": review["change"],
            "capture_digest": capture["capture_manifest_digest"],
            "prior_decision": prior["policy"]["status"],
            "hardened_decision": hardened["policy"]["status"],
            "changed_dimensions": difference_paths,
            "classification": sorted({
                item["classification"] for item in review.get("classifications", [])
            }) or ["none"],
            "bundle": bundle.name,
            "reviewer": review["reviewer"]["name"], "accepted": accepted,
            "qualification": "duplicate_subject" if duplicate_subject else (
                "accepted" if accepted else "review_rejected"
            ),
        })
    accepted_count = sum(row["accepted"] for row in rows)
    summary = {
        "protocol_version": PROTOCOL_VERSION,
        "reviewed": len(rows), "accepted": accepted_count,
        "rejected": len(rows) - accepted_count, "remaining": max(0, 20 - accepted_count),
        "decision_pairs": dict(sorted(decision_pairs.items())),
        "changed_dimensions": dict(sorted(changed_dimensions.items())),
        "classifications": dict(sorted(classifications.items())),
        "rows": rows,
    }
    _write_json(store / "summary.json", summary)
    if register:
        lines = [
            "# Assurance Integrity Shadow Assessments", "",
            f"Status: collecting; {accepted_count} of 20 qualifying assessments accepted", "",
            "This append-only register records real change assessments before production",
            "enforcement. Test fixtures, repeated runs of an unchanged subject, and invented",
            "evidence do not count.", "",
            "Every row must follow the machine-reproducible",
            "[prior-v1 baseline protocol](assurance-integrity-baseline-protocol.md).", "",
            "## Acceptance Rules", "",
            "- Assess a real, distinct change with `fettle assurance --policy production`.",
            "- Use the reviewed collector/comparator required by the baseline protocol.",
            "- Retain exact subject content, normalized decisions, comparison, and digests.",
            "- Classify every difference with evidence; unresolved or defect rows do not count.",
            "- Enforcement requires 20 accepted rows and explicit operator approval.", "",
            "## Register", "",
            "Generated from reviewed external bundles. Do not edit totals or rows manually.", "",
            "| # | Date | Change / PR | Capture digest | Prior decision | Hardened decision | Changed dimensions | Classification | Evidence bundle | Reviewer | Accepted |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for index, row in enumerate(rows, 1):
            lines.append(
                f"| {index} | {row['date']} | {row['change']} | `{row['capture_digest']}` | "
                f"{row['prior_decision']} | {row['hardened_decision']} | "
                f"{', '.join(row['changed_dimensions']) or 'none'} | "
                f"{', '.join(row['classification'])} | `{row['bundle']}` | "
                f"{row['reviewer']} | {'yes' if row['accepted'] else 'no'} |"
            )
        lines.extend([
            "", "## Operator Decision", "",
            "Not requested. Fewer than 20 qualifying assessments have been accepted."
            if accepted_count < 20 else
            "Pending explicit operator review and decision; 20 rows do not self-authorize enforcement.",
        ])
        register.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def _copy_state(root: Path, bundle: Path, runtime: Path) -> Path:
    retained = bundle / "state"
    (retained / "fettle").mkdir(parents=True)
    (runtime / "fettle").mkdir(parents=True)
    trace, claims = _portable_state(root)
    if trace:
        (retained / "fettle" / "trace.jsonl").write_bytes(trace)
        runtime_rows = []
        for line in trace.decode("utf-8").splitlines():
            row = json.loads(line)
            row["file"] = str(root / row["file"])
            runtime_rows.append(row)
        (runtime / "fettle" / "trace.jsonl").write_bytes(
            b"".join(_canonical_bytes(row) for row in runtime_rows)
        )
    if claims:
        (retained / "claims.json").write_bytes(claims)
    return runtime


def _run_prior(root: Path, frozen_state: Path, changed: list[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="fettle-prior-v1-") as temporary:
        extracted = Path(temporary)
        archive = subprocess.Popen(
            ["git", "archive", BASELINE_COMMIT, "fettle"], cwd=root,
            stdout=subprocess.PIPE,
        )
        unpack = subprocess.run(["tar", "-x", "-C", str(extracted)], stdin=archive.stdout, capture_output=True)
        if archive.stdout:
            archive.stdout.close()
        archive_code = archive.wait(timeout=30)
        if archive_code or unpack.returncode:
            raise ValueError("could not extract pinned baseline implementation")
        script = (
            "import json, pathlib; from fettle.assurance import build_assurance_record; "
            f"assert pathlib.Path(__import__('fettle.assurance').assurance.__file__).resolve().is_relative_to(pathlib.Path({str(extracted)!r}).resolve()); "
            f"print(json.dumps(build_assurance_record({str(root)!r}, changed_files={changed!r})))"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([str(extracted), str(root)])
        env["XDG_STATE_HOME"] = str(frozen_state)
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=extracted, env=env,
            capture_output=True, text=True, timeout=120,
        )
    if result.returncode:
        raise ValueError(f"prior-v1 evaluator failed: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("prior-v1 evaluator returned malformed JSON") from exc


def _run_hardened(root: Path, frozen_state: Path) -> tuple[dict, int, str]:
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(frozen_state)
    result = subprocess.run(
        [sys.executable, "-m", "fettle.cli", "assurance", "--root", str(root),
         "--policy", POLICY_NAME, "--json"],
        cwd=root, env=env, capture_output=True, text=True, timeout=120,
    )
    if result.returncode not in {0, 1, 2}:
        raise ValueError(f"hardened evaluator exited {result.returncode}")
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("hardened evaluator returned malformed JSON") from exc
    return raw, result.returncode, result.stderr


def collect(root: Path, store: Path) -> Path:
    """Capture, run, normalize, compare, and retain one unaccepted CS-6 bundle."""
    root = root.resolve()
    store = store.expanduser().resolve()
    try:
        store.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValueError("assessment store must be outside the candidate repository")
    capture = capture_candidate(root)
    bundle = store / capture["capture_manifest_digest"].removeprefix("sha256:")
    if bundle.exists():
        raise ValueError(f"assessment bundle already exists: {bundle}")
    bundle.mkdir(parents=True)
    try:
        _write_json(bundle / "capture.json", capture)
        _write_json(bundle / "changed-files.json", capture["changed_files"])
        for row in capture["changed_files"]:
            if row["status"] != "deleted":
                destination = bundle / "source" / row["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / row["path"], destination)
        paths = [row["path"] for row in capture["changed_files"]]
        with tempfile.TemporaryDirectory(prefix="fettle-baseline-state-") as state_dir:
            frozen_state = _copy_state(root, bundle, Path(state_dir))
            prior_raw = _run_prior(root, frozen_state, paths)
            hardened_raw, exit_code, stderr = _run_hardened(root, frozen_state)
        _write_json(bundle / "prior-v1.raw.json", portable_value(prior_raw, root))
        prior = normalize_decision(
            prior_raw, capture, capture["baseline"]["commit"],
            capture["baseline"]["implementation_digest"],
        )
        _write_json(bundle / "prior-v1.decision.json", prior)
        _write_json(bundle / "hardened.raw.json", portable_value(hardened_raw, root))
        if stderr:
            (bundle / "hardened.stderr.txt").write_text(stderr, encoding="utf-8")
        hardened = normalize_decision(
            hardened_raw, capture, capture["hardened"]["commit"],
            capture["hardened"]["implementation_digest"],
        )
        reported_policy = hardened_raw.get("policy", {})
        if not isinstance(reported_policy, dict) or reported_policy.get("status") != hardened["policy"]["status"]:
            raise ValueError("hardened CLI status disagrees with frozen policy decision")
        expected_exit = {"PASS": 0, "FAIL": 1, "CONFIG_ERROR": 2}[hardened["policy"]["status"]]
        if exit_code != expected_exit:
            raise ValueError("hardened CLI exit code disagrees with frozen policy decision")
        _write_json(bundle / "hardened.decision.json", hardened)
        problems = verify_capture(root, capture)
        if problems:
            raise ValueError("candidate changed during evaluation: " + "; ".join(problems))
        comparison = {
            "protocol_version": PROTOCOL_VERSION,
            "comparator_implementation_digest": _digest_file(Path(__file__)),
            "raw_digests": {
                "prior_v1": _digest_file(bundle / "prior-v1.raw.json"),
                "hardened": _digest_file(bundle / "hardened.raw.json"),
            },
            "differences": compare_decisions(prior, hardened),
            "accepted": False,
        }
        _write_json(bundle / "comparison.json", comparison)
    except BaseException:
        shutil.rmtree(bundle, ignore_errors=True)
        raise
    return bundle
