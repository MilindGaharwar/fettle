"""Fettle v0.5.0 — WP-75: Tier policy and routing.

Define fast/changed/full/ci tiers. Route checkers by tier and scope
files appropriately for each tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field


VALID_TIERS = ("fast", "changed", "full", "ci")

_TIER_DEFAULTS: dict[str, dict] = {
    "fast": {
        "timeout_s": 15,
        "default_checkers": ["ruff", "semgrep"],
        "scope": "edited",
    },
    "changed": {
        "timeout_s": 90,
        "default_checkers": ["ruff", "semgrep", "pyright", "deptry"],
        "scope": "changed",
    },
    "full": {
        "timeout_s": 300,
        "default_checkers": [],
        "scope": "all",
    },
    "ci": {
        "timeout_s": 600,
        "default_checkers": [],
        "scope": "all",
    },
}


@dataclass
class TierInfo:
    """Resolved tier configuration."""

    name: str
    timeout_s: float = 15.0
    default_checkers: list[str] = field(default_factory=list)
    scope: str = "edited"
    error: str = ""


def resolve_tier(tier_name: str) -> TierInfo:
    """Resolve a tier name to its configuration."""
    if tier_name not in VALID_TIERS:
        return TierInfo(name=tier_name, error=f"Unknown tier: '{tier_name}'. Valid: {', '.join(VALID_TIERS)}")
    defaults = _TIER_DEFAULTS[tier_name]
    return TierInfo(
        name=tier_name,
        timeout_s=defaults["timeout_s"],
        default_checkers=list(defaults["default_checkers"]),
        scope=defaults["scope"],
    )


def scope_files_for_tier(
    tier_name: str,
    all_files: list[str],
    changed_files: list[str] | None = None,
    edited_file: str | None = None,
) -> list[str]:
    """Scope the file list based on tier policy.

    - fast: only the just-edited file
    - changed: only files in the changed set
    - full/ci: all files
    """
    if tier_name == "fast":
        if edited_file:
            return [edited_file] if edited_file in all_files else [edited_file]
        if changed_files:
            return changed_files[:1]
        return all_files[:1] if all_files else []

    if tier_name == "changed":
        if changed_files is None:
            return all_files
        return list(changed_files)

    # full and ci: all files
    return all_files
