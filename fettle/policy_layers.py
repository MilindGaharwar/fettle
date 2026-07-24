"""WP-126: Policy layering for Fettle configuration.

Layer precedence (later wins):
    built-in defaults → org pack → team pack → repo .fettle.toml → directory overrides

Each layer is a PolicyLayer dataclass with provenance info. The resolution
functions deep-merge layers in priority order to produce a single effective
config dict, backwards-compatible with load_config()'s return format.

Usage:
    from fettle.policy_layers import load_config_layered, explain_config
    cfg = load_config_layered("/path/to/project")
"""

from __future__ import annotations

import copy
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fettle.config import DEFAULTS, CONFIG_FILENAME, _deep_merge


# ---------------------------------------------------------------------------
# Layer model
# ---------------------------------------------------------------------------

@dataclass
class PolicyLayer:
    """One layer of policy configuration with provenance metadata."""

    name: str           # "defaults", "org:acme", "team:platform", "repo", "dir:src/api"
    source: str         # file path or "built-in"
    config: dict        # the config fragment from this layer
    priority: int       # lower = applied first (defaults=0, org=10, team=20, repo=30, dir=40)


# ---------------------------------------------------------------------------
# Layer discovery
# ---------------------------------------------------------------------------

def _xdg_config_home() -> Path:
    """Return $XDG_CONFIG_HOME or ~/.config."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"))


def _load_toml(path: Path) -> dict | None:
    """Load a TOML file, returning None on missing/corrupt files."""
    if not path.is_file():
        return None
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError) as e:
        print(f"fettle: could not parse {path}: {e} — skipping layer", file=sys.stderr)
        return None


def _discover_directory_overrides(project_root: Path) -> list[PolicyLayer]:
    """Find .fettle.toml files in subdirectories (not the root itself)."""
    layers: list[PolicyLayer] = []
    for toml_path in sorted(project_root.rglob(CONFIG_FILENAME)):
        # Skip the root-level config (that's the repo layer)
        if toml_path.parent == project_root:
            continue
        # Skip hidden dirs and common noise
        rel = toml_path.parent.relative_to(project_root)
        parts = rel.parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__", ".venv") for p in parts):
            continue
        data = _load_toml(toml_path)
        if data is not None:
            dir_name = str(rel)
            layers.append(PolicyLayer(
                name=f"dir:{dir_name}",
                source=str(toml_path),
                config=data,
                priority=40,
            ))
    return layers


def discover_layers(project_root: Path) -> list[PolicyLayer]:
    """Discover all policy layers for a project, sorted by priority ascending.

    Layers:
        0  - Built-in defaults
        10 - Org pack ($XDG_CONFIG_HOME/fettle/org.toml)
        20 - Team pack ($XDG_CONFIG_HOME/fettle/team.toml)
        30 - Repo config (.fettle.toml at project root)
        40 - Directory overrides (.fettle.toml in subdirectories)
    """
    layers: list[PolicyLayer] = []

    # Built-in defaults (priority 0)
    layers.append(PolicyLayer(
        name="defaults",
        source="built-in",
        config=copy.deepcopy(DEFAULTS),
        priority=0,
    ))

    # Org pack (priority 10)
    config_home = _xdg_config_home()
    org_path = config_home / "fettle" / "org.toml"
    org_data = _load_toml(org_path)
    if org_data is not None:
        # Derive org name from config if present, else use filename
        org_name = org_data.pop("_name", "org")
        layers.append(PolicyLayer(
            name=f"org:{org_name}",
            source=str(org_path),
            config=org_data,
            priority=10,
        ))

    # Team pack (priority 20)
    team_path = config_home / "fettle" / "team.toml"
    team_data = _load_toml(team_path)
    if team_data is not None:
        team_name = team_data.pop("_name", "team")
        layers.append(PolicyLayer(
            name=f"team:{team_name}",
            source=str(team_path),
            config=team_data,
            priority=20,
        ))

    # Repo config (priority 30)
    repo_path = project_root / CONFIG_FILENAME
    repo_data = _load_toml(repo_path)
    if repo_data is not None:
        layers.append(PolicyLayer(
            name="repo",
            source=str(repo_path),
            config=repo_data,
            priority=30,
        ))

    # Directory overrides (priority 40)
    layers.extend(_discover_directory_overrides(project_root))

    # Sort by priority (stable — preserves discovery order within same priority)
    layers.sort(key=lambda layer: layer.priority)
    return layers


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_config(layers: list[PolicyLayer]) -> dict:
    """Deep-merge all layers in priority order. Later layers win."""
    result: dict = {}
    for layer in sorted(layers, key=lambda lyr: lyr.priority):
        result = _deep_merge(result, layer.config)
    return result


def resolve_config_for_path(
    layers: list[PolicyLayer],
    file_path: str,
    project_root: Path,
) -> dict:
    """Resolve config including only directory overrides that match file_path.

    Directory override layers (priority 40) are included only when file_path
    is within the directory that defines the override.
    """
    try:
        rel_file = Path(file_path).relative_to(project_root)
    except ValueError:
        # file_path is not under project_root — try as already-relative
        rel_file = Path(file_path)

    applicable: list[PolicyLayer] = []
    for layer in layers:
        if layer.priority < 40:
            applicable.append(layer)
        else:
            # Directory override: include only if file is within that dir
            dir_prefix = layer.name.removeprefix("dir:")
            if str(rel_file).startswith(dir_prefix + "/") or str(rel_file) == dir_prefix:
                applicable.append(layer)

    return resolve_config(applicable)


# ---------------------------------------------------------------------------
# Provenance tracking
# ---------------------------------------------------------------------------

def _get_nested(d: dict, key_path: str) -> tuple[bool, Any]:
    """Traverse a dict by dotted key path. Returns (found, value)."""
    keys = key_path.split(".")
    current = d
    for key in keys:
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
    for layer in sorted(layers, key=lambda lyr: lyr.priority):
        found, value = _get_nested(layer.config, key_path)
        if found:
            results.append({"layer": layer.name, "value": value})
    return results


# ---------------------------------------------------------------------------
# Signed bundles (stub)
# ---------------------------------------------------------------------------

def verify_bundle(bundle_path: Path) -> bool:
    """Verify a policy bundle file is valid TOML with expected structure.

    Currently checks:
    - File exists
    - Valid TOML
    - Contains a `_signed` field (cryptographic verification is future work)

    Returns True if valid, False otherwise.
    """
    if not bundle_path.is_file():
        return False
    try:
        with open(bundle_path, "rb") as fh:
            data = tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError):
        return False

    # Must contain _signed field (actual crypto verification is future work)
    return "_signed" in data


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

def cmd_policy(args: list[str]) -> None:
    """CLI entry point for `fettle config --print-effective --explain`.

    args: list of CLI arguments (after `fettle config`).
    """
    import argparse

    parser = argparse.ArgumentParser(prog="fettle config", description="Show effective configuration")
    parser.add_argument("--print-effective", action="store_true", help="Print the resolved config")
    parser.add_argument("--explain", action="store_true", help="Show provenance for each key")
    parser.add_argument("--project", default=os.getcwd(), help="Project root (default: cwd)")
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project)
    layers = discover_layers(project_root)

    if parsed.explain:
        _print_explain(layers)
    elif parsed.print_effective:
        _print_effective(layers)
    else:
        parser.print_help()


def _print_effective(layers: list[PolicyLayer]) -> None:
    """Print the fully resolved config."""
    import json
    config = resolve_config(layers)
    print(json.dumps(config, indent=2))


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
# Integration with existing config.py (backwards-compatible entry point)
# ---------------------------------------------------------------------------

def load_config_layered(cwd: str | None = None) -> dict[str, Any]:
    """Layered config loader — drop-in replacement for config.load_config().

    Returns the same dict format as load_config() for backwards compatibility.
    Projects without org/team packs get identical behavior to before.
    """
    root = Path(cwd or os.getcwd())
    layers = discover_layers(root)
    cfg = resolve_config(layers)

    # Apply the same env var overrides as load_config() for consistency
    mode = os.environ.get("FETTLE_GATE_MODE", "").strip().lower()
    if mode in ("advisory", "soft", "enforce"):
        cfg["gates"]["lint"]["mode"] = mode
        cfg["gates"]["docs"]["mode"] = mode
    elif mode == "off":
        for gate in cfg["gates"].values():
            if isinstance(gate, dict) and "enabled" in gate:
                gate["enabled"] = False

    return cfg
