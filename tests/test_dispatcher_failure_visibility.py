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


def _crashing_security_spec() -> CheckSpec:
    def boom(_ctx):
        raise RuntimeError("scanner leaked ghp_1234567890abcdefghijklmnopqrstuvwxyz")
    return CheckSpec(
        name="runtime_secret_guard",
        run=boom,
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Read"}),
        fail_closed=True,
    )


def _run_main(monkeypatch, capsys, stdin_text: str) -> tuple[int, dict]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    rc = dispatcher_mod.main()
    out = capsys.readouterr().out.strip().splitlines()[-1]
    return rc, json.loads(out)


class TestCheckCrashVisibility:
    def test_security_check_crash_blocks_without_exception_detail(
        self, monkeypatch, capsys, caplog, isolated_trace
    ):
        monkeypatch.setattr(
            dispatcher_mod, "select_checks", lambda ctx: [_crashing_security_spec()]
        )
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/config.json"},
            "cwd": "/tmp",
            "session_id": "s0-test",
        })

        rc, out = _run_main(monkeypatch, capsys, payload)

        serialized = json.dumps(out)
        assert rc == 2
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "fettle doctor" in out["reason"]
        assert "ghp_" not in serialized
        assert "ghp_" not in caplog.text
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
    def test_corrupt_policy_file_blocks_before_checks(
        self, tmp_path, monkeypatch, capsys, isolated_trace
    ):
        config = tmp_path / "policy.toml"
        config.write_text("[gates.tests\nenabled = true\n")
        monkeypatch.setenv("FETTLE_CONFIG", str(config))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setattr(dispatcher_mod, "select_checks",
                            lambda ctx: pytest.fail("corrupt policy must not run checks"))

        code, output = _run_main(monkeypatch, capsys, _payload("Stop"))

        assert code == 2
        assert "fettle doctor" in output["reason"]

    @pytest.mark.parametrize("config", [
        None,
        {"gates": []},
        {"dispatcher": []},
        {"dispatcher": {"checks": []}},
        {"gates": {"advisory": {"max_per_turn": "not-an-integer"}}},
        {"gates": {"tests": []}},
    ])
    def test_malformed_runtime_policy_is_nonpass(
        self, monkeypatch, capsys, isolated_trace, config
    ):
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: config)
        monkeypatch.setattr(dispatcher_mod, "select_checks",
                            lambda ctx: pytest.fail("invalid policy must not select checks"))

        code, output = _run_main(monkeypatch, capsys, _payload("Stop"))

        assert code == 2
        assert "hookSpecificOutput" not in output
        assert "fettle doctor" in output["reason"]

    @pytest.mark.parametrize("name,event,active,expected", [
        ("mcp_trust_gate", "PreToolUse", True, 2),
        ("mcp_trust_gate", "PreToolUse", False, 0),
        ("capsule_guard", "PreToolUse", True, 2),
        ("capsule_guard", "PreToolUse", False, 0),
        ("stop_quality_gate", "Stop", True, 2),
    ])
    def test_enabled_only_guards_cannot_fail_open(
        self, monkeypatch, capsys, isolated_trace, name, event, active, expected
    ):
        from dataclasses import replace
        from fettle.dispatcher_registry import CHECKS

        guard = next(spec for spec in CHECKS if spec.name == name)
        monkeypatch.setattr(dispatcher_mod, "select_checks",
                            lambda ctx: [replace(guard, run=_crashing_spec().run)])
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"mcp_trust": {"enabled": active}},
        })
        monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
        if name == "capsule_guard" and active:
            monkeypatch.setenv("FETTLE_POLICY_CAPSULE", "/missing/fixture-capsule.json")

        code, output = _run_main(monkeypatch, capsys, _payload(event))

        assert code == expected
        if expected:
            assert name in output["reason"]

    @pytest.mark.parametrize("event,gate,tool,expected", [
        ("Stop", "tests", "Write", 2),
        ("PreToolUse", "plan", "Write", 2),
        ("PreToolUse", "ux_spec", "Edit", 2),
        ("PreToolUse", "ci_bootstrap", "Write", 2),
        ("PostToolUse", "plan", "Write", 0),
        ("PostToolUse", "ux_spec", "Edit", 0),
        ("PreToolUse", "plan", "Bash", 0),
        ("PreToolUse", "ui_colors", "Write", 0),
    ])
    @pytest.mark.parametrize("failure", ["exception", "unknown", "budget"])
    def test_compound_quality_gate_preserves_event_policy(
        self, monkeypatch, capsys, isolated_trace, event, gate, tool, expected, failure
    ):
        from dataclasses import replace
        from fettle.dispatcher_registry import CHECKS

        quality = next(spec for spec in CHECKS if spec.name == "quality_gate")
        runner = (_crashing_spec().run if failure == "exception" else
                  lambda ctx: CheckResult.unknown("unavailable", action="retry"))
        monkeypatch.setattr(dispatcher_mod, "select_checks",
                            lambda ctx: [replace(quality, run=runner)])
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "dispatcher": {"global_budget_ms": 1 if failure == "budget" else 1000},
            "gates": {gate: {"enabled": True, "mode": "enforce"}},
        })
        if failure == "budget":
            ticks = iter((10.0, 10.01))
            monkeypatch.setattr(dispatcher_mod.time, "monotonic", lambda: next(ticks))
        payload = json.loads(_payload(event))
        payload["tool_name"] = tool

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == expected
        if expected:
            assert "quality_gate" in output["reason"]

    @pytest.mark.parametrize("event,gate", [("Stop", "completion"), ("PostToolUse", "lint")])
    @pytest.mark.parametrize("mode,expected", [("enforce", 2), ("advisory", 0)])
    def test_registry_failure_preserves_required_policy(
        self, monkeypatch, capsys, isolated_trace, event, gate, mode, expected
    ):
        def bad_registry(_ctx):
            raise RuntimeError("injected registry fault")

        monkeypatch.setattr(dispatcher_mod, "select_checks", bad_registry)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "dispatcher": {"disabled_checks": ["stop_quality_gate"]},
            "gates": {gate: {"enabled": True, "mode": mode}},
        })

        code, output = _run_main(monkeypatch, capsys, _payload(event))

        assert code == expected
        assert "fettle doctor" in json.dumps(output)
        if expected:
            assert output["decision"] == "block"
        if event == "Stop":
            assert "hookSpecificOutput" not in output

    def test_registry_failure_cannot_bypass_secret_guard(
        self, monkeypatch, capsys, isolated_trace
    ):
        def bad_registry(_ctx):
            raise RuntimeError("injected registry fault")

        monkeypatch.setattr(dispatcher_mod, "select_checks", bad_registry)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {})

        code, output = _run_main(monkeypatch, capsys, _payload("PreToolUse"))

        assert code == 2
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.parametrize("state", ["tool_error", "unknown", "missing"])
    @pytest.mark.parametrize("mode,expected", [("enforce", 2), ("advisory", 0)])
    def test_incomplete_required_result_is_nonpass(
        self, monkeypatch, capsys, isolated_trace, state, mode, expected
    ):
        result = None if state == "missing" else getattr(CheckResult, state)("unavailable", action="retry")
        spec = CheckSpec(name="required", run=lambda ctx: result,
                         events=frozenset({"PreToolUse"}), policy_gates=("destructive",))
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: [spec])
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"destructive": {"enabled": True, "mode": mode}},
        })

        code, output = _run_main(monkeypatch, capsys, _payload("PreToolUse"))

        assert code == expected
        if expected:
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert "fettle doctor" in output["reason"]

    def test_artifact_policy_uses_owning_config_key(self):
        from fettle.dispatcher_registry import CHECKS

        artifact = next(spec for spec in CHECKS if spec.name == "artifact_gate")
        assert artifact.requires_execution({"gates": {
            "artifact_integrity": {"enabled": True, "mode": "enforce"},
        }})
        assert not artifact.requires_execution({"gates": {
            "artifact_integrity": {"enabled": False, "mode": "enforce"},
        }})

    @pytest.mark.parametrize("mode,expected", [("enforce", 2), ("advisory", 0)])
    def test_budget_checks_all_remaining_required_gates(
        self, monkeypatch, capsys, isolated_trace, mode, expected
    ):
        from fettle.dispatcher_registry import CHECKS

        destructive = next(spec for spec in CHECKS if spec.name == "destructive_guard")
        optional = CheckSpec(name="optional", run=lambda ctx: pytest.fail("budget exhausted"),
                             events=frozenset({"PreToolUse"}))
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: [optional, destructive])
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "dispatcher": {"global_budget_ms": 1},
            "gates": {"destructive": {"enabled": True, "mode": mode}},
        })
        ticks = iter((10.0, 10.01))
        monkeypatch.setattr(dispatcher_mod.time, "monotonic", lambda: next(ticks))

        code, output = _run_main(monkeypatch, capsys, _payload("PreToolUse"))

        assert code == expected
        if expected == 2:
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert "destructive_guard" in output["reason"]

    def test_enforced_check_exception_blocks(self, monkeypatch, capsys, isolated_trace):
        from dataclasses import replace
        from fettle.dispatcher_registry import CHECKS

        destructive = next(spec for spec in CHECKS if spec.name == "destructive_guard")
        destructive = replace(destructive, run=_crashing_spec().run)
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: [destructive])
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"destructive": {"enabled": True, "mode": "enforce"}},
        })

        code, output = _run_main(monkeypatch, capsys, _payload("PreToolUse"))

        assert code == 2
        assert "fettle doctor" in output["reason"]
        assert "injected fault" not in json.dumps(output)

    def test_bad_stdin_traces_input_error(self, monkeypatch, capsys, isolated_trace):
        rc, out = _run_main(monkeypatch, capsys, "{not json")
        assert rc == 0
        statuses = [e["status"] for e in isolated_trace() if e.get("hook") == "dispatcher"]
        assert "input_error" in statuses

    @pytest.mark.parametrize("event", ["PreToolUse", "PostToolUse", "Stop"])
    def test_config_failure_traces_config_error(self, monkeypatch, capsys, isolated_trace, event):
        def bad_config(_cwd, **kwargs):
            raise ValueError("injected config fault")
        monkeypatch.setattr(dispatcher_mod, "load_config", bad_config)
        monkeypatch.setattr(dispatcher_mod, "select_checks",
                            lambda ctx: pytest.fail("unknown policy must not run checks"))
        rc, output = _run_main(monkeypatch, capsys, _payload(event))
        assert rc == 2
        assert output["decision"] == "block"
        assert "fettle doctor" in output["reason"]
        assert "injected config fault" not in json.dumps(output)
        if event == "Stop":
            assert "hookSpecificOutput" not in output
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
                            lambda cwd, **kwargs: {"dispatcher": {"global_budget_ms": 1}})
        rc, _ = _run_main(monkeypatch, capsys, _payload())
        assert rc == 0
        entries = [e for e in isolated_trace()
                   if e.get("hook") == "dispatcher" and e.get("status") == "budget_exhausted"]
        assert entries
        assert entries[0]["findings"][0]["skipped_from"] == "never_runs"
        del slow_then_skipped

    def test_security_check_budget_exhaustion_blocks(self, monkeypatch, capsys, isolated_trace):
        spec = CheckSpec(
            name="runtime_secret_guard",
            run=lambda ctx: CheckResult.allow(),
            events=frozenset({"PreToolUse"}),
            tools=frozenset({"Read"}),
            fail_closed=True,
        )
        monkeypatch.setattr(dispatcher_mod, "select_checks", lambda ctx: [spec])
        monkeypatch.setattr(
            dispatcher_mod, "load_config", lambda cwd, **kwargs: {"dispatcher": {"global_budget_ms": 1}}
        )
        ticks = iter((10.0, 10.01))
        monkeypatch.setattr(dispatcher_mod.time, "monotonic", lambda: next(ticks))

        rc, out = _run_main(monkeypatch, capsys, json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/config.json"},
            "cwd": "/tmp",
            "session_id": "s0-test",
        }))

        assert rc == 2
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


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
