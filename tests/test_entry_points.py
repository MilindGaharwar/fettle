"""Tests for scripts/entry_points.py — WP-82: Entry point wiring checker."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from entry_points import check_entry_points


def test_valid_entry_point_passes(tmp_path):
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "cli.py").write_text("def main(): pass\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    findings = check_entry_points(str(tmp_path))
    assert findings == []


def test_missing_module_fails(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    findings = check_entry_points(str(tmp_path))
    assert len(findings) >= 1
    assert any("module" in f.message.lower() or "not found" in f.message.lower() for f in findings)


def test_missing_function_fails(tmp_path):
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "cli.py").write_text("def other(): pass\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    findings = check_entry_points(str(tmp_path))
    assert len(findings) >= 1
    assert any("main" in f.message for f in findings)


def test_no_entry_points_passes(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    findings = check_entry_points(str(tmp_path))
    assert findings == []


def test_invalid_toml_handled(tmp_path):
    (tmp_path / "pyproject.toml").write_text("not valid toml [[[")
    findings = check_entry_points(str(tmp_path))
    # Should not crash, returns empty or advisory
    assert isinstance(findings, list)
