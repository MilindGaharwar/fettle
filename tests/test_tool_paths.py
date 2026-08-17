import os

from fettle import tool_paths


def test_resolve_tool_prefers_path(monkeypatch):
    monkeypatch.setattr(tool_paths.shutil, "which", lambda name: f"/custom/{name}")

    assert tool_paths.resolve_tool("ruff") == "/custom/ruff"


def test_resolve_tool_falls_back_to_fettle_environment(monkeypatch, tmp_path):
    executable = tmp_path / ("ruff.exe" if os.name == "nt" else "ruff")
    executable.write_text("")
    executable.chmod(0o755)
    monkeypatch.setattr(tool_paths.shutil, "which", lambda _name: None)
    monkeypatch.setattr(tool_paths.sys, "executable", str(tmp_path / "python"))

    assert tool_paths.resolve_tool("ruff") == str(executable)


def test_resolve_tool_reports_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_paths.shutil, "which", lambda _name: None)
    monkeypatch.setattr(tool_paths.sys, "executable", str(tmp_path / "python"))

    assert tool_paths.resolve_tool("ruff") is None
