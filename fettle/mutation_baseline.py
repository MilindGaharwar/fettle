"""Strict mutation baseline establishment and canonical comparison."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import fcntl

from fettle.mutation_test import MUTMUT_VERSION, _STATES, _TEST_RUNNER, _validate_report_schema, compute_score
from fettle.overrides import OverrideContext, OverrideRecord, select_override

BASELINE_SCHEMA_VERSION = "1"
CLASSIFICATION_SCHEMA_VERSION = "1"
_DIGEST_FIELDS = ("policy_digest", "source_scope_digest", "test_mapping_digest", "line_range_digest")
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
_MAX_EVIDENCE_TEXT = 2048


def _digest(value: object) -> str:
    content = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()


def baseline_digest(value: dict) -> str:
    validate_baseline(value)
    return _digest(value)


def _read_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validate_full_report(report: dict) -> None:
    _validate_report_schema(report)
    if report.get("status") != "completed" or report.get("selection") != "all":
        raise ValueError("baseline reports must be completed full runs")
    if report.get("engine_version") != MUTMUT_VERSION or report.get("test_runner") != _TEST_RUNNER:
        raise ValueError("baseline report execution identity is unsupported")
    if report.get("untested") != 0:
        raise ValueError("baseline reports must have zero untested mutants")
    for field in ("revision", *_DIGEST_FIELDS):
        if not isinstance(report.get(field), str) or not report[field]:
            raise ValueError(f"baseline report requires {field}")
    if not re.fullmatch(r"[0-9a-f]{40}", report["revision"]):
        raise ValueError("baseline report revision is invalid")
    for field in _DIGEST_FIELDS:
        if not _HEX_DIGEST.fullmatch(report[field]):
            raise ValueError(f"baseline report {field} is invalid")
    if not isinstance(report.get("duration_ms"), int) or isinstance(report["duration_ms"], bool) or report["duration_ms"] < 0:
        raise ValueError("baseline report duration is invalid")
    expected = compute_score(*(report[state] for state in _STATES[:5]))
    if expected is None or report.get("score") != round(expected, 1):
        raise ValueError("baseline report score is invalid")


def _canonical_report_identity(report: dict) -> dict:
    return {
        "revision": report["revision"],
        "engine_version": report["engine_version"],
        "test_runner": report["test_runner"],
        "files_tested": report.get("files_tested"),
        "tests_run": report.get("tests_run"),
        "line_ranges": report.get("line_ranges"),
        **{field: report[field] for field in _DIGEST_FIELDS},
        **{state: report[state] for state in _STATES},
        "score": report["score"],
        "canonical_outcomes": sorted((record["fingerprint"], record["state"]) for record in report["non_killed"]),
    }


def _floor_override(
    records: list[OverrideRecord] | tuple[OverrideRecord, ...],
    report: dict,
    now: datetime | None,
) -> bool:
    context = OverrideContext(
        check_id="mutation.baseline",
        scope=report["files_tested"][0] if len(report["files_tested"]) == 1 else ".",
        revision=report["revision"],
        policy_digest=report["policy_digest"],
        evidence_id="baseline-floor",
        surface="ci",
    )
    return select_override(records, context, now=now).status == "overridden"


def establish_baseline(
    reports: list[dict],
    run_ids: list[str],
    *,
    floor: float,
    target: float | None = None,
    previous: dict | None = None,
    overrides: list[OverrideRecord] | tuple[OverrideRecord, ...] = (),
    now: datetime | None = None,
) -> dict:
    if not isinstance(floor, (int, float)) or isinstance(floor, bool) or not 0 <= floor <= 100:
        raise ValueError("baseline floor must be between 0 and 100")
    if target is None:
        target = float(floor)
    if not isinstance(target, (int, float)) or isinstance(target, bool) or not 0 <= target <= 100:
        raise ValueError("baseline target must be between 0 and 100")
    if len(reports) != 2 or len(run_ids) != 2 or len(set(run_ids)) != 2:
        raise ValueError("baseline establishment requires exactly two independent reports and run IDs")
    for report in reports:
        _validate_full_report(report)
    if _canonical_report_identity(reports[0]) != _canonical_report_identity(reports[1]):
        raise ValueError("baseline reports differ")
    first = reports[0]
    if previous is not None:
        validate_baseline(previous)
        if floor < previous["floor"] and not _floor_override(overrides, first, now):
            raise ValueError("baseline floor cannot decrease without a mutation.baseline override")
    created = (now or datetime.now(UTC)).astimezone(UTC).isoformat().replace("+00:00", "Z")
    survivor_fingerprints = sorted(
        record["fingerprint"] for record in first["non_killed"] if record["state"] == "survived"
    )
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "created_at": created,
        "run_ids": list(run_ids),
        "report_digests": [_digest(report) for report in reports],
        "revision": first["revision"],
        "engine_version": first["engine_version"],
        "test_runner": first["test_runner"],
        **{field: first[field] for field in _DIGEST_FIELDS},
        **{state: first[state] for state in _STATES},
        "score": first["score"],
        "floor": float(floor),
        "target": float(target),
        "survivor_fingerprints": survivor_fingerprints,
        "max_duration_ms": max(report["duration_ms"] for report in reports),
        "max_total_duration_ms": max(report.get("total_duration_ms", report["duration_ms"]) for report in reports),
    }


def validate_baseline(value: dict) -> None:
    required = {
        "schema_version", "created_at", "run_ids", "report_digests", "revision", "engine_version",
        "test_runner", *_DIGEST_FIELDS, *_STATES, "score", "floor", "target",
        "survivor_fingerprints", "max_duration_ms", "max_total_duration_ms",
    }
    if value.get("schema_version") != BASELINE_SCHEMA_VERSION or not required <= set(value):
        raise ValueError("mutation baseline has an unsupported or incomplete schema")
    if value["engine_version"] != MUTMUT_VERSION or value["test_runner"] != _TEST_RUNNER:
        raise ValueError("mutation baseline execution identity is unsupported")
    if not re.fullmatch(r"[0-9a-f]{40}", str(value["revision"])):
        raise ValueError("mutation baseline revision is invalid")
    if any(not isinstance(value[field], str) or not _HEX_DIGEST.fullmatch(value[field]) for field in _DIGEST_FIELDS):
        raise ValueError("mutation baseline identity digests are invalid")
    if any(not isinstance(value[state], int) or isinstance(value[state], bool) or value[state] < 0 for state in _STATES):
        raise ValueError("mutation baseline outcome counts are invalid")
    score = compute_score(*(value[state] for state in _STATES[:5]))
    if score is None or value["score"] != round(score, 1):
        raise ValueError("mutation baseline score is invalid")
    if not isinstance(value["survivor_fingerprints"], list) or value["survivor_fingerprints"] != sorted(set(value["survivor_fingerprints"])):
        raise ValueError("mutation baseline survivor fingerprints are invalid")
    if any(not isinstance(item, str) or len(item) != 64 for item in value["survivor_fingerprints"]):
        raise ValueError("mutation baseline survivor fingerprints are invalid")
    if value["untested"] != 0 or not isinstance(value["floor"], (int, float)) or isinstance(value["floor"], bool):
        raise ValueError("mutation baseline policy values are invalid")
    if not 0 <= value["floor"] <= 100:
        raise ValueError("mutation baseline floor is invalid")
    if not isinstance(value["target"], (int, float)) or isinstance(value["target"], bool) or not 0 <= value["target"] <= 100:
        raise ValueError("mutation baseline target is invalid")
    if any(
        not isinstance(value[field], int) or isinstance(value[field], bool) or value[field] < 0
        for field in ("max_duration_ms", "max_total_duration_ms")
    ):
        raise ValueError("mutation baseline duration is invalid")
    if (
        not isinstance(value["run_ids"], list) or len(value["run_ids"]) != 2
        or len(set(value["run_ids"])) != 2 or any(not isinstance(item, str) or not item for item in value["run_ids"])
    ):
        raise ValueError("mutation baseline run IDs are invalid")
    if (
        not isinstance(value["report_digests"], list) or len(value["report_digests"]) != 2
        or any(not isinstance(item, str) or not _HEX_DIGEST.fullmatch(item) for item in value["report_digests"])
    ):
        raise ValueError("mutation baseline report digests are invalid")


def load_baseline(path: Path) -> dict | None:
    if not path.exists():
        return None
    value = _read_object(path, "mutation baseline")
    validate_baseline(value)
    return value


@contextmanager
def _baseline_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / f".{path.name}.lock"
    with lock_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def save_baseline(path: Path, baseline: dict, *, expected_digest: str | None = None) -> str:
    with _baseline_lock(path):
        return _save_baseline_locked(path, baseline, expected_digest=expected_digest)


def _save_baseline_locked(path: Path, baseline: dict, *, expected_digest: str | None = None) -> str:
    existing_digest: str | None = None
    if path.exists():
        try:
            existing = load_baseline(path)
        except ValueError as exc:
            raise ValueError("refusing to overwrite an invalid existing mutation baseline") from exc
        assert existing is not None
        existing_digest = _digest(existing)
        if expected_digest is None:
            raise ValueError("existing mutation baseline requires an expected digest")
        if existing_digest != expected_digest:
            raise ValueError("mutation baseline changed since it was read")
    elif expected_digest is not None:
        raise ValueError("mutation baseline changed since it was read")
    validate_baseline(baseline)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(baseline, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and _digest(load_baseline(path)) != existing_digest:
            raise ValueError("mutation baseline changed during update")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return _digest(baseline)


def _classification(value: object, root: Path | None = None) -> dict:
    if not isinstance(value, dict):
        raise ValueError("classification record must be an object")
    required = {
        "fingerprint", "classification", "owner", "reason", "expiry", "policy_digest",
        "source_context_digest", "evidence",
    }
    if set(value) != required or value["classification"] not in {"equivalent", "unproductive"}:
        raise ValueError("classification record is incomplete or unsupported")
    if any(
        not isinstance(value[field], str) or not value[field] or len(value[field]) > _MAX_EVIDENCE_TEXT
        for field in required - {"evidence"}
    ):
        raise ValueError("classification record contains invalid text")
    for field in ("fingerprint", "policy_digest", "source_context_digest"):
        if not _HEX_DIGEST.fullmatch(value[field]):
            raise ValueError(f"classification {field} must be a SHA-256 digest")
    try:
        expiry = datetime.fromisoformat(value["expiry"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("classification expiry must be ISO-8601") from exc
    if expiry.tzinfo is None:
        raise ValueError("classification expiry must include a timezone")
    evidence = value["evidence"]
    if not isinstance(evidence, dict):
        raise ValueError("classification evidence must be an object")
    evidence_type = evidence.get("type")
    evidence_fields = {
        "behavioral": {"type", "steps", "expected"},
        "static": {"type", "tool", "version", "result_digest"},
        "oracle": {"type", "target", "content_digest"},
    }
    if evidence_type not in evidence_fields or set(evidence) != evidence_fields[evidence_type]:
        raise ValueError("classification evidence is incomplete or unsupported")
    if any(not isinstance(item, str) or not item or len(item) > _MAX_EVIDENCE_TEXT for item in evidence.values()):
        raise ValueError("classification evidence contains invalid text")
    if evidence_type == "static" and not _HEX_DIGEST.fullmatch(evidence["result_digest"]):
        raise ValueError("classification static result digest is invalid")
    if evidence_type == "oracle":
        target = Path(evidence["target"])
        if target.is_absolute() or ".." in target.parts:
            raise ValueError("classification oracle target must be repository-relative")
        if not _HEX_DIGEST.fullmatch(evidence["content_digest"]):
            raise ValueError("classification oracle content digest is invalid")
        if root is not None:
            oracle = root / target
            try:
                actual = hashlib.sha256(oracle.read_bytes()).hexdigest()
            except OSError as exc:
                raise ValueError("classification oracle target cannot be read") from exc
            if actual != evidence["content_digest"]:
                raise ValueError("classification oracle content digest does not match target")
    return value


def load_classifications(path: Path, *, root: Path | None = None) -> list[dict]:
    if not path.exists():
        return []
    value = _read_object(path, "mutation classification ledger")
    if value.get("schema_version") != CLASSIFICATION_SCHEMA_VERSION or not isinstance(value.get("classifications"), list):
        raise ValueError("mutation classification ledger has an unsupported schema")
    records = [_classification(item, root) for item in value["classifications"]]
    fingerprints = [record["fingerprint"] for record in records]
    if len(fingerprints) != len(set(fingerprints)):
        raise ValueError("mutation classification ledger contains duplicate fingerprints")
    return records


def compare_report(
    report: dict,
    baseline: dict,
    *,
    overrides: list[OverrideRecord] | tuple[OverrideRecord, ...] = (),
    classifications: list[dict] | None = None,
    now: datetime | None = None,
) -> dict:
    try:
        _validate_report_schema(report)
        validate_baseline(baseline)
    except ValueError as exc:
        return {"status": "unknown", "passed": False, "message": str(exc)}
    evaluation_time = (now or datetime.now(UTC)).astimezone(UTC)
    baseline_survivors = set(baseline["survivor_fingerprints"])
    current_survivors = {record["fingerprint"] for record in report["non_killed"] if record["state"] == "survived"}
    classifications_by_id = {item["fingerprint"]: item for item in (classifications or [])}
    compared: list[dict] = []
    for record in report["non_killed"]:
        fingerprint = record["fingerprint"]
        disposition = "existing" if fingerprint in baseline_survivors else "new"
        classification = classifications_by_id.get(fingerprint)
        if classification is not None:
            expiry = datetime.fromisoformat(classification["expiry"].replace("Z", "+00:00")).astimezone(UTC)
            if (
                expiry > evaluation_time
                and classification["policy_digest"] == report.get("policy_digest")
                and classification["source_context_digest"] == record.get("source_context_digest")
            ):
                disposition = "non_actionable"
        context = OverrideContext(
            check_id="mutation.survivor", scope=record["file"], revision=report["revision"],
            policy_digest=report["policy_digest"], evidence_id=fingerprint, surface="ci",
        )
        if disposition == "new" and select_override(overrides, context, now=evaluation_time).status == "overridden":
            disposition = "waived"
        compared.append({**record, "disposition": disposition})
    raw_counts = {state: report[state] for state in _STATES}
    return {
        "status": "completed",
        "records": compared,
        "resolved": sorted(baseline_survivors - current_survivors),
        "raw_counts": raw_counts,
        "score": report.get("score"),
        "passed": not any(record["disposition"] == "new" for record in compared),
    }
