"""Typed, value-redacting comparators for state-consistency observations."""

from __future__ import annotations

import hashlib
import json
import unicodedata


class ComparisonError(ValueError):
    """Raised when a value cannot be compared without ambiguity."""


def _normalize(value: object) -> object:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ComparisonError("JSON object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ComparisonError("object keys resolve to the same NFC form")
            normalized[normalized_key] = _normalize(item)
        return normalized
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise ComparisonError(f"unsupported observation type: {type(value).__name__}")


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise ComparisonError(f"unsupported observation type: {type(value).__name__}")


def fingerprint_value(value: object, comparator_kind: str) -> str:
    """Return a typed fingerprint without retaining the compared value."""
    if comparator_kind == "exact":
        comparable = value
    elif comparator_kind == "normalized":
        comparable = _normalize(value)
    else:
        raise ComparisonError(f"unsupported comparator: {comparator_kind}")
    try:
        encoded = json.dumps(
            {"type": _json_type(comparable), "value": comparable},
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ComparisonError("observation is not canonical JSON") from exc
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
