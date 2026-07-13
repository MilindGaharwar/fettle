"""Tests for scripts/tier_routing.py — WP-75: Tier policy and routing."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from tier_routing import (
    resolve_tier,
    scope_files_for_tier,
)


def test_fast_tier_runs_only_configured_checkers():
    tier = resolve_tier("fast")
    assert tier.name == "fast"
    assert "ruff" in tier.default_checkers
    assert "semgrep" in tier.default_checkers


def test_changed_tier_scopes_to_changed_files():
    all_files = ["src/app.py", "src/util.py", "tests/test_app.py"]
    changed = ["src/app.py"]
    scoped = scope_files_for_tier("changed", all_files, changed_files=changed)
    assert scoped == ["src/app.py"]


def test_full_tier_runs_all_checkers_all_files():
    tier = resolve_tier("full")
    assert tier.name == "full"
    # Full tier doesn't restrict checkers
    assert tier.default_checkers == []


def test_ci_tier_runs_profile_commands():
    tier = resolve_tier("ci")
    assert tier.name == "ci"


def test_unknown_tier_errors_clearly():
    tier = resolve_tier("nonexistent")
    assert tier.error
    assert "unknown" in tier.error.lower() or "invalid" in tier.error.lower()


def test_checker_receives_only_relevant_files():
    all_files = ["src/app.py", "src/util.py", "README.md", "tests/test_app.py"]
    changed = ["src/app.py", "README.md"]
    scoped = scope_files_for_tier("changed", all_files, changed_files=changed)
    assert "src/app.py" in scoped
    assert "README.md" in scoped
    assert "src/util.py" not in scoped


def test_no_changed_files_skips_changed_tier():
    all_files = ["src/app.py"]
    scoped = scope_files_for_tier("changed", all_files, changed_files=[])
    assert scoped == []


def test_fast_tier_scopes_to_single_file():
    # Fast tier typically checks only the just-edited file
    scoped = scope_files_for_tier("fast", ["src/app.py"], edited_file="src/app.py")
    assert scoped == ["src/app.py"]
