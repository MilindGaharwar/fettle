"""Tests for packaged resource resolution."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from pathlib import Path

import fettle

from fettle._resources import commands_dir, rules_dir, templates_dir


def test_rules_dir_contains_builtin_configs():
    root = rules_dir()
    assert (root / ".ruff.toml").is_file()
    assert (root / "llm-antipatterns.yml").is_file()


def test_runtime_package_contains_every_bundled_resource_family():
    package = Path(fettle.__file__).parent

    assert len(list(commands_dir().glob("*.md"))) == 17
    assert (templates_dir() / "preflight.md").is_file()
    assert (package / "_demo_fixture" / "calculator.py.txt").is_file()
    assert (package / "host-capabilities.schema.json").is_file()
