"""Portable, bounded evidence artifacts with fail-closed validation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Sequence


SCHEMA_VERSION = "1"
MAX_ARTIFACT_BYTES = 1024 * 1024
MAX_PAYLOAD_BYTES = 768 * 1024
MAX_STRING_BYTES = 64 * 1024
MAX_DEPTH = 32
MAX_OBJECT_KEYS = 4096
MAX_ARRAY_ITEMS = 10_000
MAX_PARENTS = 64

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_UTC_INSTANT = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z"
)
_DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/]")
_SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"(?i)(?:secret|password|token|api[_-]?key)\w*\s*[=:]\s*\S+"),
)

_ARTIFACT_FIELDS = {
    "schema_version", "artifact_digest", "kind", "producer", "result_state",
    "completeness", "trust_class", "source", "policy_digest", "scope_digest",
    "observation_id", "observed_at", "payload", "parents",
}
_REQUIRED_ARTIFACT_FIELDS = _ARTIFACT_FIELDS - {"parents"}
_PRODUCER_FIELDS = {"id", "version", "implementation_digest"}
_SOURCE_FIELDS = {"snapshot_digest", "revision"}
_REFERENCE_FIELDS = {"artifact_digest", "kind", "schema_version", "expected"}
_EXPECTED_FIELDS = {
    "source_snapshot_digest", "policy_digest", "scope_digest", "producer_id",
}


class ResultState(StrEnum):
    PASS = "pass"
    VIOLATION = "violation"
    OVERRIDDEN = "overridden"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class Validity(StrEnum):
    VALID = "valid"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    UNSUPPORTED = "unsupported"
    TAMPERED = "tampered"
    DIGEST_COLLISION = "digest_collision"
    DUPLICATE_ID = "duplicate_id"
    INCOMPLETE = "incomplete"
    STALE = "stale"
    WRONG_SOURCE = "wrong_source"
    WRONG_POLICY = "wrong_policy"
    WRONG_SCOPE = "wrong_scope"
    WRONG_PRODUCER = "wrong_producer"


class _EvidenceError(ValueError):
    def __init__(self, validity: Validity, message: str):
        super().__init__(message)
        self.validity = validity


def _normalized_text(value: object, name: str, *, max_bytes: int = MAX_STRING_BYTES) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = unicodedata.normalize("NFC", value)
    size = len(normalized.encode("utf-8"))
    if not normalized or size > max_bytes:
        raise ValueError(f"{name} must contain 1-{max_bytes} UTF-8 bytes")
    return normalized


def _digest(value: object, name: str) -> str:
    text = _normalized_text(value, name)
    if not _DIGEST.fullmatch(text):
        raise ValueError(f"{name} must be a full lowercase SHA-256 digest")
    return text


def _check_sensitive_text(value: str) -> None:
    if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
        raise ValueError("evidence contains secret material")
    portable = value.replace("\\", "/")
    if portable.startswith(("/", "../")) or portable == ".." or _DRIVE_PATH.match(value):
        raise ValueError("evidence contains an absolute or escaping path")


def _canonical_value(value: object, *, depth: int = 0, payload: bool = False) -> object:
    if depth > MAX_DEPTH:
        raise ValueError("evidence exceeds the maximum nesting depth")
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        raise ValueError("floats are not permitted in canonical evidence")
    if isinstance(value, str):
        normalized = _normalized_text(value, "string value")
        if payload:
            _check_sensitive_text(normalized)
        return normalized
    if isinstance(value, Mapping):
        if len(value) > MAX_OBJECT_KEYS:
            raise ValueError("evidence object has too many keys")
        normalized: list[tuple[str, object]] = []
        for key, item in value.items():
            normalized_key = _normalized_text(key, "object key")
            normalized.append((normalized_key, item))
        keys = [key for key, _item in normalized]
        if len(set(keys)) != len(keys):
            raise ValueError("evidence object keys are ambiguous after NFC normalization")
        return {
            key: _canonical_value(item, depth=depth + 1, payload=payload)
            for key, item in sorted(normalized, key=lambda pair: pair[0].encode("utf-8"))
        }
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_ARRAY_ITEMS:
            raise ValueError("evidence array has too many items")
        return [
            _canonical_value(item, depth=depth + 1, payload=payload)
            for item in value
        ]
    raise ValueError(f"unsupported canonical evidence value: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Return the strict canonical JSON representation of supported values."""
    return json.dumps(
        _canonical_value(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class EvidenceReference:
    artifact_digest: str
    kind: str
    expected: Mapping[str, str] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_digest", _digest(self.artifact_digest, "artifact_digest"))
        object.__setattr__(self, "kind", _normalized_text(self.kind, "kind", max_bytes=128))
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported evidence reference schema")
        if not isinstance(self.expected, Mapping) or not set(self.expected) <= _EXPECTED_FIELDS:
            raise ValueError("evidence reference has unknown expected fields")
        expected = {
            _normalized_text(key, "expected key"): _normalized_text(value, f"expected.{key}")
            for key, value in self.expected.items()
        }
        for key in ("source_snapshot_digest", "policy_digest", "scope_digest"):
            if key in expected:
                _digest(expected[key], f"expected.{key}")
        object.__setattr__(self, "expected", MappingProxyType(expected))

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_digest": self.artifact_digest,
            "kind": self.kind,
            "schema_version": self.schema_version,
            "expected": dict(self.expected),
        }


def _content_projection(value: Mapping[str, object]) -> dict[str, object]:
    return {
        key: item for key, item in value.items()
        if key not in {"artifact_digest", "observation_id", "observed_at"}
    }


def _content_digest(value: Mapping[str, object]) -> str:
    content = canonical_json(_content_projection(value)).encode("utf-8")
    return "sha256:" + hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class EvidenceArtifact:
    schema_version: str
    artifact_digest: str
    kind: str
    producer: Mapping[str, str]
    result_state: str
    completeness: str
    trust_class: str
    source: Mapping[str, str]
    policy_digest: str
    scope_digest: str
    observation_id: str
    observed_at: str
    payload: Mapping[str, object]
    parents: tuple[EvidenceReference, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        kind: str,
        producer: Mapping[str, str],
        result_state: str,
        completeness: str,
        trust_class: str,
        source: Mapping[str, str],
        policy_digest: str,
        scope_digest: str,
        observation_id: str,
        observed_at: str,
        payload: Mapping[str, object],
        parents: Sequence[EvidenceReference] = (),
    ) -> EvidenceArtifact:
        values: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "artifact_digest": "sha256:" + "0" * 64,
            "kind": kind,
            "producer": producer,
            "result_state": result_state,
            "completeness": completeness,
            "trust_class": trust_class,
            "source": source,
            "policy_digest": policy_digest,
            "scope_digest": scope_digest,
            "observation_id": observation_id,
            "observed_at": observed_at,
            "payload": payload,
        }
        if parents:
            values["parents"] = [
                parent.to_dict() for parent in sorted(
                    parents,
                    key=lambda item: (
                        item.artifact_digest, item.kind, item.schema_version,
                    ),
                )
            ]
        values["artifact_digest"] = _content_digest(values)
        return _artifact_from_dict(values, verify_digest=True)

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": self.schema_version,
            "artifact_digest": self.artifact_digest,
            "kind": self.kind,
            "producer": dict(self.producer),
            "result_state": self.result_state,
            "completeness": self.completeness,
            "trust_class": self.trust_class,
            "source": dict(self.source),
            "policy_digest": self.policy_digest,
            "scope_digest": self.scope_digest,
            "observation_id": self.observation_id,
            "observed_at": self.observed_at,
            "payload": _thaw(self.payload),
        }
        if self.parents:
            value["parents"] = [parent.to_dict() for parent in self.parents]
        return value

    def to_bytes(self) -> bytes:
        return canonical_json(self.to_dict()).encode("utf-8")


