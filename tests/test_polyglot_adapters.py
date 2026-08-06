"""Tests for polyglot adapters — WP-94,95,96: TypeScript, Rust, Go."""

import os
import json
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.adapters import get_adapter, list_adapters
from fettle.profile import Profile
from fettle.tool_runner import RunResult
from fettle.workspace import Workspace


def test_registry_has_all_adapters():
    adapters = list_adapters()
    languages = {a.language for a in adapters}
    assert "python" in languages
    assert "typescript" in languages
    assert "rust" in languages
    assert "go" in languages


def test_typescript_adapter_detects():
    adapter = get_adapter("typescript")
    profile = Profile(languages=["typescript"])
    assert adapter.detect(profile)


def test_typescript_adapter_rejects_python():
    adapter = get_adapter("typescript")
    profile = Profile(languages=["python"])
    assert not adapter.detect(profile)


def test_rust_adapter_detects():
    adapter = get_adapter("rust")
    profile = Profile(languages=["rust"])
    assert adapter.detect(profile)


def test_go_adapter_detects():
    adapter = get_adapter("go")
    profile = Profile(languages=["go"])
    assert adapter.detect(profile)


def test_typescript_lint_handles_missing_tools(tmp_path):
    adapter = get_adapter("typescript")
    adapter._cwd = str(tmp_path)
    adapter._runner._cwd = str(tmp_path)
    (tmp_path / "app.ts").write_text("const x: number = 'hello';\n")
    workspace = Workspace(path=".", language="typescript", manager="npm")
    findings = adapter.lint(workspace, [str(tmp_path / "app.ts")]).findings
    # Should return advisory about missing tools, not crash
    assert isinstance(findings, list)


def test_rust_lint_handles_missing_cargo(tmp_path):
    from fettle.adapters.rust_adapter import RustAdapter
    adapter = RustAdapter(cwd=str(tmp_path))
    adapter._runner.run = lambda cmd: type("R", (), {"tool_missing": True, "returncode": -1, "stdout": "", "stderr": ""})()
    findings = adapter.lint(Workspace(path=".", language="rust"), []).findings
    assert any("not found" in f.message.lower() for f in findings)


def test_go_lint_handles_missing_go(tmp_path):
    from fettle.adapters.go_adapter import GoAdapter
    adapter = GoAdapter(cwd=str(tmp_path))
    adapter._runner.run = lambda cmd: type("R", (), {"tool_missing": True, "returncode": -1, "stdout": "", "stderr": ""})()
    findings = adapter.lint(Workspace(path=".", language="go"), []).findings
    assert any("not found" in f.message.lower() or "neither" in f.message.lower() for f in findings)


def test_go_native_lint_preserves_semgrep_findings(tmp_path):
    from fettle.adapters.go_adapter import GoAdapter

    target = tmp_path / "app.go"
    target.write_text('package app\nimport "fmt"\nfunc f() { fmt.Println("debug") }\n')
    adapter = GoAdapter(cwd=str(tmp_path))
    workspace = Workspace(path=".", language="go", manager="go")
    output = json.dumps({
        "results": [{
            "check_id": "debug-print-go",
            "path": "app.go",
            "start": {"line": 3},
            "extra": {"severity": "WARNING", "message": "debug print"},
        }],
    })
    with (patch("fettle.adapters._resolve_tool", return_value="semgrep"),
          patch("fettle.adapters.subprocess.run", return_value=subprocess.CompletedProcess(
              [], 1, output, "",
          )),
          patch.object(adapter._runner, "run", return_value=RunResult(returncode=0))):
        run = adapter.lint(workspace, [str(target)])
    assert run.result_state == "violation"
    assert run.findings[0].code == "debug-print-go"


def test_all_adapters_have_required_methods():
    for adapter in list_adapters():
        assert hasattr(adapter, "detect")
        assert hasattr(adapter, "lint")
        assert hasattr(adapter, "format_check")
        assert hasattr(adapter, "typecheck")
        assert hasattr(adapter, "test")
        assert hasattr(adapter, "build")
        assert hasattr(adapter, "dependency_check")
