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

WP4 (Stage 2) — dependency model. Three declarative tables keyed by dotted
path, consumed by BOTH validate_config and generate_json_schema:
- MODE_ENUMS: the modes each gate's code actually honors -> error otherwise
  (a mode outside the set silently acts as some other mode — e.g.
  tdd.mode="enforce" behaves as advisory — which is an invalid config state).
- RANGES: numeric bounds -> error outside them.
- DEPENDENCIES: cross-field rules evaluated on the defaults-merged view ->
  error when the config would misbehave, warning when a feature is inert.
"""

from __future__ import annotations

import os
import re
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

#: WP4 — per-gate mode vocabulary: exactly the values each gate's code honors.
#: ("off" is deliberately absent everywhere: the kill switch is enabled=false;
#: mode="off" is treated as a non-advisory mode by blocking gates.)
MODE_ENUMS: dict[str, frozenset[str]] = {
    "gates.lint.mode": frozenset({"advisory", "soft", "enforce"}),
    "gates.docs.mode": frozenset({"advisory", "soft", "enforce"}),
    "gates.ci_bootstrap.mode": frozenset({"advisory", "strict"}),
    "gates.destructive.mode": frozenset({"advisory", "enforce"}),
    "gates.config_protect.mode": frozenset({"advisory", "enforce"}),
    "gates.commit_message.mode": frozenset({"advisory", "enforce"}),
    "gates.subagent.mode": frozenset({"advisory", "enforce"}),
    "gates.lean_review.mode": frozenset({"silent", "advisory"}),
    "gates.tdd.mode": frozenset({"advisory", "strict"}),
    "gates.bdd.mode": frozenset({"advisory", "enforce"}),
    "gates.coverage.mode": frozenset({"advisory", "enforce"}),
    "gates.deploy_safety.mode": frozenset({"advisory", "enforce"}),
    "gates.release.mode": frozenset({"advisory", "enforce"}),
    "gates.artifact_integrity.mode": frozenset({"advisory", "enforce"}),
    "gates.provenance.mode": frozenset({"none", "marker", "manifest", "commit"}),
    "gates.worklog.mode": frozenset({"advisory", "enforce"}),
}

#: WP4 — numeric bounds: (min, max), None = unbounded on that side.
RANGES: dict[str, tuple[float | None, float | None]] = {
    "gates.plan.threshold": (1, None),
    "gates.plan.max_age_hours": (1, None),
    "gates.plan.diff_timeout_ms": (1, None),
    "gates.loop_detect.threshold": (1, None),
    "gates.loop_detect.window": (1, None),
    "gates.scope_creep.warning_threshold": (1, None),
    "gates.scope_creep.critical_threshold": (1, None),
    "gates.commit_message.max_subject_length": (1, None),
    "gates.coverage.threshold": (0, 100),
    "gates.coverage.minimum_branch_percent": (0, 100),
    "gates.coverage.max_staleness_seconds": (0, None),
    "gates.complexity.max_cyclomatic": (1, None),
    "gates.complexity.max_cognitive": (1, None),
    "gates.advisory.cooldown_seconds": (0, None),
    "gates.advisory.dedup_window_seconds": (0, None),
    "gates.advisory.max_per_turn": (0, None),
    "gates.advisory.max_total_bytes": (0, None),
    "gates.discipline_link.cooldown_seconds": (0, None),
    "gates.tests.browser_test_window_s": (0, None),
    "gates.bash_audit.retention_days": (1, None),
    "gates.lean_review.tier1.max_runtime_ms": (1, None),
    "gates.lean_review.tier2.ollama_timeout_ms": (1, None),
    "gates.lean_review.tier2.high_confidence_threshold": (0, 1),
    "gates.lean_review.tier2.max_findings": (1, None),
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _dep_extends_pin(cfg: dict[str, Any]) -> str | None:
    ext = cfg.get("extends", {})
    url = str(ext.get("url", ""))
    if not url:
        return None
    sha = str(ext.get("sha256", "")).lower()
    if not _SHA256_RE.match(sha):
        return ("'extends.url' is set but 'extends.sha256' is not a 64-char hex "
                "digest — the pin is what makes remote policy safe; policy sync "
                "will refuse to apply it")
    return None


def _dep_boundaries_rules(cfg: dict[str, Any]) -> str | None:
    gate = cfg["gates"]["architecture_boundaries"]
    if gate.get("enabled") and not gate.get("rules"):
        return ("'gates.architecture_boundaries' is enabled with no rules — "
                "the gate is inert; add rules or disable it")
    return None


def _dep_tier2_backend(cfg: dict[str, Any]) -> str | None:
    tier2 = cfg["gates"]["lean_review"]["tier2"]
    if tier2.get("enabled") and not (str(tier2.get("model", "")).strip()
                                     and str(tier2.get("ollama_url", "")).strip()):
        return ("'gates.lean_review.tier2' is enabled but 'model' or 'ollama_url' "
                "is empty — tier2 can never run")
    return None


def _dep_ui_palette(cfg: dict[str, Any]) -> str | None:
    gate = cfg["gates"]["ui_colors"]
    if gate.get("enabled") and not gate.get("allowed_hex"):
        return ("'gates.ui_colors' is enabled with an empty 'allowed_hex' — every "
                "hardcoded color will be flagged; set your palette or confirm intent")
    return None


def _dep_tdd_roots(cfg: dict[str, Any]) -> str | None:
    gate = cfg["gates"]["tdd"]
    if gate.get("enabled") and not gate.get("implementation_roots"):
        return ("'gates.tdd' is enabled with empty 'implementation_roots' — no "
                "file counts as implementation, so the gate is inert")
    return None


#: WP4 — cross-field rules: (trigger_path, check(merged_cfg) -> msg|None, severity).
#: severity "error" = config would misbehave; "warning" = feature is inert or
#: an unusual-but-coherent policy.
DEPENDENCIES: tuple[tuple[str, Any, str], ...] = (
    ("extends.url", _dep_extends_pin, "error"),
    ("gates.architecture_boundaries.enabled", _dep_boundaries_rules, "warning"),
    ("gates.lean_review.tier2.enabled", _dep_tier2_backend, "warning"),
    ("gates.ui_colors.enabled", _dep_ui_palette, "warning"),
    ("gates.tdd.enabled", _dep_tdd_roots, "warning"),
)


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
    """Validate a raw .fettle.toml dict. Returns (errors, warnings).

    Dependency rules run on the defaults-merged view of the file, so a rule
    can rely on default values the user didn't override. (Org policy layers
    are not resolved here — validation is static and network-free.)
    """
    errors: list[str] = []
    warnings: list[str] = []
    base = defaults if defaults is not None else DEFAULTS
    _walk(user_cfg, base, "", errors, warnings)
    if base is DEFAULTS and not errors:
        # dependency rules are written against real DEFAULTS paths and assume
        # a structurally valid file (structural errors already fail validation)
        from fettle.config import _deep_merge
        merged = _deep_merge(DEFAULTS, user_cfg)
        for _trigger, check, severity in DEPENDENCIES:
            msg = check(merged)
            if msg:
                (errors if severity == "error" else warnings).append(msg)
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
        if key_path in MODE_ENUMS and isinstance(value, str):
            allowed = MODE_ENUMS[key_path]
            if value not in allowed:
                errors.append(
                    f"'{key_path}' value {value!r} is not a mode this gate honors "
                    f"({', '.join(sorted(allowed))}) — it would silently behave "
                    f"as another mode"
                )
            continue
        if key == "mode" and isinstance(value, str) and value not in _MODE_VALUES:
            warnings.append(
                f"'{key_path}' value {value!r} is not a known mode "
                f"({', '.join(sorted(_MODE_VALUES))})"
            )
            continue
        if key_path in RANGES and isinstance(value, (int, float)) and not isinstance(value, bool):
            lo, hi = RANGES[key_path]
            if (lo is not None and value < lo) or (hi is not None and value > hi):
                bound = (f">= {lo}" if hi is None else f"<= {hi}" if lo is None
                         else f"between {lo} and {hi}")
                errors.append(f"'{key_path}' must be {bound} (got {value!r})")


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
        schema_i: dict[str, Any] = {"type": "integer", "default": value}
        _apply_range(schema_i, path)
        return schema_i
    if isinstance(value, float):
        schema_f: dict[str, Any] = {"type": "number", "default": value}
        _apply_range(schema_f, path)
        return schema_f
    if isinstance(value, str):
        schema: dict[str, Any] = {"type": "string", "default": value}
        if path in MODE_ENUMS:
            schema["enum"] = sorted(MODE_ENUMS[path])
        elif path.endswith(".mode"):
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


def _apply_range(schema: dict[str, Any], path: str) -> None:
    if path in RANGES:
        lo, hi = RANGES[path]
        if lo is not None:
            schema["minimum"] = lo
        if hi is not None:
            schema["maximum"] = hi