def _exact_fields(value: Mapping[str, object], required: set[str], allowed: set[str], name: str) -> None:
    fields = set(value)
    if not required <= fields <= allowed:
        raise ValueError(f"{name} has missing or unknown fields")


def _artifact_from_dict(value: Mapping[str, object], *, verify_digest: bool) -> EvidenceArtifact:
    _exact_fields(value, _REQUIRED_ARTIFACT_FIELDS, _ARTIFACT_FIELDS, "evidence artifact")
    if value["schema_version"] != SCHEMA_VERSION:
        raise _EvidenceError(Validity.UNSUPPORTED, "unsupported evidence artifact schema")
    if not isinstance(value["producer"], Mapping):
        raise ValueError("producer must be an object")
    if not isinstance(value["source"], Mapping):
        raise ValueError("source must be an object")
    if not isinstance(value["payload"], Mapping):
        raise ValueError("payload must be an object")
    producer = value["producer"]
    source = value["source"]
    payload = _canonical_value(value["payload"], payload=True)
    assert isinstance(payload, dict)
    _exact_fields(producer, _PRODUCER_FIELDS, _PRODUCER_FIELDS, "producer")
    _exact_fields(source, {"snapshot_digest"}, _SOURCE_FIELDS, "source")
    normalized_producer = {
        "id": _normalized_text(producer["id"], "producer.id"),
        "version": _normalized_text(producer["version"], "producer.version"),
        "implementation_digest": _digest(
            producer["implementation_digest"], "producer.implementation_digest"
        ),
    }
    normalized_source = {
        "snapshot_digest": _digest(source["snapshot_digest"], "source.snapshot_digest")
    }
    if "revision" in source:
        normalized_source["revision"] = _normalized_text(source["revision"], "source.revision")
    result_state = _normalized_text(value["result_state"], "result_state")
    try:
        ResultState(result_state)
    except ValueError as exc:
        raise ValueError("unsupported result_state") from exc
    completeness = _normalized_text(value["completeness"], "completeness")
    if completeness not in {"complete", "partial", "unknown"}:
        raise ValueError("unsupported completeness")
    trust_class = _normalized_text(value["trust_class"], "trust_class")
    if trust_class not in {"authoritative", "derived", "heuristic", "external"}:
        raise ValueError("unsupported trust_class")
    observed_at = _normalized_text(value["observed_at"], "observed_at")
    if not _UTC_INSTANT.fullmatch(observed_at):
        raise ValueError("observed_at must be a UTC RFC 3339 instant")
    raw_parents = value.get("parents", [])
    if not isinstance(raw_parents, (list, tuple)) or len(raw_parents) > MAX_PARENTS:
        raise ValueError("parents must be an array of at most 64 references")
    parents = tuple(
        parent if isinstance(parent, EvidenceReference) else _reference_from_dict(parent)
        for parent in raw_parents
    )
    parents = tuple(sorted(parents, key=lambda item: (
        item.artifact_digest, item.kind, item.schema_version,
    )))
    identities = [(item.artifact_digest, item.kind, item.schema_version) for item in parents]
    if len(set(identities)) != len(identities):
        raise ValueError("parents must be unique")
    artifact = EvidenceArtifact(
        schema_version=SCHEMA_VERSION,
        artifact_digest=_digest(value["artifact_digest"], "artifact_digest"),
        kind=_normalized_text(value["kind"], "kind", max_bytes=128),
        producer=MappingProxyType(normalized_producer),
        result_state=result_state,
        completeness=completeness,
        trust_class=trust_class,
        source=MappingProxyType(normalized_source),
        policy_digest=_digest(value["policy_digest"], "policy_digest"),
        scope_digest=_digest(value["scope_digest"], "scope_digest"),
        observation_id=_normalized_text(
            value["observation_id"], "observation_id", max_bytes=128
        ),
        observed_at=observed_at,
        payload=_freeze(payload),
        parents=parents,
    )
    serialized = artifact.to_bytes()
    if len(canonical_json(payload).encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("evidence payload exceeds 768 KiB")
    if len(serialized) > MAX_ARTIFACT_BYTES:
        raise ValueError("evidence artifact exceeds 1 MiB")
    if verify_digest and artifact.artifact_digest != _content_digest(artifact.to_dict()):
        raise _EvidenceError(Validity.TAMPERED, "evidence artifact digest does not match content")
    return artifact


def _reference_from_dict(value: object) -> EvidenceReference:
    if not isinstance(value, Mapping):
        raise ValueError("evidence reference must be an object")
    _exact_fields(value, _REFERENCE_FIELDS, _REFERENCE_FIELDS, "evidence reference")
    expected = value["expected"]
    if not isinstance(expected, Mapping):
        raise ValueError("reference expected bindings must be an object")
    return EvidenceReference(
        artifact_digest=value["artifact_digest"],  # type: ignore[arg-type]
        kind=value["kind"],  # type: ignore[arg-type]
        schema_version=value["schema_version"],  # type: ignore[arg-type]
        expected=expected,  # type: ignore[arg-type]
    )


def _decode_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in pairs:
        normalized_key = unicodedata.normalize("NFC", key)
        if normalized_key in normalized:
            raise ValueError("JSON object has duplicate or NFC-ambiguous keys")
        normalized[normalized_key] = value
    return normalized


def _parse_artifact(
    value: bytes | str | Mapping[str, object], *, verify_digest: bool,
) -> EvidenceArtifact:
    if isinstance(value, Mapping):
        return _artifact_from_dict(value, verify_digest=verify_digest)
    raw = value.encode("utf-8") if isinstance(value, str) else value
    if not isinstance(raw, bytes) or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("evidence must be canonical UTF-8 JSON without a BOM")
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("evidence artifact exceeds 1 MiB")
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_decode_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("evidence must be canonical UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("evidence artifact must be an object")
    if canonical_json(parsed).encode("utf-8") != raw:
        raise ValueError("evidence bytes are not canonical")
    return _artifact_from_dict(parsed, verify_digest=verify_digest)


def parse_artifact(value: bytes | str | Mapping[str, object]) -> EvidenceArtifact:
    """Parse a canonical artifact, rejecting coercion and digest mismatch."""
    return _parse_artifact(value, verify_digest=True)


@dataclass(frozen=True)
class EvidenceValidationContext:
    kind: str
    source_snapshot_digest: str
    source_revision: str | None
    policy_digest: str
    scope_digest: str
    producer_id: str
    producer_versions: frozenset[str]
    producer_implementation_digest: str
    require_complete: bool = True
    allowed_trust_classes: frozenset[str] = frozenset({"authoritative"})
    invalidated: bool = False
    recovery_action: str = ""


@dataclass(frozen=True)
class EvidenceValidationResult:
    validity: Validity
    result_state: ResultState
    recovery_action: str


def _failure(validity: Validity, context: EvidenceValidationContext) -> EvidenceValidationResult:
    return EvidenceValidationResult(validity, ResultState.UNKNOWN, context.recovery_action)


def validate_artifact(
    value: EvidenceArtifact | bytes | str | Mapping[str, object] | None,
    context: EvidenceValidationContext,
    *,
    registered_artifacts: Sequence[EvidenceArtifact] = (),
) -> EvidenceValidationResult:
    """Validate exact applicability without converting any failure to pass."""
    if value is None:
        return _failure(Validity.MISSING, context)
    try:
        artifact = value if isinstance(value, EvidenceArtifact) else _parse_artifact(
            value, verify_digest=False,
        )
        content = artifact.to_dict()
        calculated_digest = _content_digest(content)
        for registered in registered_artifacts:
            if registered.artifact_digest == artifact.artifact_digest:
                if canonical_json(registered.to_dict()) != canonical_json(content):
                    return _failure(Validity.DIGEST_COLLISION, context)
            if registered.observation_id == artifact.observation_id:
                if canonical_json(registered.to_dict()) != canonical_json(content):
                    return _failure(Validity.DUPLICATE_ID, context)
    except _EvidenceError as exc:
        return _failure(exc.validity, context)
    except (TypeError, ValueError):
        return _failure(Validity.MALFORMED, context)
    if artifact.schema_version != SCHEMA_VERSION or artifact.kind != context.kind:
        return _failure(Validity.UNSUPPORTED, context)
    if artifact.producer["id"] != context.producer_id:
        return _failure(Validity.WRONG_PRODUCER, context)
    if artifact.producer["version"] not in context.producer_versions:
        return _failure(Validity.UNSUPPORTED, context)
    if artifact.producer["implementation_digest"] != context.producer_implementation_digest:
        return _failure(Validity.WRONG_PRODUCER, context)
    if artifact.source["snapshot_digest"] != context.source_snapshot_digest:
        return _failure(Validity.WRONG_SOURCE, context)
    if (
        context.source_revision is not None
        and artifact.source.get("revision") != context.source_revision
    ):
        return _failure(Validity.WRONG_SOURCE, context)
    if artifact.policy_digest != context.policy_digest:
        return _failure(Validity.WRONG_POLICY, context)
    if artifact.scope_digest != context.scope_digest:
        return _failure(Validity.WRONG_SCOPE, context)
    if context.require_complete and artifact.completeness != "complete":
        return _failure(Validity.INCOMPLETE, context)
    if artifact.trust_class not in context.allowed_trust_classes:
        return _failure(Validity.UNSUPPORTED, context)
    if context.invalidated:
        return _failure(Validity.STALE, context)
    if artifact.artifact_digest != calculated_digest:
        return _failure(Validity.TAMPERED, context)
    return EvidenceValidationResult(
        Validity.VALID, ResultState(artifact.result_state), "",
    )
