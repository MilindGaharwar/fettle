"""Tests for scripts/test_discovery.py — WP-85: Python test command discovery."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from test_discovery import discover_test_config


def test_discovers_pytest_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
    )
    config = discover_test_config(str(tmp_path))
    assert config.framework == "pytest"
    assert "pytest" in config.command


def test_discovers_pytest_from_conftest(tmp_path):
    (tmp_path / "conftest.py").write_text("import pytest\n")
    config = discover_test_config(str(tmp_path))
    assert config.framework == "pytest"


def test_discovers_test_directory(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("def test_x(): pass\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    config = discover_test_config(str(tmp_path))
    assert "tests" in config.test_roots


def test_discovers_tox_configuration(tmp_path):
    (tmp_path / "tox.ini").write_text("[tox]\nenvlist = py311\n[testenv]\ncommands = pytest\n")
    config = discover_test_config(str(tmp_path))
    assert config.has_tox


def test_no_test_framework_returns_none(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    config = discover_test_config(str(tmp_path))
    assert config.framework is None
    assert config.command == ""


def test_custom_test_command_from_config_honored(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    (tmp_path / ".fettle.toml").write_text('[profile]\ntest_command = "make test"\n')
    config = discover_test_config(str(tmp_path))
    assert config.command == "make test"
