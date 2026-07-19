"""Doctor self-check tests — the fail-visible contract.

Missing optional tools must be warnings (exit 0, consequence stated);
only missing REQUIRED tools may fail the check. A doctor that cries wolf
gets ignored; one that stays silent hides degraded gate coverage.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import doctor  # noqa: E402

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "doctor.py")


def test_missing_optional_tool_is_warning_not_failure(monkeypatch):
    real_which = doctor._which
    monkeypatch.setattr(
        doctor, "_which",
        lambda name: None if name in ("semgrep", "cargo", "shellcheck", "claude") else real_which(name),
    )
    checks = doctor.check_environment()
    by_name = {c["name"]: c for c in checks}
    for optional in ("semgrep", "cargo", "shellcheck", "claude"):
        assert by_name[optional]["ok"] is False
        assert by_name[optional]["required"] is False
        assert "skipped" in by_name[optional]["detail"] or "unavailable" in by_name[optional]["detail"]
    # Missing optionals alone must not make the environment unhealthy
    assert not [c for c in checks if c["required"] and not c["ok"]]


def test_missing_required_tool_fails(monkeypatch):
    monkeypatch.setattr(doctor, "_which", lambda name: None)
    checks = doctor.check_environment()
    required_failures = [c for c in checks if c["required"] and not c["ok"]]
    assert [c["name"] for c in required_failures] == ["ruff"]
    assert "disabled" in next(c for c in checks if c["name"] == "ruff")["detail"]


def test_json_mode_shape_and_exit_code():
    proc = subprocess.run(
        [sys.executable, SCRIPT, "--json"],
        capture_output=True, text=True, timeout=60,
    )
    data = json.loads(proc.stdout)
    assert isinstance(data["healthy"], bool)
    names = [c["name"] for c in data["checks"]]
    assert names[0] == "python"
    assert "ruff" in names
    assert proc.returncode == (0 if data["healthy"] else 1)


def test_python_check_reports_interpreter():
    checks = doctor.check_environment()
    py = checks[0]
    assert py["name"] == "python"
    assert py["ok"] is (sys.version_info >= (3, 11))
    assert sys.version.split()[0] in py["detail"]
