"""Fettle configuration — single source for gates, severity, and paths.

Canonical layering (later wins, WP-20 unified resolver):
    defaults → org.toml → team.toml → remote [extends] → repo .fettle.toml
            → directory overrides (path-scoped) → env → capsule (tighten-only)

Directory `.fettle.toml` overrides apply only when a caller resolves for a
specific file (`load_config(cwd, for_path=...)`); pathless callers resolve
at root scope. Uses stdlib tomllib (Python >= 3.11); no dependencies.

Design principles (docs/ROADMAP.md, docs/engagement/17):
- Opinionated process gates (plan/UX/UI/tests/MCP) default OFF.
- Core lint gate defaults ON in advisory mode.
- FETTLE_GATE_MODE env var is an emergency global override only.
- Inspection (`fettle config`) and runtime share this one resolver.
"""

import copy
import os
import sys
import tomllib
from dataclasses import dataclass
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
            "exclude": [],
            "max_age_hours": 1,
            # v1.6: accept active session plans (.fettle/plans/) too.
            "session_plans": True,
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
        # doc-update-before-push check. "soft" is a deprecated alias for
        # "enforce" (any non-advisory mode blocks) — kept one release (WP9).
        "docs": {"enabled": False, "mode": "enforce"},
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
        # allowlist_path, when set via policy, pins the trust root and makes
        # the MCP_ALLOWLIST_PATH env override inert (WP-4c).
        "mcp_trust": {"enabled": False, "allowlist_path": ""},
        # CI must be set up before development. Default on + advisory (a
        # one-time nudge to run `fettle ci init`); mode="strict" blocks.
        "ci_bootstrap": {"enabled": True, "mode": "advisory"},
        "destructive": {
            "enabled": True,
            "mode": "advisory",
            "extra_patterns": [],
            "allow_commands": [],
        },
        # Nested agent launches must go through `fettle spawn` (WP-157).
        "agent_spawn": {"enabled": True, "mode": "advisory"},
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
        "subagent": {"enabled": True, "injection_file": ""},
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
        # Stage 3 (S3.3): scenario-coverage gate over living specs. An edited
        # impl file inside an active spec's scope requires every scenario of
        # that spec to have a trace-marked test. Deterministic; no test runs.
        "bdd": {
            "enabled": False,
            "mode": "advisory",
        },
        # Stage 4 (S4.3): claim-before-work in fettle-managed worktrees
        # (Wayfinder invariant). Main-worktree edits always exempt.
        "claims": {
            "enabled": False,
            "mode": "advisory",
        },
        # Stage 7 (S7.1, closes WP2): functional test verification. The Stop
        # gate demands a fresh green `fettle verify` stamp for sessions that
        # edited code; `fettle verify` runs the discovered test command
        # (scope: impacted subset via edit tracking, or full suite).
        "verify": {
            "enabled": False,
            "mode": "advisory",
            "scope": "impacted",
            "timeout_s": 120,
            "parallel": False,
        },
        # Stage 8: remote CI verification. A `git push` this session demands
        # a fresh green CI verdict for the pushed sha before Stop; the
        # verdict is fetched by `fettle ci status|wait` (never by the gate).
        "ci": {
            "enabled": False,
            "mode": "advisory",
            "timeout_s": 900,
            "poll_s": 15,
        },
        "complexity": {
            "enabled": True,
            "mode": "advisory",
            # Deprecated: `enforce = true` behaves as mode = "enforce" (WP9).
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
        "deploy_safety": {
            "enabled": False,
            "mode": "advisory",
            "require_tests": True,
            "require_changelog": False,
            "require_health_endpoint": True,
            "check_debug_flags": True,
        },
        "release": {
            "enabled": False,
            "mode": "advisory",
            "changelog_path": "CHANGELOG.md",
            "require_semver": True,
            "check_breaking_changes": True,
        },
        "architecture_boundaries": {
            "enabled": False,
            "rules": [],
        },
        "artifact_integrity": {
            "enabled": False,
            "mode": "advisory",
        },
        "provenance": {
            "enabled": False,
            "mode": "none",
            "marker_text": "",
            "exempt_paths": [
                "**/*.json", "**/*.lock", "**/migrations/**", "**/*.generated.*",
            ],
        },
        "worklog": {
            "enabled": False,
            "mode": "advisory",
            # "daily": today's entry suffices. "session": the entry must
            # have been updated during this session (v1.6 slice A).
            "scope": "daily",
        },
        # v1.6 slice C: at Stop, write a structured completion report to
        # .fettle/reports/<session>.json (files edited, claims, stamps,
        # planned-vs-done) for orchestrators/integrators. Never blocks.
        "session_report": {
            "enabled": False,
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
    "profile": {
        "test_command": "",
        "lint_command": "",
        "format_command": "",
        "typecheck_command": "",
        "build_command": "",
        "workspaces": [],
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
    "boundary": {"forbidden": [], "exclude": [], "extra_secret_patterns": []},
    # Project-local semgrep rule extension (scripts/project_rules.py).
    "rules": {
        "extra_dirs": [".fettle/rules"],  # project rule files, relative to root
        "promise_apis": [],  # extra APIs for unawaited-promise (TS/JS)
    },
    # WP-144: central policy distribution — digest-pinned org policy layered
    # UNDER this repo's config (defaults → org → repo → env). Cache-only in
    # hooks; `fettle policy sync` fetches.
    "extends": {"url": "", "sha256": ""},
    # WP-148: opt-in telemetry — anonymous counters only, default OFF.
    # `enabled` is honored ONLY from the digest-pinned org policy ([extends]);
    # setting it in a repo's .fettle.toml is ignored and surfaced.
    "telemetry": {"enabled": False, "endpoint": ""},
    # WP-14b: external tool adapters, run via `fettle integrations`. All
    # default OFF; tokens come from env vars (never from config). The keys
    # mirror exactly what each adapter reads.
    "integrations": {
        "sonarqube": {
            "enabled": False,
            "endpoint": "",           # https:// required unless allow_insecure
            "project_key": "",
            "token_env": "SONAR_TOKEN",
            "allow_insecure": False,
        },
        "blackduck": {
            "enabled": False,
            "cli_path": "polaris",
            "token_env": "POLARIS_TOKEN",
            "scan_timeout_s": 300,
        },
        "pact": {
            "enabled": False,
            "broker_url": "",         # https:// required unless allow_insecure
            "token_env": "PACT_BROKER_TOKEN",
            "allow_insecure": False,
        },
    },
    # WP7 (Stage 4): worktree spine — one worktree per work item, branch
    # fettle/<item-id>. Root is inside the checkout (gitignored, scanners
    # skip .fettle).
    # require=true gates main-worktree edits (WP-162): non-exempt edits get
    # "create a work-item worktree first", honoring gates.claims.mode.
    "worktrees": {
        "root": ".fettle/worktrees",
        "require": False,
        "exempt_paths": ["docs/**", "**/*.md"],
    },
    # WP3 (Stage 5): agentic UAT — independent acceptance layer. Surfaces:
    # auto-detected (cli/api/web/library) unless listed explicitly. mode is
    # report-only in this stage.
    "uat": {
        "surfaces": ["auto"],
        "app_url": "",
        "start_command": "",
        "runner": "claude",
        "timeout_s": 1800,
        "mode": "report",
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


@dataclass
class PolicyLayer:
    """One layer of policy configuration with provenance metadata.

    List order IS the precedence order (later layers win). Env and capsule
    appear as pseudo-layers whose `config` is the *applied* diff.
    """

    name: str    # "defaults", "org:acme", "team:platform", "remote", "repo", "dir:src/api", "env:FETTLE_GATE_MODE", "capsule"
    source: str  # file path, env var name, or "built-in"
    config: dict


_DIR_NOISE = ("node_modules", "__pycache__", ".venv")


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"))


def _load_toml_layer(path: Path) -> dict | None:
    """Load one layer file. Missing → None; corrupt → fail-visible skip."""
    if not path.is_file():
        return None
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError) as e:
        print(f"fettle: could not parse {path}: {e} — skipping layer", file=sys.stderr)
        return None


def _ancestor_dir_layers(root: Path, for_path: str) -> list[PolicyLayer]:
    """Directory-override layers applicable to `for_path`.

    Walks ancestors of the file from the repo root down (deeper wins) —
    O(depth) stat calls, never a tree scan, so hooks stay fast. Hidden and
    noise directories end the walk (their configs never apply).
    """
    p = Path(for_path)
    if not p.is_absolute():
        p = root / p
    try:
        rel = p.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return []
    layers: list[PolicyLayer] = []
    current = root
    for part in rel.parts[:-1]:  # directory components only
        if part.startswith(".") or part in _DIR_NOISE:
            break
        current = current / part
        data = _load_toml_layer(current / CONFIG_FILENAME)
        if data is not None:
            layers.append(PolicyLayer(
                name=f"dir:{current.relative_to(root)}",
                source=str(current / CONFIG_FILENAME),
                config=data,
            ))
    return layers


def _dict_diff(before: dict, after: dict) -> dict:
    """Nested fragment of keys whose values differ between two dicts."""
    out: dict = {}
    for key, val in after.items():
        if isinstance(val, dict) and isinstance(before.get(key), dict):
            sub = _dict_diff(before[key], val)
            if sub:
                out[key] = sub
        elif key not in before or before[key] != val:
            out[key] = copy.deepcopy(val)
    return out


def resolve_with_provenance(
    cwd: str | None = None, for_path: str | None = None
) -> tuple[dict[str, Any], list[PolicyLayer]]:
    """Canonical resolution with per-layer provenance (WP-20).

    Returns (effective_config, layers). `load_config()` is this minus the
    provenance — inspection and runtime cannot diverge.
    """
    root = Path(cwd or os.getcwd())
    layers = [PolicyLayer("defaults", "built-in", copy.deepcopy(DEFAULTS))]

    # Org / team packs ($XDG_CONFIG_HOME/fettle/{org,team}.toml).
    packs_dir = _xdg_config_home() / "fettle"
    for kind in ("org", "team"):
        pack_path = packs_dir / f"{kind}.toml"
        data = _load_toml_layer(pack_path)
        if data is not None:
            name = data.pop("_name", kind)
            layers.append(PolicyLayer(f"{kind}:{name}", str(pack_path), data))

    # Repo config (.fettle.toml at root, or $FETTLE_CONFIG).
    configured_path = os.environ.get("FETTLE_CONFIG", "").strip()
    config_path = Path(configured_path).expanduser() if configured_path else root / CONFIG_FILENAME
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    repo_data = _load_toml_layer(config_path)

    # WP-144: central policy (cache-only — never network in the hook path)
    # is keyed off the repo's [extends] and merges UNDER it, over team.
    if repo_data and repo_data.get("extends"):
        from fettle.policy_remote import resolve_cached_policy
        remote_cfg = resolve_cached_policy(repo_data)
        if remote_cfg:
            ext = repo_data.get("extends")
            url = ext.get("url", "") if isinstance(ext, dict) else ""
            layers.append(PolicyLayer("remote", url or "[extends] cache", remote_cfg))
    if repo_data is not None:
        layers.append(PolicyLayer("repo", str(config_path), repo_data))

    # Directory overrides — path-scoped resolution only.
    if for_path:
        layers.extend(_ancestor_dir_layers(root, for_path))

    cfg: dict = {}
    for layer in layers:
        cfg = _deep_merge(cfg, layer.config)

    # Emergency env overrides. Mode values change how enabled gates behave;
    # "off" is the kill switch for every gate with an enabled flag.
    mode = os.environ.get("FETTLE_GATE_MODE", "").strip().lower()
    if mode in ("advisory", "soft", "enforce", "off"):
        before = copy.deepcopy(cfg)
        if mode == "off":
            for gate in cfg["gates"].values():
                if isinstance(gate, dict) and "enabled" in gate:
                    gate["enabled"] = False
        else:
            cfg["gates"]["lint"]["mode"] = mode
            cfg["gates"]["docs"]["mode"] = mode
        diff = _dict_diff(before, cfg)
        if diff:
            layers.append(PolicyLayer("env:FETTLE_GATE_MODE", f"FETTLE_GATE_MODE={mode}", diff))

    # Stage A (A3): delegated policy capsule — a verified capsule handed
    # down by a parent session merges OVER everything local, monotonically
    # stricter (children may only tighten). Applied after env handling so
    # kill-switch env vars cannot weaken delegated policy (design 12, D-A3).
    from fettle.policy_capsule import ENV_VAR as CAPSULE_ENV, apply_env_capsule
    before = cfg
    cfg = apply_env_capsule(cfg)
    diff = _dict_diff(before, cfg)
    if diff:
        layers.append(PolicyLayer("capsule", CAPSULE_ENV, diff))

    return cfg, layers


def load_config(cwd: str | None = None, for_path: str | None = None) -> dict[str, Any]:
    """Merged config for the project at `cwd` (default: process cwd).

    Pass `for_path` (a file the caller is gating) to include directory
    `.fettle.toml` overrides on the file's ancestor chain.
    """
    return resolve_with_provenance(cwd, for_path)[0]


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
