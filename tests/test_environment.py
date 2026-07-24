"""Tests for scripts/environment.py — WP-72: Tool/runtime discovery."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.environment import (
    discover_runtime,
    discover_tool,
    check_lockfile_sync,
)


def test_detects_python_version():
    info = discover_runtime("python")
    assert info.available
    assert info.version
    assert "." in info.version


def test_detects_node_version():
    info = discover_runtime("node")
    # May not be available in all environments
    if info.available:
        assert info.version
        assert "." in info.version


def test_detects_missing_tool():
    info = discover_tool("nonexistent_tool_xyz_99999")
    assert not info.available
    assert info.path is None


def test_detects_lockfile_out_of_sync(tmp_path):
    # Simulate: pyproject.toml newer than uv.lock
    lock = tmp_path / "uv.lock"
    lock.write_text("old lock content")
    import time
    time.sleep(0.05)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\ndependencies = ["requests"]\n')
    result = check_lockfile_sync(str(tmp_path), "pyproject.toml", "uv.lock")
    assert not result.in_sync
    assert "newer" in result.message.lower() or "out of sync" in result.message.lower()


def test_reads_python_version_file(tmp_path):
    (tmp_path / ".python-version").write_text("3.12.0\n")
    info = discover_runtime("python", cwd=str(tmp_path))
    assert info.expected_version == "3.12.0"


def test_reads_node_version_file(tmp_path):
    (tmp_path / ".node-version").write_text("20.11.0\n")
    info = discover_runtime("node", cwd=str(tmp_path))
    assert info.expected_version == "20.11.0"


def test_tool_discovery_prefers_workspace_local(tmp_path):
    # If a tool exists in node_modules/.bin, it should be noted
    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    fake_tool = bin_dir / "eslint"
    fake_tool.write_text("#!/bin/sh\necho fake")
    fake_tool.chmod(0o755)
    info = discover_tool("eslint", search_paths=[str(bin_dir)])
    assert info.available
    assert str(bin_dir) in (info.path or "")


def test_unsupported_runtime_handled():
    info = discover_runtime("cobol")
    assert not info.available


def test_reports_advisory_on_mismatch(tmp_path):
    (tmp_path / ".python-version").write_text("3.99.0\n")
    info = discover_runtime("python", cwd=str(tmp_path))
    # actual version won't be 3.99.0
    if info.available and info.expected_version:
        assert info.version != info.expected_version
