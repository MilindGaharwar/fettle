"""Tests for scripts/profile.py — WP-67: Project profile detector."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from profile import detect_profile


def test_detects_python_from_pyproject_toml(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    (tmp_path / "src").mkdir()
    profile = detect_profile(str(tmp_path))
    assert "python" in profile.languages
    assert profile.workspaces[0].language == "python"


def test_detects_python_from_setup_py(tmp_path):
    (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup(name='x')")
    profile = detect_profile(str(tmp_path))
    assert "python" in profile.languages


def test_detects_node_from_package_json(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "myapp", "version": "1.0.0"}')
    profile = detect_profile(str(tmp_path))
    assert "javascript" in profile.languages or "typescript" in profile.languages


def test_detects_rust_from_cargo_toml(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "myapp"\nversion = "0.1.0"\n')
    profile = detect_profile(str(tmp_path))
    assert "rust" in profile.languages


def test_detects_go_from_go_mod(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/myapp\n\ngo 1.21\n")
    profile = detect_profile(str(tmp_path))
    assert "go" in profile.languages


def test_detects_polyglot_repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "backend"\n')
    (tmp_path / "package.json").write_text('{"name": "frontend"}')
    profile = detect_profile(str(tmp_path))
    assert len(profile.languages) >= 2


def test_no_markers_returns_empty_profile(tmp_path):
    (tmp_path / "readme.md").write_text("just docs")
    profile = detect_profile(str(tmp_path))
    assert profile.languages == []
    assert profile.workspaces == []


def test_cache_invalidation_on_marker_change(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "v1"\n')
    p1 = detect_profile(str(tmp_path))
    assert "python" in p1.languages
    # Add node
    (tmp_path / "package.json").write_text('{"name": "frontend"}')
    p2 = detect_profile(str(tmp_path), use_cache=False)
    assert len(p2.languages) >= 2


def test_does_not_walk_outside_repo_root(tmp_path):
    inner = tmp_path / "project"
    inner.mkdir()
    (inner / "pyproject.toml").write_text('[project]\nname = "inner"\n')
    # Parent has a Cargo.toml — should NOT be detected
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "parent"\n')
    profile = detect_profile(str(inner))
    assert "rust" not in profile.languages
    assert "python" in profile.languages


def test_custom_commands_from_fettle_toml_override(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    (tmp_path / ".fettle.toml").write_text(
        '[profile]\ntest_command = "make test"\nlint_command = "make lint"\n'
    )
    profile = detect_profile(str(tmp_path))
    ws = profile.workspaces[0]
    assert ws.test_command == "make test"
    assert ws.lint_command == "make lint"
