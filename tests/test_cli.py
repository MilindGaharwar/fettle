"""Tests for scripts/cli.py — CLI entry point."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_cli_help(capsys):
    from cli import main
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["fettle"]):
            main()
    assert exc_info.value.code == 0


def test_cli_config_effective(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    from cli import main
    with patch("sys.argv", ["fettle", "config", "--print-effective"]):
        main()
    output = capsys.readouterr().out
    assert "Effective Fettle Configuration" in output


def test_cli_doctor(tmp_path, monkeypatch):
    """Doctor command runs without crashing."""
    monkeypatch.chdir(tmp_path)
    from cli import cmd_doctor
    import argparse
    args = argparse.Namespace()
    cmd_doctor(args)
