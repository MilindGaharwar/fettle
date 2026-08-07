"""Canonical, revision-bound override records for enforcing decisions."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1"
_MAX_TEXT = 2048


def _required_text(name: str, value: object, limit: int = _MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return value


def _scope(value: object) -> str:
    value = _required_text("scope", value, 1024).replace("\\", "/")
    normalized = posixpath.normpath(value)
    if normalized.startswith("/") or normalized == ".." or normalized.startswith("../"):
        raise ValueError("scope must be repository-relative")
    return normalized


def _instant(name: str, value: object) -> datetime:
    text = _required_text(name, value, 64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(UTC)


def _identity(payload: dict[str, str]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "ov-" + hashlib.sha256(canonical.encode()).hexdigest()[:24]


@dataclass(frozen=True)
class OverrideContext:
    check_id: str
    scope: str
    revision: str
    policy_digest: str
    evidence_id: str
    surface: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "check_id", _required_text("check_id", self.check_id, 256))
        object.__setattr__(self, "scope", _scope(self.scope))
        for name in ("revision", "policy_digest", "evidence_id", "surface"):
            object.__setattr__(self, name, _required_text(name, getattr(self, name), 256))


@dataclass(frozen=True)
class OverrideRecord:
    override_id: str
    actor: str
    reason: str
    timestamp: str
    expiry: str
    check_id: str
    scope: str
    revision: str
    policy_digest: str
    evidence_id: str
    surface: str
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def create(cls, **fields: str) -> OverrideRecord:
        payload = cls._validated_payload(fields)
        return cls(_identity(payload), **payload)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> OverrideRecord:
        if not isinstance(value, dict):
            raise ValueError("override record must be an object")
        if value.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported override schema_version: {value.get('schema_version')!r}")
        payload = cls._validated_payload(value)
        expected = _identity(payload)
        if value.get("override_id") != expected:
            raise ValueError("override_id does not match record content")
        return cls(expected, **payload)

    @staticmethod
    def _validated_payload(fields: dict[str, Any]) -> dict[str, str]:
        timestamp = _instant("timestamp", fields.get("timestamp"))
        expiry = _instant("expiry", fields.get("expiry"))
        if expiry <= timestamp:
            raise ValueError("expiry must be after timestamp")
        return {
            "actor": _required_text("actor", fields.get("actor"), 256),
            "reason": _required_text("reason", fields.get("reason")),
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "expiry": expiry.isoformat().replace("+00:00", "Z"),
            "check_id": _required_text("check_id", fields.get("check_id"), 256),
            "scope": _scope(fields.get("scope")),
            "revision": _required_text("revision", fields.get("revision"), 256),
            "policy_digest": _required_text("policy_digest", fields.get("policy_digest"), 256),
            "evidence_id": _required_text("evidence_id", fields.get("evidence_id"), 256),
            "surface": _required_text("surface", fields.get("surface"), 64),
            "schema_version": SCHEMA_VERSION,
        }

    @property
    def recorded_at(self) -> datetime:
        return _instant("timestamp", self.timestamp)

    @property
    def expires_at(self) -> datetime:
        return _instant("expiry", self.expiry)

    def is_expired(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("evaluation time must include a timezone")
        return self.expires_at <= now.astimezone(UTC)

    def matches(self, context: OverrideContext) -> bool:
        return all(
            getattr(self, field) == getattr(context, field)
            for field in ("check_id", "scope", "revision", "policy_digest", "evidence_id", "surface")
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "override_id": self.override_id,
            "actor": self.actor,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "expiry": self.expiry,
            "check_id": self.check_id,
            "scope": self.scope,
            "revision": self.revision,
            "policy_digest": self.policy_digest,
            "evidence_id": self.evidence_id,
            "surface": self.surface,
        }


@dataclass(frozen=True)
class OverrideLedger:
    records: tuple[OverrideRecord, ...] = ()
    invalid: tuple[str, ...] = ()


@dataclass(frozen=True)
class OverrideSelection:
    status: str
    record: OverrideRecord | None = None


def select_override(
    records: list[OverrideRecord] | tuple[OverrideRecord, ...],
    context: OverrideContext,
    *,
    now: datetime | None = None,
) -> OverrideSelection:
    evaluation_time = now or datetime.now(UTC)
    if evaluation_time.tzinfo is None or evaluation_time.utcoffset() is None:
        raise ValueError("evaluation time must include a timezone")
    evaluation_time = evaluation_time.astimezone(UTC)
    matching = [record for record in records if record.matches(context)]
    active = [
        record for record in matching
        if record.recorded_at <= evaluation_time and not record.is_expired(evaluation_time)
    ]
    if active:
        active.sort(key=lambda record: (record.expires_at, record.override_id))
        return OverrideSelection("overridden", active[0])
    expired = [record for record in matching if record.is_expired(evaluation_time)]
    if expired:
        expired.sort(key=lambda record: (record.expires_at, record.override_id), reverse=True)
        return OverrideSelection("expired", expired[0])
    if matching:
        matching.sort(key=lambda record: (record.recorded_at, record.override_id))
        return OverrideSelection("not_yet_active", matching[0])
    return OverrideSelection("not_found")


def _ledger_path(project_root: Path) -> Path:
    return project_root / ".fettle" / "overrides.json"


def load_override_ledger(project_root: Path) -> OverrideLedger:
    path = _ledger_path(project_root)
    if not path.exists():
        return OverrideLedger()
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return OverrideLedger(invalid=(f"cannot parse {path}: {exc}",))
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return OverrideLedger(invalid=("override ledger has an unsupported or missing schema_version",))
    values = data.get("overrides")
    if not isinstance(values, list):
        return OverrideLedger(invalid=("override ledger 'overrides' must be an array",))
    records: list[OverrideRecord] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        try:
            record = OverrideRecord.from_dict(value)
            if record.override_id in seen:
                raise ValueError(f"duplicate override_id {record.override_id}")
            seen.add(record.override_id)
            records.append(record)
        except (TypeError, ValueError) as exc:
            invalid.append(f"record {index}: {exc}")
    return OverrideLedger(tuple(records), tuple(invalid))


def save_override_ledger(project_root: Path, records: list[OverrideRecord]) -> None:
    directory = project_root / ".fettle"
    directory.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        {"schema_version": SCHEMA_VERSION, "overrides": [record.to_dict() for record in records]},
        indent=2,
    ) + "\n"
    fd, temporary = tempfile.mkstemp(dir=str(directory), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, _ledger_path(project_root))
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def summarize_ledger(
    ledger: OverrideLedger,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    evaluation_time = now or datetime.now(UTC)
    if evaluation_time.tzinfo is None or evaluation_time.utcoffset() is None:
        raise ValueError("evaluation time must include a timezone")
    evaluation_time = evaluation_time.astimezone(UTC)
    active = [
        record.to_dict() for record in ledger.records
        if record.recorded_at <= evaluation_time and not record.is_expired(evaluation_time)
    ]
    pending = [
        record.to_dict() for record in ledger.records if record.recorded_at > evaluation_time
    ]
    expired = [
        record.to_dict() for record in ledger.records if record.is_expired(evaluation_time)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "active_count": len(active),
        "pending_count": len(pending),
        "expired_count": len(expired),
        "invalid_count": len(ledger.invalid),
        "active": active,
        "pending": pending,
        "expired": expired,
        "invalid": list(ledger.invalid),
    }
