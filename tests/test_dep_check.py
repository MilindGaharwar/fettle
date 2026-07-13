"""Tests for scripts/dep_check.py — WP-79: Dependency validation checker."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from dep_check import (
    extract_imports,
    get_declared_deps,
    check_undeclared,
    is_stdlib,
)


def test_detects_undeclared_import(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("import requests\nimport flask\n")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\ndependencies = ["flask"]\n')
    findings = check_undeclared(str(tmp_path), [str(src)])
    assert any("requests" in f.message for f in findings)


def test_ignores_stdlib_import(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("import os\nimport json\nimport pathlib\n")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\ndependencies = []\n')
    findings = check_undeclared(str(tmp_path), [str(src)])
    assert findings == []


def test_ignores_declared_dependency(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("import flask\n")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\ndependencies = ["flask"]\n')
    findings = check_undeclared(str(tmp_path), [str(src)])
    assert findings == []


def test_ignores_local_package_import(tmp_path):
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    src = tmp_path / "main.py"
    src.write_text("import myapp\nfrom myapp import utils\n")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "myapp"\ndependencies = []\n')
    findings = check_undeclared(str(tmp_path), [str(src)])
    assert findings == []


def test_handles_from_import(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("from requests import get\nfrom os.path import join\n")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\ndependencies = []\n')
    findings = check_undeclared(str(tmp_path), [str(src)])
    # requests is undeclared, os.path is stdlib
    assert any("requests" in f.message for f in findings)
    assert not any("os" in f.message for f in findings)


def test_handles_conditional_import(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("try:\n    import ujson\nexcept ImportError:\n    import json as ujson\n")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\ndependencies = []\n')
    # Conditional imports should not be flagged
    findings = check_undeclared(str(tmp_path), [str(src)])
    assert not any("ujson" in f.message for f in findings)


def test_handles_type_checking_import(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("from __future__ import annotations\nfrom typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import pandas\n")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\ndependencies = []\n')
    findings = check_undeclared(str(tmp_path), [str(src)])
    assert not any("pandas" in f.message for f in findings)


def test_reads_pyproject_dependencies(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\ndependencies = ["flask>=2.0", "requests[security]", "SQLAlchemy"]\n')
    deps = get_declared_deps(str(tmp_path))
    assert "flask" in deps
    assert "requests" in deps
    assert "sqlalchemy" in deps


def test_stdlib_detection():
    assert is_stdlib("os")
    assert is_stdlib("json")
    assert is_stdlib("pathlib")
    assert is_stdlib("typing")
    assert is_stdlib("collections")
    assert not is_stdlib("flask")
    assert not is_stdlib("requests")


def test_extract_imports_basic(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("import os\nimport flask\nfrom requests import get\n")
    imports = extract_imports(str(src))
    assert "os" in imports
    assert "flask" in imports
    assert "requests" in imports
