"""Tests for scripts/entry_points.py — WP-82: Entry point wiring checker."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.entry_points import check_entry_points
from fettle.finding import FindingSeverity


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
    assert len(findings) == 1
    finding = findings[0]
    assert finding.checker == "entry-points"
    assert finding.severity == FindingSeverity.ERROR
    assert finding.file == "pyproject.toml"
    assert finding.line == 0
    assert finding.message == "Entry point 'myapp': module 'myapp.cli' not found"
    assert finding.suggested_fix == "Create cli.py or check the module path in [project.scripts]"
    assert finding.blocking is False


def test_missing_function_fails(tmp_path):
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "cli.py").write_text("def other(): pass\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    findings = check_entry_points(str(tmp_path))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.checker == "entry-points"
    assert finding.severity == FindingSeverity.ERROR
    assert finding.file == str(pkg / "cli.py")
    assert finding.line == 0
    assert finding.message == "Entry point 'myapp': function 'main' not found in cli.py"
    assert finding.suggested_fix == "Define 'def main():' in cli.py"
    assert finding.blocking is False


def test_no_entry_points_passes(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    findings = check_entry_points(str(tmp_path))
    assert findings == []


def test_invalid_toml_handled(tmp_path):
    (tmp_path / "pyproject.toml").write_text("not valid toml [[[")
    findings = check_entry_points(str(tmp_path))
    # Should not crash, returns empty or advisory
    assert isinstance(findings, list)


def test_invalid_entry_point_format_reports_actionable_finding(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\nmyapp = "myapp.cli"\n'
    )

    findings = check_entry_points(str(tmp_path))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.checker == "entry-points"
    assert finding.severity == FindingSeverity.ERROR
    assert finding.file == "pyproject.toml"
    assert finding.line == 0
    assert finding.message == (
        "Entry point 'myapp' has invalid format: 'myapp.cli' "
        "(expected 'module.path:function')"
    )
    assert finding.blocking is False


def test_entry_point_with_multiple_colons_reports_invalid_format(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\nmyapp = "myapp.cli:main:extra"\n'
    )

    findings = check_entry_points(str(tmp_path))

    assert len(findings) == 1
    assert "invalid format" in findings[0].message


def test_nested_missing_module_suggests_leaf_module(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\nmyapp = "myapp.commands.cli:main"\n'
    )

    findings = check_entry_points(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].suggested_fix == "Create cli.py or check the module path in [project.scripts]"


def test_package_entry_point_passes(tmp_path):
    package = tmp_path / "myapp"
    package.mkdir()
    (package / "__init__.py").write_text("def main(): pass\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\nmyapp = "myapp:main"\n'
    )

    assert check_entry_points(str(tmp_path)) == []


def test_src_module_and_package_entry_points_pass(tmp_path):
    package = tmp_path / "src" / "myapp"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("def package_main(): pass\n")
    (package / "cli.py").write_text("def module_main(): pass\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\n'
        'module = "myapp.cli:module_main"\npackage = "myapp:package_main"\n'
    )

    assert check_entry_points(str(tmp_path)) == []


def test_root_module_takes_precedence_over_src_module(tmp_path):
    root_package = tmp_path / "myapp"
    src_package = tmp_path / "src" / "myapp"
    root_package.mkdir()
    src_package.mkdir(parents=True)
    (root_package / "cli.py").write_text("def other(): pass\n")
    (src_package / "cli.py").write_text("def main(): pass\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )

    findings = check_entry_points(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].file == str(root_package / "cli.py")
