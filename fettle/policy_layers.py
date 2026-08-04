"""Provenance and explain engine over the unified config resolver (WP-20).

The canonical resolver lives in fettle.config (`load_config` /
`resolve_with_provenance`): defaults → org → team → remote [extends] → repo
→ directory overrides (path-scoped) → env → capsule. This module renders
that resolution: which layer set which key, and what each layer overrode.

Usage:
    from fettle.config import resolve_with_provenance
    from fettle.policy_layers import explain_config

    cfg, layers = resolve_with_provenance("/path/to/project")
    explain_config(layers, "gates.lint.mode")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fettle.config import (
    CONFIG_FILENAME,
    PolicyLayer,
    _deep_merge,
    _load_toml_layer,
    load_config,
    resolve_with_provenance,
)

_DIR_NOISE = ("node_modules", "__pycache__", ".venv")


def discover_layers(project_root: Path) -> list[PolicyLayer]:
    """All layers that apply at root scope, in precedence order.

    Delegates to the canonical resolver; includes env/capsule pseudo-layers
    (their `config` is the applied diff). Directory overrides are excluded —
    they only apply on path-scoped resolution (see
    `discover_directory_layers` for listing them).
    """
    return resolve_with_provenance(str(project_root))[1]


def discover_directory_layers(project_root: Path) -> list[PolicyLayer]:
    """Directory-override `.fettle.toml` files present in the tree.

    Inspection-only (rglob) — at runtime these layers are picked up via the
    O(depth) ancestor walk when a gate resolves with `for_path`.
    """
    layers: list[PolicyLayer] = []
    for toml_path in sorted(project_root.rglob(CONFIG_FILENAME)):
        if toml_path.parent == project_root:
            continue  # the repo layer, not a directory override
        rel = toml_path.parent.relative_to(project_root)
        if any(p.startswith(".") or p in _DIR_NOISE for p in rel.parts):
            continue
        data = _load_toml_layer(toml_path)
        if data is not None:
            layers.append(PolicyLayer(name=f"dir:{rel}", source=str(toml_path), config=data))
    return layers


def resolve_config(layers: list[PolicyLayer]) -> dict:
    """Deep-merge layers in list order. Later layers win."""
    result: dict = {}
    for layer in layers:
        result = _deep_merge(result, layer.config)
    return result


# ---------------------------------------------------------------------------
# Provenance rendering
# ---------------------------------------------------------------------------

def _get_nested(d: dict, key_path: str) -> tuple[bool, Any]:
    """Traverse a dict by dotted key path. Returns (found, value)."""
    current = d
    for key in key_path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return False, None
    return True, current


def explain_config(layers: list[PolicyLayer], key_path: str) -> list[dict]:
    """Show which layers set a given config key (dotted path).

    Returns a list of dicts: [{"layer": name, "value": value}, ...]
    The last entry is the effective (winning) value.
    """
    results: list[dict] = []
    for layer in layers:
        found, value = _get_nested(layer.config, key_path)
        if found:
            results.append({"layer": layer.name, "value": value})
    return results


def _print_explain(layers: list[PolicyLayer]) -> None:
    """Print each config key with its provenance chain."""
    config = resolve_config(layers)
    _explain_dict(layers, config, prefix="")


def _explain_dict(layers: list[PolicyLayer], d: dict, prefix: str) -> None:
    """Recursively explain all keys in a dict."""
    for key, value in sorted(d.items()):
        key_path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            _explain_dict(layers, value, key_path)
        else:
            provenance = explain_config(layers, key_path)
            if len(provenance) > 1:
                effective = provenance[-1]
                overridden = provenance[-2]
                print(
                    f"{key_path} = {_fmt_value(effective['value'])} "
                    f"({effective['layer']}, overrides {overridden['layer']}: "
                    f"{_fmt_value(overridden['value'])})"
                )
            elif provenance:
                effective = provenance[0]
                print(f"{key_path} = {_fmt_value(effective['value'])} ({effective['layer']})")


def _fmt_value(value: Any) -> str:
    """Format a value for display."""
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return f"[{len(value)} items]"
    return repr(value)


# ---------------------------------------------------------------------------
# Deprecated alias (kept one release, WP-20)
# ---------------------------------------------------------------------------

def load_config_layered(cwd: str | None = None) -> dict[str, Any]:
    """Deprecated: use fettle.config.load_config — the resolvers are unified."""
    return load_config(cwd)


__all__ = [
    "PolicyLayer",
    "discover_layers",
    "discover_directory_layers",
    "resolve_config",
    "explain_config",
    "load_config_layered",
]
