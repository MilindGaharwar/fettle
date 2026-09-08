"""Tests for fettle.autofix — safe ruff fix application."""

from unittest.mock import patch

from fettle.autofix import fix_file


class TestFixFile:
    def test_ruff_not_found(self, tmp_path):
        cfg = {"paths": {"ruff_config": ""}}
        with patch("fettle.autofix._resolve_ruff", return_value=None):
            result = fix_file(str(tmp_path / "x.py"), cfg)
        assert result["status"] == "error"
        assert "ruff not found" in result["message"]

    def test_file_not_found(self, tmp_path):
        cfg = {"paths": {"ruff_config": ""}}
        with patch("fettle.autofix._resolve_ruff", return_value="/usr/bin/ruff"):
            result = fix_file(str(tmp_path / "nonexistent.py"), cfg)
        assert result["status"] == "error"
        assert "file not found" in result["message"]

    def test_successful_fix(self, tmp_path, monkeypatch):
        py = tmp_path / "target.py"
        py.write_text("import os\nx = 1\n")
        cfg = {"paths": {"ruff_config": ""}}
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

        class FakeProc:
            returncode = 0
            stdout = "Found 1 error (1 fixed, 0 remaining)."
            stderr = ""

        def fake_run(*args, **kwargs):
            py.write_text("x = 1\n")
            return FakeProc()

        with patch("fettle.autofix._resolve_ruff", return_value="/usr/bin/ruff"), \
             patch("subprocess.run", side_effect=fake_run):
            result = fix_file(str(py), cfg)
        assert result["status"] == "fixed"

    def test_clean_file_is_not_reported_as_fixed(self, tmp_path, monkeypatch):
        py = tmp_path / "target.py"
        py.write_text("x = 1\n")
        cfg = {"paths": {"ruff_config": ""}}
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

        class FakeProc:
            returncode = 0
            stdout = "All checks passed!"
            stderr = ""

        with patch("fettle.autofix._resolve_ruff", return_value="/usr/bin/ruff"), \
             patch("subprocess.run", return_value=FakeProc()):
            result = fix_file(str(py), cfg)

        assert result["status"] == "no_change"

    def test_timeout_returns_error(self, tmp_path, monkeypatch):
        import subprocess
        py = tmp_path / "target.py"
        py.write_text("x = 1\n")
        cfg = {"paths": {"ruff_config": ""}}

        with patch("fettle.autofix._resolve_ruff", return_value="/usr/bin/ruff"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 10)):
            result = fix_file(str(py), cfg)
        assert result["status"] == "error"
        assert "timed out" in result["message"]

    def test_uses_custom_ruff_config(self, tmp_path, monkeypatch):
        py = tmp_path / "target.py"
        py.write_text("x = 1\n")
        custom_config = str(tmp_path / "custom.toml")
        cfg = {"paths": {"ruff_config": custom_config}}
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

        class FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""

        captured_cmd = []

        def fake_run(cmd, **kw):
            captured_cmd.extend(cmd)
            return FakeProc()

        with patch("fettle.autofix._resolve_ruff", return_value="/usr/bin/ruff"), \
             patch("subprocess.run", side_effect=fake_run):
            fix_file(str(py), cfg)
        assert custom_config in captured_cmd
