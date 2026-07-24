"""Fettle v0.5.0 — WP-73: Configuration and enforcement policy.

Extends the v0.4.0 config system with tier policies, per-checker config,
suppressions with expiry, and path exclusions. Layered: defaults -> repo
.fettle.toml -> CLI overrides.
"""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


KNOWN_CHECKERS = {"ruff", "semgrep", "pyright", "mypy", "deptry", "gitleaks", "eslint", "biome", "cargo", "golangci-lint"}


@dataclass
class TierPolicy:
    """Policy for a single enforcement tier."""

    timeout_s: float = 15.0
    blocking: bool = True
    checkers: list[str] = field(default_factory=list)

    def merge(self, overrides: dict[str, Any]) -> None:
        if "timeout_s" in overrides:
            self.timeout_s = overrides["timeout_s"]
        if "blocking" in overrides:
            self.blocking = overrides["blocking"]
        if "checkers" in overrides:
            self.checkers = overrides["checkers"]


@dataclass
class CheckerConfig:
    """Per-checker configuration."""

    name: str
    enabled: bool = True
    severity: str = "error"
    timeout_s: float = 30.0


DEFAULT_POLICY = {
    "fast": {"timeout_s": 15, "blocking": True, "checkers": ["ruff", "semgrep"]},
    "changed": {"timeout_s": 90, "blocking": True, "checkers": ["ruff", "semgrep", "pyright", "deptry"]},
    "full": {"timeout_s": 300, "blocking": True, "checkers": []},
    "ci": {"timeout_s": 600, "blocking": True, "checkers": []},
}


@dataclass
class PolicyConfig:
    """Complete v0.5.0 policy configuration."""

    fast: TierPolicy = field(default_factory=lambda: TierPolicy(timeout_s=15))
    changed: TierPolicy = field(default_factory=lambda: TierPolicy(timeout_s=90))
    full: TierPolicy = field(default_factory=lambda: TierPolicy(timeout_s=300))
    ci: TierPolicy = field(default_factory=lambda: TierPolicy(timeout_s=600))
    checkers: dict[str, CheckerConfig] = field(default_factory=dict)
    suppressions: list[dict[str, Any]] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config_error: str = ""

    @property
    def active_suppressions(self) -> list[dict[str, Any]]:
        today = date.today().isoformat()
        return [s for s in self.suppressions if not s.get("expires") or s["expires"] > today]


def load_policy(cwd: str, overrides: dict[str, Any] | None = None) -> PolicyConfig:
    """Load full v0.5.0 policy from .fettle.toml + overrides."""
    root = Path(cwd)
    config_path = root / ".fettle.toml"
    policy = PolicyConfig()

    # Apply defaults
    policy.fast = TierPolicy(**copy.deepcopy(DEFAULT_POLICY["fast"]))
    policy.changed = TierPolicy(**copy.deepcopy(DEFAULT_POLICY["changed"]))
    policy.full = TierPolicy(**copy.deepcopy(DEFAULT_POLICY["full"]))
    policy.ci = TierPolicy(**copy.deepcopy(DEFAULT_POLICY["ci"]))

    # Load from file
    file_cfg: dict[str, Any] = {}
    if config_path.is_file():
        try:
            with open(config_path, "rb") as fh:
                file_cfg = tomllib.load(fh)
        except (tomllib.TOMLDecodeError, OSError) as e:
            policy.config_error = f"Could not parse .fettle.toml: {e}"
            return policy

    # Apply tier policies from file
    file_policy = file_cfg.get("policy", {})
    if isinstance(file_policy.get("fast"), dict):
        policy.fast.merge(file_policy["fast"])
    if isinstance(file_policy.get("changed"), dict):
        policy.changed.merge(file_policy["changed"])
    if isinstance(file_policy.get("full"), dict):
        policy.full.merge(file_policy["full"])
    if isinstance(file_policy.get("ci"), dict):
        policy.ci.merge(file_policy["ci"])

    # Apply CLI overrides
    if overrides:
        for tier_name, tier_overrides in overrides.items():
            tier = getattr(policy, tier_name, None)
            if isinstance(tier, TierPolicy) and isinstance(tier_overrides, dict):
                tier.merge(tier_overrides)

    # Load per-checker config
    checks_cfg = file_cfg.get("checks", {})
    for name, cfg in checks_cfg.items():
        if name not in KNOWN_CHECKERS:
            policy.warnings.append(f"Unknown checker in config: {name}")
        if isinstance(cfg, dict):
            policy.checkers[name] = CheckerConfig(
                name=name,
                enabled=cfg.get("enabled", True),
                severity=cfg.get("severity", "error"),
                timeout_s=cfg.get("timeout_s", 30.0),
            )

    # Load suppressions
    policy.suppressions = file_cfg.get("suppressions", [])
    if isinstance(policy.suppressions, dict):
        policy.suppressions = [policy.suppressions]

    # Load exclude patterns
    exclude_cfg = file_cfg.get("exclude", {})
    if isinstance(exclude_cfg, dict):
        policy.exclude_patterns = exclude_cfg.get("patterns", [])

    return policy
