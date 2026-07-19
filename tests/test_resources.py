"""Tests for packaged resource resolution."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from _resources import rules_dir


def test_rules_dir_contains_builtin_configs():
    root = rules_dir()
    assert (root / ".ruff.toml").is_file()
    assert (root / "llm-antipatterns.yml").is_file()
