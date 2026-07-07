"""Tests for scripts/ux_spec_gate.py"""

import io
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_skips_when_disabled(tmp_path, monkeypatch):
    """Gate exits silently when disabled (default)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".fettle.toml").write_text("")

    data = json.dumps({
        "tool_input": {"file_path": str(tmp_path / "src/pages/Home.tsx")},
        "cwd": str(tmp_path),
        "session_id": "test",
    })

    from ux_spec_gate import main
    with patch("sys.stdin", io.StringIO(data)):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0


def test_skips_non_frontend_file(tmp_path, monkeypatch):
    """Gate exits silently for non-frontend files."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".fettle.toml").write_text("[gates.ux_spec]\nenabled = true\n")

    data = json.dumps({
        "tool_input": {"file_path": str(tmp_path / "scripts/main.py")},
        "cwd": str(tmp_path),
        "session_id": "test",
    })

    from ux_spec_gate import main
    with patch("sys.stdin", io.StringIO(data)):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0
