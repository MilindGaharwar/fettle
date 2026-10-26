"""Tests for the GitHub Action entrypoint."""

import importlib.util
import json
from pathlib import Path

import pytest

from fettle import __version__


_SPEC = importlib.util.spec_from_file_location(
    "fettle_action_entrypoint",
    Path(__file__).parents[1] / "scripts" / "action_entrypoint.py",
)
assert _SPEC and _SPEC.loader
action_entrypoint = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(action_entrypoint)


def test_enforce_mode_fails_on_uppercase_error(tmp_path, monkeypatch):
    output = tmp_path / "output"
    monkeypatch.setenv("INPUT_MODE", "enforce")
    monkeypatch.setenv("INPUT_SARIF", "false")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setattr(
        action_entrypoint.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {
            "stdout": json.dumps({"status": "violation", "tool_errors": [], "file_count": 1,
                                  "findings": [{"severity": "ERROR", "file": "app.py",
                                                "line": 1, "code": "TEST", "message": "error"}]}),
            "stderr": "",
            "returncode": 1,
        })(),
    )

    assert action_entrypoint.main() == 1
    assert "exit_code=1" in output.read_text()


def test_invalid_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("INPUT_MODE", "disabled")
    assert action_entrypoint.main() == 2


def test_sarif_normalizes_uppercase_severity():
    sarif = action_entrypoint._findings_to_sarif([
        {"code": "BLE001", "severity": "ERROR", "message": "broad catch", "file": "x.py", "line": 3},
    ])
    assert sarif["runs"][0]["results"][0]["level"] == "error"
    assert sarif["runs"][0]["tool"]["driver"]["version"] == __version__


def test_scan_failure_is_not_advisory_success(tmp_path, monkeypatch):
    monkeypatch.setenv("INPUT_MODE", "advisory")
    monkeypatch.setenv("INPUT_SARIF", "false")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setattr(
        action_entrypoint.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {
            "stdout": "",
            "stderr": "scanner crashed",
            "returncode": 2,
        })(),
    )

    assert action_entrypoint.main() == 2


def test_paths_are_passed_as_explicit_scan_roots(tmp_path, monkeypatch):
    calls = []
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src with spaces").mkdir()
    (tmp_path / "tests").mkdir()
    monkeypatch.setenv("INPUT_PATHS", '"src with spaces" tests')
    monkeypatch.setenv("INPUT_SARIF", "false")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return type("Result", (), {"stdout": json.dumps({"status": "pass", "tool_errors": [],
                                "file_count": 0, "findings": []}),
                       "stderr": "", "returncode": 0})()

    monkeypatch.setattr(action_entrypoint.subprocess, "run", run)

    assert action_entrypoint.main() == 0
    assert calls[0][0][-2:] == ["--root", str(tmp_path / "src with spaces")]
    assert calls[1][0][-2:] == ["--root", str(tmp_path / "tests")]
    assert "cwd" not in calls[0][1]


@pytest.mark.parametrize("paths", ["", "   ", '"', "does-not-exist", "source.py"])
def test_invalid_scan_scope_is_nonpass(tmp_path, monkeypatch, paths):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "source.py").write_text("value = 1\n")
    monkeypatch.setenv("INPUT_PATHS", paths)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("INPUT_SARIF", "false")
    monkeypatch.setattr(action_entrypoint.subprocess, "run",
                        lambda *args, **kwargs: pytest.fail("invalid scope must not run scanner"))
    assert action_entrypoint.main() == 2


@pytest.mark.parametrize("data,returncode", [
    ({}, 0),
    ([], 0),
    ({"status": "tool_error", "tool_errors": [], "file_count": 1, "findings": []}, 1),
    ({"status": "pass", "tool_errors": [], "file_count": 1, "findings": []}, 1),
    ({"status": "pass", "tool_errors": [{}], "file_count": 1, "findings": []}, 0),
    ({"status": "pass", "tool_errors": [], "file_count": True, "findings": []}, 0),
    ({"status": "violation", "tool_errors": [], "file_count": 1, "findings": [None]}, 0),
    ({"status": "violation", "tool_errors": [], "file_count": 1,
      "findings": [{"severity": "ERROR", "file": "app.py", "code": "TEST",
                    "line": 1, "message": "error"}]}, 0),
])
def test_invalid_scanner_evidence_is_nonpass(tmp_path, monkeypatch, data, returncode):
    monkeypatch.setenv("INPUT_PATHS", str(tmp_path))
    monkeypatch.setenv("INPUT_MODE", "advisory")
    monkeypatch.setenv("INPUT_SARIF", "false")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setattr(action_entrypoint.subprocess, "run", lambda *args, **kwargs:
                        type("Result", (), {"stdout": json.dumps(data), "stderr": "",
                                            "returncode": returncode})())
    assert action_entrypoint.main() == 2


@pytest.mark.parametrize("mode", ["advisory", "enforce"])
def test_later_root_failure_cannot_publish_success(tmp_path, monkeypatch, mode):
    output = tmp_path / "output"
    monkeypatch.setenv("INPUT_PATHS", f'"{tmp_path}" "{tmp_path}"')
    monkeypatch.setenv("INPUT_MODE", mode)
    monkeypatch.setenv("INPUT_SARIF", "true")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    responses = iter([
        {"status": "pass", "tool_errors": [], "file_count": 1, "findings": []},
        {},
    ])
    monkeypatch.setattr(action_entrypoint.subprocess, "run", lambda *args, **kwargs:
                        type("Result", (), {"stdout": json.dumps(next(responses)),
                                            "stderr": "", "returncode": 0})())

    assert action_entrypoint.main() == 2
    assert not output.exists() or "exit_code=0" not in output.read_text()


def test_valid_warning_only_result_remains_success(tmp_path, monkeypatch):
    data = {"status": "violation", "tool_errors": [], "file_count": 1,
            "findings": [{"severity": "warning", "file": "app.py", "line": 1,
                          "code": "TEST", "message": "warning"}]}
    monkeypatch.setenv("INPUT_PATHS", str(tmp_path))
    monkeypatch.setenv("INPUT_MODE", "enforce")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setattr(action_entrypoint.subprocess, "run", lambda *args, **kwargs:
                        type("Result", (), {"stdout": json.dumps(data), "stderr": "",
                                            "returncode": 0})())
    assert action_entrypoint.main() == 0
