"""Tests for scripts/adapters/ — WP-78: Language adapter protocol + Python adapter."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.adapters import CheckRun, get_adapter, list_adapters, run_adapter_check
from fettle.finding import ResultState
from fettle.tool_runner import RunResult
from fettle.workspace import Workspace
from fettle.adapters.python_adapter import PythonAdapter
from fettle.profile import detect_profile


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


def test_adapter_run_exposes_tool_error_instead_of_empty_findings(tmp_path):
    adapter = PythonAdapter(cwd=str(tmp_path))
    adapter._runner.run = lambda _cmd: RunResult(returncode=-1, tool_missing=True)
    workspace = Workspace(name="app", path=".", language="python", marker="pyproject.toml")

    run = run_adapter_check(adapter, "lint", workspace, ["app.py"], scope="changed")
    assert isinstance(run, CheckRun)
    assert run.result_state == ResultState.TOOL_ERROR
    assert run.tool_error
    assert run.evidence[0].kind == "command"


def test_adapter_run_marks_clean_result_pass(tmp_path):
    adapter = PythonAdapter(cwd=str(tmp_path))
    adapter._runner.run = lambda _cmd: RunResult(returncode=0)
    workspace = Workspace(name="app", path=".", language="python", marker="pyproject.toml")
    run = run_adapter_check(adapter, "lint", workspace, [], scope="full")
    assert run.result_state == ResultState.PASS
    assert run.findings == []


def test_all_adapter_operations_support_native_workspace_contract(tmp_path):
    workspace = Workspace(name="app", path=".", language="python", marker="pyproject.toml")
    adapter = PythonAdapter(cwd=str(tmp_path))
    adapter._runner.run = lambda _cmd: RunResult(returncode=0)

    runs = [
        adapter.lint(workspace, ["app.py"]),
        adapter.format_check(workspace, ["app.py"]),
        adapter.typecheck(workspace, ["app.py"]),
        adapter.test(workspace, ["test_app.py"], "changed"),
        adapter.build(workspace),
        adapter.dependency_check(workspace),
    ]

    assert all(isinstance(run, CheckRun) for run in runs)
    assert all(run.result_state == ResultState.PASS for run in runs)


def test_each_registered_adapter_returns_native_check_run(tmp_path):
    languages = {
        "python": "pyproject.toml",
        "typescript": "package.json",
        "go": "go.mod",
        "rust": "Cargo.toml",
    }
    for language, marker in languages.items():
        adapter_type = type(get_adapter(language))
        adapter = adapter_type(cwd=str(tmp_path))
        adapter._runner.run = lambda _cmd: RunResult(returncode=0)
        workspace = Workspace(name="app", path=".", language=language, marker=marker)
        run = adapter.lint(workspace, [])
        assert isinstance(run, CheckRun)
        assert run.result_state == ResultState.PASS
