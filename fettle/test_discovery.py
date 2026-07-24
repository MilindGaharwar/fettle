"""Fettle v0.5.0 — WP-85: Python test command discovery.

Discover how to run tests for a Python project.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestConfig:
    """Discovered test configuration."""

    framework: str | None = None
    command: str = ""
    test_roots: list[str] = field(default_factory=list)
    has_tox: bool = False
    has_nox: bool = False


def discover_test_config(cwd: str) -> TestConfig:
    """Discover test framework and configuration for a Python project."""
    root = Path(cwd)
    config = TestConfig()

    # Check for .fettle.toml override first
    fettle_toml = root / ".fettle.toml"
    if fettle_toml.is_file():
        try:
            with open(fettle_toml, "rb") as f:
                data = tomllib.load(f)
            custom_cmd = data.get("profile", {}).get("test_command", "")
            if custom_cmd:
                config.command = custom_cmd
                config.framework = "custom"
                return config
        except (tomllib.TOMLDecodeError, OSError):
            pass

    # Detect test directories
    for name in ("tests", "test", "spec"):
        if (root / name).is_dir():
            config.test_roots.append(name)

    # Detect tox/nox
    config.has_tox = (root / "tox.ini").is_file()
    config.has_nox = (root / "noxfile.py").is_file()

    # Detect pytest
    if _has_pytest(root):
        config.framework = "pytest"
        config.command = "python3 -m pytest"
        if config.test_roots:
            config.command += f" {config.test_roots[0]}/"
        return config

    # Check pyproject.toml for test framework hints
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            if "pytest" in str(data.get("tool", {})):
                config.framework = "pytest"
                config.command = "python3 -m pytest"
                return config
        except (tomllib.TOMLDecodeError, OSError):
            pass

    return config


def _has_pytest(root: Path) -> bool:
    """Check for pytest presence."""
    if (root / "conftest.py").is_file():
        return True
    if (root / "pytest.ini").is_file():
        return True
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            if "pytest" in data.get("tool", {}):
                return True
        except (tomllib.TOMLDecodeError, OSError):
            pass
    return False
