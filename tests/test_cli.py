"""Tests for scripts/cli.py — CLI entry point."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_cli_help(capsys):
    from cli import main
    with pytest.raises(SystemExit) as exc_info, patch("sys.argv", ["fettle"]):
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


def test_cli_config_effective_honors_mode_override(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FETTLE_GATE_MODE", "enforce")
    (tmp_path / ".git").mkdir()
    from cli import main
    with patch("sys.argv", ["fettle", "config", "--print-effective"]):
        main()
    output = capsys.readouterr().out
    assert '"mode": "enforce"' in output


def test_cli_doctor(tmp_path, monkeypatch):
    """Doctor command runs without crashing."""
    monkeypatch.chdir(tmp_path)
    from cli import cmd_doctor
    import argparse
    args = argparse.Namespace()
    cmd_doctor(args)


# --- `fettle check` exit-code contract (WP-133 / audit D1+D2) ---
# 0 = clean, 1 = error-severity findings, 2 = usage/environment error.
# Codes must be identical for text and --json modes.

_ERROR_FINDING = {
    "file": "a.py", "line": 1, "code": "S608",
    "message": "sql injection", "severity": "error", "tool": "ruff",
}
_WARNING_FINDING = {
    "file": "a.py", "line": 2, "code": "SIM108",
    "message": "use ternary", "severity": "warning", "tool": "ruff",
}


def _run_check(tmp_path, monkeypatch, argv, findings):
    """Run `fettle check` in-process with scan_project mocked out."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir(exist_ok=True)
    from cli import main
    with patch("quality_scan.scan_project",
               return_value={"findings": findings, "file_count": 1}), \
         patch("paths.find_repo_root", return_value=tmp_path), \
         patch("sys.argv", ["fettle", "check", *argv]), \
         pytest.raises(SystemExit) as exc_info:
        main()
    return exc_info.value.code


def test_check_json_exits_1_on_error_findings(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--json"], [_ERROR_FINDING]) == 1


def test_check_text_exits_1_on_error_findings(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, [], [_ERROR_FINDING]) == 1


def test_check_json_exits_0_when_clean(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--json"], []) == 0


def test_check_exits_0_on_warnings_only(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--json"], [_WARNING_FINDING]) == 0


def test_check_all_and_changed_conflict_exits_2(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--all", "--changed"], []) == 2


def test_check_outside_repo_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from cli import main
    with patch("paths.find_repo_root", return_value=None), \
         patch("sys.argv", ["fettle", "check"]), \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


def test_check_baseline_missing_exits_2(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--baseline"], [_ERROR_FINDING]) == 2


def test_check_baseline_filters_known_findings(tmp_path, monkeypatch, capsys):
    import json as _json
    (tmp_path / ".fettle-baseline.json").write_text(
        _json.dumps({"version": 1, "findings": [_ERROR_FINDING]})
    )
    assert _run_check(tmp_path, monkeypatch, ["--baseline"], [_ERROR_FINDING]) == 0


def test_check_baseline_reports_new_findings(tmp_path, monkeypatch, capsys):
    import json as _json
    (tmp_path / ".fettle-baseline.json").write_text(
        _json.dumps({"version": 1, "findings": [_WARNING_FINDING]})
    )
    assert _run_check(tmp_path, monkeypatch, ["--baseline"], [_ERROR_FINDING]) == 1


def test_check_changed_no_changes_exits_0(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from cli import main
    with patch("paths.find_repo_root", return_value=tmp_path), \
         patch("changeset.get_changed_files", return_value=[]), \
         patch("sys.argv", ["fettle", "check", "--changed"]), \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert "No changed" in capsys.readouterr().out


# --- Version reporting and alignment (WP-138 / audit D5) ---

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_version_flag(capsys):
    import re
    from cli import main
    with patch("sys.argv", ["fettle", "--version"]), pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert re.match(r"^fettle \d+\.\d+\.\d+", out)


def test_version_metadata_aligned():
    """pyproject, package __version__, CHANGELOG, and README must agree.

    Release gate: the repo shipped with pyproject at 0.7.0 while docs
    claimed v1.0.0 (audit D5). This test makes that drift impossible.
    """
    import re
    import tomllib

    with open(os.path.join(_REPO_ROOT, "pyproject.toml"), "rb") as fh:
        pyproject_version = tomllib.load(fh)["project"]["version"]

    with open(os.path.join(_REPO_ROOT, "scripts", "__init__.py")) as fh:
        init_version = re.search(r'__version__ = "([^"]+)"', fh.read()).group(1)

    with open(os.path.join(_REPO_ROOT, "CHANGELOG.md")) as fh:
        changelog_version = re.search(r"^## v(\d+\.\d+\.\d+)", fh.read(), re.MULTILINE).group(1)

    with open(os.path.join(_REPO_ROOT, "README.md")) as fh:
        readme_version = re.search(r"\*\*Status: v(\d+\.\d+\.\d+)\*\*", fh.read()).group(1)

    assert pyproject_version == init_version == changelog_version == readme_version


def test_cli_version_matches_pyproject():
    import tomllib
    from cli import _version
    with open(os.path.join(_REPO_ROOT, "pyproject.toml"), "rb") as fh:
        assert _version() == tomllib.load(fh)["project"]["version"]


