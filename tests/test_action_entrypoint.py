"""Tests for the GitHub Action entrypoint."""

import importlib.util
import json
from pathlib import Path


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
            "stdout": json.dumps({"findings": [{"severity": "ERROR"}]}),
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
    monkeypatch.setenv("INPUT_PATHS", '"src with spaces" tests')
    monkeypatch.setenv("INPUT_SARIF", "false")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return type("Result", (), {"stdout": '{"findings": []}', "stderr": "", "returncode": 0})()

    monkeypatch.setattr(action_entrypoint.subprocess, "run", run)

    assert action_entrypoint.main() == 0
    assert calls[0][0][-2:] == ["--root", str(tmp_path / "src with spaces")]
    assert calls[1][0][-2:] == ["--root", str(tmp_path / "tests")]
    assert "cwd" not in calls[0][1]
