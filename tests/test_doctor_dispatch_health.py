"""Stage-0 failure visibility — doctor and report surface dispatcher fail-opens.

A gate that silently never runs must be visible from `fettle doctor` and
`fettle report`, and audit-trace writability must be probeable from outside
the trace itself.
"""

import json

import pytest

from fettle import trace as trace_mod
from fettle.doctor import check_dispatch_health
from fettle.report import compute_effectiveness


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "state"


def _write_dispatcher_failure(status: str, findings: list[dict]) -> None:
    trace_mod.log_decision(hook="dispatcher", status=status, findings=findings)


class TestDoctorDispatchHealth:
    def test_clean_trace_reports_ok(self, isolated_state):
        trace_mod.log_decision(hook="post-edit", status="pass")
        checks = {c["name"]: c for c in check_dispatch_health()}
        assert checks["audit-trace"]["ok"] is True
        assert checks["dispatch"]["ok"] is True
        assert "no fail-open events" in checks["dispatch"]["detail"]

    def test_check_errors_flagged_with_failing_check_names(self, isolated_state):
        for _ in range(4):
            _write_dispatcher_failure(
                "check_error", [{"check": "lean_sniffers", "error": "boom"}])
        _write_dispatcher_failure(
            "budget_exhausted", [{"skipped_from": "coverage_gate"}])
        checks = {c["name"]: c for c in check_dispatch_health()}
        assert checks["dispatch"]["ok"] is False
        assert "check_error×4" in checks["dispatch"]["detail"]
        assert "budget_exhausted×1" in checks["dispatch"]["detail"]
        assert "lean_sniffers (4×)" in checks["dispatch"]["detail"]

    def test_unwritable_trace_flagged(self, tmp_path, monkeypatch):
        blocked = tmp_path / "blocked-file"
        blocked.write_text("")  # a FILE where a directory is needed
        monkeypatch.setenv("XDG_STATE_HOME", str(blocked))
        checks = {c["name"]: c for c in check_dispatch_health()}
        assert checks["audit-trace"]["ok"] is False
        assert "NOT writable" in checks["audit-trace"]["detail"]

    def test_doctor_never_marks_dispatch_required(self, isolated_state):
        # Fail-open debt warns; it must not flip doctor to UNHEALTHY on its own.
        _write_dispatcher_failure("check_error", [{"check": "x", "error": "y"}])
        assert all(c["required"] is False for c in check_dispatch_health())


class TestReportDispatchFailures:
    def test_dispatch_failures_in_effectiveness(self, isolated_state):
        trace_mod.log_decision(hook="post-edit", status="pass")
        for _ in range(2):
            _write_dispatcher_failure(
                "check_error", [{"check": "quality_gate", "error": "boom"}])
        _write_dispatcher_failure("input_error", [{"detail": "bad json"}])
        report = compute_effectiveness(days=1)
        assert report["dispatch_failures"]["check_error"] == 2
        assert report["dispatch_failures"]["input_error"] == 1
        assert report["failing_checks"][0] == ("quality_gate", 2)

    def test_no_dispatch_failures_yields_empty_section(self, isolated_state):
        trace_mod.log_decision(hook="post-edit", status="pass")
        report = compute_effectiveness(days=1)
        assert report["dispatch_failures"] == {}
        assert report["failing_checks"] == []


class TestProbeWritable:
    def test_ok_when_writable(self, isolated_state):
        ok, detail = trace_mod.probe_writable()
        assert ok is True
        assert detail.endswith("trace.jsonl")

    def test_fails_when_blocked(self, tmp_path, monkeypatch):
        blocked = tmp_path / "blocked-file"
        blocked.write_text("")
        monkeypatch.setenv("XDG_STATE_HOME", str(blocked))
        ok, detail = trace_mod.probe_writable()
        assert ok is False
        assert detail  # carries the error message


class TestDoctorJsonContract:
    def test_doctor_main_includes_new_checks(self, isolated_state, monkeypatch, capsys):
        from fettle import doctor as doctor_mod
        monkeypatch.setattr("sys.argv", ["doctor", "--json"])
        rc = doctor_mod.main()
        payload = json.loads(capsys.readouterr().out)
        names = {c["name"] for c in payload["checks"]}
        assert {"audit-trace", "dispatch"} <= names
        assert rc in (0, 1)  # contract unchanged: only required tools flip it
