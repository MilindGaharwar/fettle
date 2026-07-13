"""Tests for config extensions — WP-73: Configuration and enforcement policy."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from config_v050 import load_policy


def test_default_config_works_with_no_file(tmp_path):
    policy = load_policy(str(tmp_path))
    assert policy.fast is not None
    assert policy.changed is not None
    assert policy.full is not None


def test_repo_config_overrides_defaults(tmp_path):
    (tmp_path / ".fettle.toml").write_text("""
[policy.fast]
timeout_s = 10
blocking = false

[policy.changed]
timeout_s = 60
""")
    policy = load_policy(str(tmp_path))
    assert policy.fast.timeout_s == 10
    assert policy.fast.blocking is False
    assert policy.changed.timeout_s == 60


def test_cli_flags_override_config(tmp_path):
    (tmp_path / ".fettle.toml").write_text("""
[policy.fast]
timeout_s = 10
""")
    policy = load_policy(str(tmp_path), overrides={"fast": {"timeout_s": 5}})
    assert policy.fast.timeout_s == 5


def test_invalid_config_produces_clear_error(tmp_path):
    (tmp_path / ".fettle.toml").write_text("this is not valid toml [[[")
    policy = load_policy(str(tmp_path))
    assert policy.config_error
    assert "parse" in policy.config_error.lower() or "invalid" in policy.config_error.lower()


def test_policy_controls_blocking_advisory(tmp_path):
    (tmp_path / ".fettle.toml").write_text("""
[policy.fast]
blocking = false
""")
    policy = load_policy(str(tmp_path))
    assert policy.fast.blocking is False


def test_suppression_excludes_finding(tmp_path):
    (tmp_path / ".fettle.toml").write_text("""
[[suppressions]]
checker = "ruff"
rule = "F401"
path = "legacy/"
reason = "Legacy code, rewrite planned Q3"
""")
    policy = load_policy(str(tmp_path))
    assert len(policy.suppressions) == 1
    assert policy.suppressions[0]["rule"] == "F401"


def test_suppression_with_expiry_re_enables(tmp_path):
    (tmp_path / ".fettle.toml").write_text("""
[[suppressions]]
checker = "ruff"
rule = "F401"
path = "legacy/"
reason = "Rewrite planned"
expires = "2020-01-01"
""")
    policy = load_policy(str(tmp_path))
    # Expired suppression should be filtered out
    assert len(policy.active_suppressions) == 0


def test_exclude_patterns_skip_files(tmp_path):
    (tmp_path / ".fettle.toml").write_text("""
[exclude]
patterns = ["vendor/", "generated/", "*.pb.go"]
""")
    policy = load_policy(str(tmp_path))
    assert "vendor/" in policy.exclude_patterns
    assert "generated/" in policy.exclude_patterns


def test_unknown_checker_in_config_warned(tmp_path):
    (tmp_path / ".fettle.toml").write_text("""
[checks.nonexistent_checker_xyz]
enabled = true
""")
    policy = load_policy(str(tmp_path))
    assert any("nonexistent_checker_xyz" in w for w in policy.warnings)
