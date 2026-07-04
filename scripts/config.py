"""Fettle configuration — single source for gates, severity, and paths.

Layering (later wins): built-in defaults → `.fettle.toml` at the project root
→ environment variables. Uses stdlib tomllib (Python >= 3.11); no dependencies.

Design principles (docs/ROADMAP.md):
- Opinionated process gates (plan/UX/UI/tests/MCP) default OFF.
- Core lint gate defaults ON in advisory mode.
- FETTLE_GATE_MODE env var is an emergency global override only.
"""

import copy
import os
import tomllib
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "gates": {
        "lint": {"enabled": True, "mode": "advisory"},  # ruff + semgrep per edit
        "cross_file": {"enabled": True},  # Stop-hook import/contract checks
        "plan": {
            "enabled": False,
            "threshold": 3,
            "plan_dir": "docs",
            "plan_glob": "*plan*.md",
            "max_age_hours": 1,
        },
        "ux_spec": {
            "enabled": False,
            "frontend_paths": [
                "frontend/src/pages/", "frontend/src/components/",
                "src/pages/", "src/components/",
            ],
            "exempt": ["components/ui/", "utils/", "hooks/", "stores/", "api/",
                       "test", ".test.", ".spec."],
        },
        "ui_colors": {"enabled": False, "allowed_hex": []},
        "docs": {"enabled": False, "mode": "soft"},  # doc-update-before-push check
        "tests": {"enabled": False, "browser_test_window_s": 1800},
        "mcp_trust": {"enabled": False},
    },
    "severity": {
        "error_rules": ["BLE001", "S110", "S608", "S701"],
        "warning_prefixes": ["SIM", "UP"],
    },
    "paths": {
        "ruff_config": "",   # empty → plugin's rules/.ruff.toml
        "trace_dir": ".fettle",  # relative to project root, gitignore it
    },
    "review": {
        "provider": "claude_code",  # v0.4.0 (WP-11)
        "endpoint": "",
        "model": "",
    },
}

CONFIG_FILENAME = ".fettle.toml"


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_config(cwd: str | None = None) -> dict[str, Any]:
    """Merged config for the project at `cwd` (default: process cwd)."""
    root = Path(cwd or os.getcwd())
    cfg = copy.deepcopy(DEFAULTS)

    config_path = root / CONFIG_FILENAME
    if config_path.is_file():
        try:
            with open(config_path, "rb") as fh:
                file_cfg = tomllib.load(fh)
            cfg = _deep_merge(cfg, file_cfg)
        except (tomllib.TOMLDecodeError, OSError) as e:
            # Fail-visible: a broken config must not silently revert to defaults.
            import sys
            print(f"fettle: could not parse {config_path}: {e} — using defaults", file=sys.stderr)

    # Emergency env overrides. Mode values change how enabled gates behave;
    # "off" is the kill switch for every gate with an enabled flag.
    mode = os.environ.get("FETTLE_GATE_MODE", "").strip().lower()
    if mode in ("advisory", "soft", "enforce"):
        cfg["gates"]["lint"]["mode"] = mode
        cfg["gates"]["docs"]["mode"] = mode
    elif mode == "off":
        for gate in cfg["gates"].values():
            if "enabled" in gate:
                gate["enabled"] = False

    return cfg


def state_dir(session_id: str) -> Path:
    """Per-session state directory — no cross-session /tmp bleed.

    $FETTLE_STATE_DIR > $XDG_STATE_HOME/fettle > ~/.local/state/fettle,
    then /<session_id>/ under it.
    """
    base = os.environ.get("FETTLE_STATE_DIR")
    if not base:
        xdg = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
        base = os.path.join(xdg, "fettle")
    safe_session = "".join(c for c in (session_id or "unknown") if c.isalnum() or c in "-_") or "unknown"
    path = Path(base) / safe_session
    path.mkdir(parents=True, exist_ok=True)
    return path


def trace_path(cfg: dict[str, Any], cwd: str) -> Path:
    """Project-local trace file (findings/metrics/gate errors), gitignored."""
    trace_dir = Path(cwd) / str(cfg["paths"]["trace_dir"])
    trace_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir / "trace.jsonl"
