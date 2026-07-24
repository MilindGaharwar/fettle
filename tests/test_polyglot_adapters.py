"""Tests for polyglot adapters — WP-94,95,96: TypeScript, Rust, Go."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.adapters import get_adapter, list_adapters
from fettle.profile import Profile


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
    findings = adapter.lint("fast", [str(tmp_path / "app.ts")])
    # Should return advisory about missing tools, not crash
    assert isinstance(findings, list)


def test_rust_lint_handles_missing_cargo(tmp_path):
    from fettle.adapters.rust_adapter import RustAdapter
    adapter = RustAdapter(cwd=str(tmp_path))
    adapter._runner.run = lambda cmd: type("R", (), {"tool_missing": True, "returncode": -1, "stdout": "", "stderr": ""})()
    findings = adapter.lint("fast", [])
    assert any("not found" in f.message.lower() for f in findings)


def test_go_lint_handles_missing_go(tmp_path):
    from fettle.adapters.go_adapter import GoAdapter
    adapter = GoAdapter(cwd=str(tmp_path))
    adapter._runner.run = lambda cmd: type("R", (), {"tool_missing": True, "returncode": -1, "stdout": "", "stderr": ""})()
    findings = adapter.lint("fast", [])
    assert any("not found" in f.message.lower() or "neither" in f.message.lower() for f in findings)


def test_all_adapters_have_required_methods():
    for adapter in list_adapters():
        assert hasattr(adapter, "detect")
        assert hasattr(adapter, "lint")
        assert hasattr(adapter, "format_check")
        assert hasattr(adapter, "typecheck")
        assert hasattr(adapter, "test")
        assert hasattr(adapter, "build")
        assert hasattr(adapter, "dependency_check")
