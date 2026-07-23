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
            "risk_paths": [],
            "module_threshold": None,
            "module_roots": ["src", "packages"],
            "line_threshold": None,
            "diff_timeout_ms": 500,
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
        "spec_audit": {
            "enabled": False,
            "audit_path": "docs/spec-audit.md",
            "base_ref": "main",
            "spec_patterns": [
                "docs/*spec*.md",
                "docs/**/*spec*.md",
                "docs/*strategy*.md",
                "docs/**/*strategy*.md",
                "docs/*architecture*.md",
                "docs/**/*architecture*.md",
                "docs/*plan*.md",
                "docs/**/*plan*.md",
            ],
        },
        "tests": {"enabled": False, "browser_test_window_s": 1800},
        "mcp_trust": {"enabled": False},
        # CI must be set up before development. Default on + advisory (a
        # one-time nudge to run `fettle ci init`); mode="strict" blocks.
        "ci_bootstrap": {"enabled": True, "mode": "advisory"},
        "destructive": {
            "enabled": True,
            "mode": "advisory",
            "extra_patterns": [],
            "allow_commands": [],
        },
        "config_protect": {
            "enabled": True,
            "mode": "advisory",
            "extra_patterns": [],
            "allow_patterns": [],
        },
        "loop_detect": {
            "enabled": True,
            "threshold": 3,
            "window": 7,
        },
        "scope_creep": {
            "enabled": True,
            "warning_threshold": 15,
            "critical_threshold": 25,
            "reset_on_commit": True,
        },
        "commit_message": {
            "enabled": True,
            "mode": "advisory",
            "types": [
                "feat", "fix", "docs", "style", "refactor", "perf",
                "test", "build", "ci", "chore", "revert",
            ],
            "max_subject_length": 72,
            "require_conventional": True,
        },
        "subagent": {"enabled": True, "injection_file": "", "mode": "advisory"},
        "lean_review": {
            "enabled": True,
            "mode": "silent",
            "tier1": {
                "enabled": True,
                "max_runtime_ms": 200,
                "sniffers": {
                    "LR001_DEPENDENCY_ADDED": True,
                    "LR002_NEW_ABSTRACTION_NAME": True,
                    "LR003_PASS_THROUGH_WRAPPER": True,
                    "LR004_SINGLE_METHOD_CLASS": True,
                    "LR008_LARGE_ADDITION": True,
                    "LR012_DUPLICATE_LOCAL_HELPER_NAME": True,
                },
                "thresholds": {
                    "large_added_lines": 120,
                    "large_function_lines": 60,
                    "large_class_lines": 80,
                },
            },
            "tier2": {
                "enabled": False,
                "model": "qwen2.5-coder:7b",
                "ollama_url": "http://localhost:11434",
                "ollama_timeout_ms": 6000,
                "high_confidence_threshold": 0.85,
                "max_findings": 3,
            },
            "paths": {
                "ignore": [
                    "**/__pycache__/**", "**/.venv/**", "**/node_modules/**",
                    "**/dist/**", "**/build/**", "**/migrations/**",
                ],
            },
        },
        "advisory": {
            "cooldown_seconds": 300,
            "dedup_window_seconds": 900,
            "max_per_turn": 3,
            "max_total_bytes": 2048,
            "allow_escalation": True,
        },
        "discipline_link": {
            "enabled": True,
            "skills_path": "~/.claude/plugins/disciplines/skills",
            "cooldown_seconds": 300,
            "reminder_style": "compact",
        },
        "tdd": {
            "enabled": False,
            "mode": "advisory",
            "test_patterns": ["tests/test_*.py", "tests/**/test_*.py"],
            "implementation_roots": ["src/"],
            "exempt_paths": [
                "docs/**", "**/*.md", "**/*.toml", "**/*.yaml", "**/*.yml",
                "**/*.json", "**/*.cfg", "tests/fixtures/**",
                "**/__pycache__/**", "**/node_modules/**", "**/.venv/**", "**/dist/**",
            ],
            "accept_preexisting_tests": True,
            "path_mappings": {},
        },
        "complexity": {
            "enabled": True,
            "enforce": False,
            "max_cyclomatic": 10,
            "max_cognitive": 15,
        },
        "coverage": {
            "enabled": False,
            "threshold": 80,
            "minimum_branch_percent": 0,
            "mode": "advisory",
            "scope": "changed_lines",
            "max_staleness_seconds": 0,
        },
        "worklog": {
            "enabled": False,
            "mode": "advisory",
        },
        "bash_audit": {
            "enabled": False,
            "capture_command": False,
            "capture_exit_code": True,
            "capture_duration": True,
            "retention_days": 14,
            "redaction": {
                "enabled": True,
                "replacement": "[REDACTED]",
                "patterns": [
                    r"(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*\S+",
                    r"(?i)bearer\s+\S+",
                ],
                "fail_closed": True,
            },
        },
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
    # Boundary scan: secrets + out-of-project paths (always on) plus a
    # repo-declared forbidden-strings list (sibling projects this package
    # must not reference). Fettle ships no names — each repo fills `forbidden`.
    "boundary": {"forbidden": [], "extra_secret_patterns": []},
    # Project-local semgrep rule extension (scripts/project_rules.py).
    "rules": {
        "extra_dirs": [".fettle/rules"],  # project rule files, relative to root
        "promise_apis": [],  # extra APIs for unawaited-promise (TS/JS)
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

    configured_path = os.environ.get("FETTLE_CONFIG", "").strip()
    config_path = Path(configured_path).expanduser() if configured_path else root / CONFIG_FILENAME
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
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
