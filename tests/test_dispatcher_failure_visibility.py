"""Stage-0 failure visibility — dispatcher fail-open paths leave trace evidence.

Non-negotiable under test: no silent failures. A check crash, a budget kill,
bad stdin, a config-load failure, or a registry failure must produce a
persistent trace entry, and chronic check failures must surface in-session.
"""

import io
import json
import time

import pytest

from fettle import dispatcher as dispatcher_mod
from fettle import trace as trace_mod
from fettle.finding import CheckFinding, EvidenceReference, FindingSeverity
from fettle.dispatcher_types import CheckResult, CheckSpec


@pytest.fixture
def isolated_trace(tmp_path, monkeypatch):
    """Point the trace at a temp dir; return a reader for its entries."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    def read_entries() -> list[dict]:
        path = tmp_path / "state" / "fettle" / "trace.jsonl"
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    return read_entries


def _payload(event: str = "PostToolUse") -> str:
    return json.dumps({
        "hook_event_name": event,
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/x.py"},
        "cwd": "/tmp",
        "session_id": "s0-test",
    })


def _crashing_spec() -> CheckSpec:
    def boom(_ctx):
        raise RuntimeError("injected fault")
    return CheckSpec(
        name="fault_injected",
        run=boom,
        events=frozenset({"PostToolUse"}),
    )


def _run_main(monkeypatch, capsys, stdin_text: str) -> tuple[int, dict]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    rc = dispatcher_mod.main()
    out = capsys.readouterr().out.strip().splitlines()[-1]
    return rc, json.loads(out)


class TestCheckCrashVisibility:
    def test_check_crash_writes_check_error_trace(self, monkeypatch, capsys, isolated_trace):
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: [_crashing_spec()])
        rc, out = _run_main(monkeypatch, capsys, _payload())
        assert rc == 0  # still fail-open
        errors = [e for e in isolated_trace()
                  if e.get("hook") == "dispatcher" and e.get("status") == "check_error"]
        assert len(errors) == 1
        assert errors[0]["findings"][0]["check"] == "fault_injected"
        assert "RuntimeError" in errors[0]["findings"][0]["error"]

    def test_repeated_crashes_escalate_to_advisory(self, monkeypatch, capsys, isolated_trace):
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: [_crashing_spec()])
        contexts = []
        for _ in range(3):
            rc, out = _run_main(monkeypatch, capsys, _payload())
            assert rc == 0
            contexts.append(out.get("hookSpecificOutput", {}).get("additionalContext", ""))
        # First two runs: silent fail-open. Third: visible escalation.
        assert "fail-open" not in contexts[0]
        assert "fault_injected" in contexts[2]
        assert "fettle doctor" in contexts[2]

    def test_single_crash_does_not_advise(self, monkeypatch, capsys, isolated_trace):
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: [_crashing_spec()])
        _, out = _run_main(monkeypatch, capsys, _payload())
        assert "fail-open" not in out.get("hookSpecificOutput", {}).get("additionalContext", "")


class TestStructuredResultVisibility:
    def test_result_findings_and_evidence_are_traced(self, monkeypatch, capsys, isolated_trace):
        finding = CheckFinding(
            checker="ruff", severity=FindingSeverity.ERROR, file="x.py", line=1,
            message="unused import",
        )
        result = CheckResult.advisory(
            "fix import", findings=[finding],
            evidence=[EvidenceReference("ev-ruff123", "command")],
        )
        spec = CheckSpec(
            name="ruff", run=lambda _ctx: result, events=frozenset({"PostToolUse"}),
        )
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: [spec])

        rc, _ = _run_main(monkeypatch, capsys, _payload())

        assert rc == 0
        entries = [e for e in isolated_trace() if e.get("hook") == "ruff"]
        assert entries[0]["findings"][0]["checker"] == "ruff"
        assert entries[0]["evidence"][0]["evidence_id"] == "ev-ruff123"

    def test_stale_failures_outside_window_do_not_escalate(self, monkeypatch, capsys, isolated_trace):
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: [_crashing_spec()])
        # Two old failures beyond the 24h window
        old_ts = time.time() - (25 * 3600)
        for _ in range(2):
            _, _ = _run_main(monkeypatch, capsys, _payload())
        trace_path = None
        entries = isolated_trace()
        # Rewrite entries as stale
        import os
        state = os.environ["XDG_STATE_HOME"]
        trace_path = os.path.join(state, "fettle", "trace.jsonl")
        stale = []
        for e in entries:
            e["ts"] = old_ts
            stale.append(json.dumps(e))
        with open(trace_path, "w") as f:
            f.write("\n".join(stale) + "\n")
        _, out = _run_main(monkeypatch, capsys, _payload())
        assert "fail-open" not in out.get("hookSpecificOutput", {}).get("additionalContext", "")


class TestDispatchLevelFailures:
    def test_bad_stdin_traces_input_error(self, monkeypatch, capsys, isolated_trace):
        rc, out = _run_main(monkeypatch, capsys, "{not json")
        assert rc == 0
        statuses = [e["status"] for e in isolated_trace() if e.get("hook") == "dispatcher"]
        assert "input_error" in statuses

    def test_config_failure_traces_config_error(self, monkeypatch, capsys, isolated_trace):
        def bad_config(_cwd):
            raise ValueError("injected config fault")
        monkeypatch.setattr(dispatcher_mod, "load_config", bad_config)
        rc, _ = _run_main(monkeypatch, capsys, _payload())
        assert rc == 0
        entries = [e for e in isolated_trace()
                   if e.get("hook") == "dispatcher" and e.get("status") == "config_error"]
        assert entries and "injected config fault" in entries[0]["findings"][0]["detail"]

    def test_registry_failure_traces_registry_error(self, monkeypatch, capsys, isolated_trace):
        def bad_registry(_ctx):
            raise KeyError("injected registry fault")
        monkeypatch.setattr(dispatcher_mod, "select_checks", bad_registry)
        rc, _ = _run_main(monkeypatch, capsys, _payload())
        assert rc == 0
        statuses = [e["status"] for e in isolated_trace() if e.get("hook") == "dispatcher"]
        assert "registry_error" in statuses

    def test_budget_exhaustion_traces(self, monkeypatch, capsys, isolated_trace):
        slow_then_skipped = []

        def slow(_ctx):
            time.sleep(0.05)
            return CheckResult.allow()

        specs = [
            CheckSpec(name="slow_check", run=slow, events=frozenset({"PostToolUse"})),
            CheckSpec(name="never_runs", run=lambda ctx: CheckResult.allow(),
                      events=frozenset({"PostToolUse"})),
        ]
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: specs)
        monkeypatch.setattr(dispatcher_mod, "load_config",
                            lambda cwd: {"dispatcher": {"global_budget_ms": 1}})
        rc, _ = _run_main(monkeypatch, capsys, _payload())
        assert rc == 0
        entries = [e for e in isolated_trace()
                   if e.get("hook") == "dispatcher" and e.get("status") == "budget_exhausted"]
        assert entries
        assert entries[0]["findings"][0]["skipped_from"] == "never_runs"
        del slow_then_skipped


class TestTraceWriteFailureVisibility:
    def test_log_decision_returns_false_and_warns_once(self, monkeypatch, capsys, tmp_path):
        blocked = tmp_path / "blocked-file"
        blocked.write_text("")  # a FILE where a directory is needed
        monkeypatch.setenv("XDG_STATE_HOME", str(blocked))
        monkeypatch.setattr(trace_mod, "_write_failure_warned", False)
        ok1 = trace_mod.log_decision(hook="t", status="pass")
        ok2 = trace_mod.log_decision(hook="t", status="pass")
        assert ok1 is False and ok2 is False
        err = capsys.readouterr().err
        assert err.count("audit trace write failed") == 1  # warn once, no spam

    def test_log_decision_returns_true_on_success(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        assert trace_mod.log_decision(hook="t", status="pass") is True


class TestReadTail:
    def test_reads_recent_entries(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        for i in range(5):
            trace_mod.log_decision(hook="h", status=f"s{i}")
        tail = trace_mod.read_tail()
        assert [e["status"] for e in tail] == [f"s{i}" for i in range(5)]

    def test_bounded_read_discards_partial_first_line(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        for i in range(200):
            trace_mod.log_decision(hook="h", status=f"s{i}", file="x" * 200)
        tail = trace_mod.read_tail(max_bytes=2048)
        assert tail  # got some entries
        assert all(isinstance(e, dict) for e in tail)
        assert tail[-1]["status"] == "s199"

    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        assert trace_mod.read_tail() == []
