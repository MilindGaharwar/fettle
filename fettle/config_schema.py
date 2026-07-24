"""WP-142 — Config schema v1: validation + published JSON Schema.

Both are DERIVED from `config.DEFAULTS`, so the schema cannot drift from the
code (a test asserts docs/fettle.schema.json matches the generator output).

Validation rules:
- Unknown key at any level  -> warning (typo'd keys silently doing nothing is
  the classic config failure mode)
- Type mismatch vs default  -> error (bool != int; int/float interchangeable)
- `None` defaults           -> unconstrained (e.g. plan.module_threshold)
- Open dicts (arbitrary keys by design, e.g. tdd.path_mappings) -> any keys
- Empty-list defaults       -> any item types
"""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.config import DEFAULTS  # noqa: E402

SCHEMA_VERSION = 1

#: Dict paths whose keys are user-defined by design.
OPEN_DICT_PATHS = frozenset({
    "gates.tdd.path_mappings",
})

_MODE_VALUES = {"advisory", "soft", "enforce", "silent", "strict",
                "none", "marker", "manifest", "commit", "off"}


def _type_name(value: Any) -> str:
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
    return "any"


def _compatible(default: Any, value: Any) -> bool:
    if default is None:
        return True
    if isinstance(default, bool) or isinstance(value, bool):
        return isinstance(default, bool) and isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float))
    return isinstance(value, type(default))


def validate_config(user_cfg: dict[str, Any],
                    defaults: dict[str, Any] | None = None,
                    ) -> tuple[list[str], list[str]]:
    """Validate a raw .fettle.toml dict. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    _walk(user_cfg, defaults if defaults is not None else DEFAULTS, "", errors, warnings)
    return errors, warnings


def _walk(user: dict[str, Any], defaults: dict[str, Any], path: str,
          errors: list[str], warnings: list[str]) -> None:
    for key, value in user.items():
        key_path = f"{path}.{key}" if path else key
        if key not in defaults:
            warnings.append(
                f"unknown key '{key_path}' — not a Fettle setting (typo?); it has no effect"
            )
            continue
        default = defaults[key]
        if isinstance(default, dict):
            if not isinstance(value, dict):
                errors.append(
                    f"'{key_path}' must be a table (got {_type_name(value)})"
                )
            elif key_path in OPEN_DICT_PATHS:
                continue  # arbitrary keys by design
            else:
                _walk(value, default, key_path, errors, warnings)
            continue
        if not _compatible(default, value):
            errors.append(
                f"'{key_path}' must be {_type_name(default)} "
                f"(got {_type_name(value)}: {value!r})"
            )
            continue
        if key == "mode" and isinstance(value, str) and value not in _MODE_VALUES:
            warnings.append(
                f"'{key_path}' value {value!r} is not a known mode "
                f"({', '.join(sorted(_MODE_VALUES))})"
            )


def generate_json_schema(defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Emit a JSON Schema (draft 2020-12) for .fettle.toml, derived from DEFAULTS."""
    root = _node_schema(defaults if defaults is not None else DEFAULTS, "")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/MilindGaharwar/fettle/blob/main/docs/fettle.schema.json",
        "title": "Fettle configuration (.fettle.toml)",
        "description": (
            f"Schema v{SCHEMA_VERSION}, generated from fettle.config.DEFAULTS. "
            "Validate locally with: fettle config --validate"
        ),
        "x-fettle-schema-version": SCHEMA_VERSION,
        **root,
    }


def _node_schema(value: Any, path: str) -> dict[str, Any]:
    if isinstance(value, dict):
        if path in OPEN_DICT_PATHS:
            return {"type": "object", "additionalProperties": True}
        return {
            "type": "object",
            "properties": {
                k: _node_schema(v, f"{path}.{k}" if path else k)
                for k, v in value.items()
            },
            "additionalProperties": False,
        }
    if isinstance(value, bool):
        return {"type": "boolean", "default": value}
    if isinstance(value, int):
        return {"type": "integer", "default": value}
    if isinstance(value, float):
        return {"type": "number", "default": value}
    if isinstance(value, str):
        schema: dict[str, Any] = {"type": "string", "default": value}
        if path.endswith(".mode"):
            schema["enum"] = sorted(_MODE_VALUES)
        return schema
    if isinstance(value, list):
        item_types = {_type_name(v) for v in value}
        schema = {"type": "array"}
        if len(item_types) == 1:
            schema["items"] = {"type": item_types.pop()}
        if value:
            schema["default"] = value
        return schema
    return {}  # None default: unconstrained
