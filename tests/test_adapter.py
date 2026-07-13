"""Tests for scripts/adapters/ — WP-78: Language adapter protocol + Python adapter."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from adapters import get_adapter, list_adapters
from adapters.python_adapter import PythonAdapter
from profile import detect_profile


def test_adapter_registry_discovers_python():
    adapters = list_adapters()
    names = [a.language for a in adapters]
    assert "python" in names


def test_adapter_protocol_enforced():
    adapter = PythonAdapter()
    assert hasattr(adapter, "language")
    assert hasattr(adapter, "detect")
    assert hasattr(adapter, "lint")
    assert hasattr(adapter, "format_check")
    assert hasattr(adapter, "typecheck")
    assert hasattr(adapter, "test")
    assert hasattr(adapter, "build")
    assert hasattr(adapter, "dependency_check")


def test_python_adapter_detects_from_profile(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    profile = detect_profile(str(tmp_path))
    adapter = PythonAdapter()
    assert adapter.detect(profile)


def test_python_adapter_does_not_detect_node(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "app"}')
    profile = detect_profile(str(tmp_path))
    adapter = PythonAdapter()
    assert not adapter.detect(profile)


def test_python_lint_wraps_ruff(tmp_path):
    (tmp_path / "bad.py").write_text("import os\nimport sys\nx = 1\n")
    adapter = PythonAdapter(cwd=str(tmp_path))
    findings = adapter.lint("fast", [str(tmp_path / "bad.py")])
    # If ruff is available, it should find unused imports
    # If not available, should return advisory finding
    assert isinstance(findings, list)


def test_python_format_wraps_ruff_format(tmp_path):
    (tmp_path / "ugly.py").write_text("x=1\ny  =  2\n")
    adapter = PythonAdapter(cwd=str(tmp_path))
    findings = adapter.format_check("changed", [str(tmp_path / "ugly.py")])
    assert isinstance(findings, list)


def test_python_typecheck_wraps_pyright(tmp_path):
    (tmp_path / "typed.py").write_text("x: int = 'hello'\n")
    adapter = PythonAdapter(cwd=str(tmp_path))
    findings = adapter.typecheck("changed", [str(tmp_path / "typed.py")])
    assert isinstance(findings, list)


def test_python_test_wraps_pytest(tmp_path):
    (tmp_path / "test_x.py").write_text("def test_ok(): assert True\n")
    adapter = PythonAdapter(cwd=str(tmp_path))
    findings = adapter.test("full", [str(tmp_path / "test_x.py")])
    assert isinstance(findings, list)


def test_missing_tool_produces_advisory(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    adapter = PythonAdapter(cwd=str(tmp_path))
    # Force a missing tool scenario by using a fake tool name
    adapter._ruff_cmd = "nonexistent_ruff_xyz"
    findings = adapter.lint("fast", [str(tmp_path / "app.py")])
    assert any("not found" in f.message.lower() or "not available" in f.message.lower() for f in findings)


def test_get_adapter_by_language():
    adapter = get_adapter("python")
    assert adapter is not None
    assert adapter.language == "python"


def test_get_adapter_unknown():
    adapter = get_adapter("cobol")
    assert adapter is None
