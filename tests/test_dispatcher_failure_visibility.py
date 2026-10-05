"""Stage-0 failure visibility — dispatcher fail-open paths leave trace evidence.

Non-negotiable under test: no silent failures. A check crash, a budget kill,
bad stdin, a config-load failure, or a registry failure must produce a
persistent trace entry, and chronic check failures must surface in-session.
"""

import io
import json
import time
from types import SimpleNamespace

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
    @pytest.mark.parametrize(("name", "tool", "gates"), [
        ("runtime_secret_guard", "Read", {}),
        ("mcp_trust_gate", "Bash", {"mcp_trust": {"enabled": True, "mode": "enforce"}}),
        ("destructive_guard", "Bash", {"destructive": {"enabled": True, "mode": "enforce"}}),
    ])
    def test_real_registry_honors_public_check_disable(
        self, monkeypatch, capsys, isolated_trace, name, tool, gates
    ):
        """A named dispatcher disable must prevent that exact gate from executing."""
        from fettle import dispatcher_registry

        def import_check(module):
            result = CheckResult.block("disabled gate executed") if module == f"fettle.{name}" else CheckResult.allow()
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": gates,
            "dispatcher": {
                "global_budget_ms": 1000,
                "checks": {name: {"enabled": False}},
            },
        })
        payload = json.loads(_payload("PreToolUse"))
        payload["tool_name"] = tool

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"

    @pytest.mark.parametrize(("name", "tool", "gate"), [
        ("config_protect", "Write", "config_protect"),
        ("config_protect", "Edit", "config_protect"),
        ("agent_spawn_gate", "Bash", "agent_spawn"),
        ("commit_message", "Bash", "commit_message"),
        ("destructive_guard", "Bash", "destructive"),
        ("release_gate", "Bash", "release"),
        ("artifact_gate", "Bash", "artifact_integrity"),
    ])
    def test_real_registry_enforced_gate_incomplete_result_blocks(
        self, monkeypatch, capsys, isolated_trace, name, tool, gate
    ):
        """The configured policy owner must make its incomplete result non-passing."""
        from fettle import dispatcher_registry

        def import_check(module):
            result = (
                CheckResult.unknown("required evidence unavailable", action="retry")
                if module == f"fettle.{name}"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {gate: {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("PreToolUse"))
        payload["tool_name"] = tool

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert f"Required check '{name}' did not complete." in output["reason"]

    @pytest.mark.parametrize(("name", "module", "gate"), [
        ("verify_gate", "fettle.verify_gate", "verify"),
        ("ci_gate", "fettle.ci_gate", "ci"),
        ("completion_gate", "fettle.completion_gate", "completion"),
        ("coverage_gate", "fettle.coverage_gate", "coverage"),
    ])
    def test_real_registry_stop_enforcement_incomplete_result_blocks(
        self, monkeypatch, capsys, isolated_trace, name, module, gate
    ):
        """A final-decision gate cannot disappear or fail open at Stop."""
        from fettle import dispatcher_registry

        def import_check(imported):
            result = (
                CheckResult.unknown("required evidence unavailable", action="retry")
                if imported == module
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {gate: {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"global_budget_ms": 1000},
        })

        code, output = _run_main(monkeypatch, capsys, _payload("Stop"))

        assert code == 2
        assert "hookSpecificOutput" not in output
        assert f"Required check '{name}' did not complete." in output["reason"]

    @pytest.mark.parametrize(("tool", "suffix"), [
        ("Write", ".json"),
        ("Write", ".md"),
        ("Edit", ".json"),
        ("Edit", ".md"),
    ])
    def test_real_registry_completion_manifest_enforcement_blocks(
        self, tmp_path, monkeypatch, capsys, isolated_trace, tool, suffix
    ):
        """Incomplete completion validation must block every supported manifest edit."""
        from fettle import dispatcher_registry

        def import_check(module):
            result = (
                CheckResult.unknown("completion evidence unavailable", action="retry")
                if module == "fettle.completion_gate"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"completion": {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = tool
        payload["tool_input"]["file_path"] = str(tmp_path / f"milestone{suffix}")

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert output["decision"] == "block"
        assert "Required check 'completion_manifest_gate' did not complete." in output["reason"]

    def test_real_registry_policy_capsule_incomplete_result_blocks(
        self, monkeypatch, capsys, isolated_trace
    ):
        """An active delegated-policy capsule must reach its owning guard."""
        from fettle import dispatcher_registry

        def import_check(module):
            result = (
                CheckResult.unknown("capsule unavailable", action="retry")
                if module == "fettle.capsule_guard"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setenv("FETTLE_POLICY_CAPSULE", "/missing/fixture-capsule.json")
        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {}, "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("PreToolUse"))
        payload["tool_name"] = "Bash"

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert "Required check 'capsule_guard' did not complete." in output["reason"]

    def test_real_registry_output_guard_replaces_post_tool_output(
        self, monkeypatch, capsys, isolated_trace
    ):
        """Post-tool output sanitization must reach the runtime output owner."""
        from fettle import dispatcher_registry

        def import_check(module):
            result = (
                CheckResult(
                    hook_specific_output={"updatedToolOutput": "sanitized output"},
                )
                if module == "fettle.runtime_output_guard"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {}, "dispatcher": {"global_budget_ms": 1000},
        })

        code, output = _run_main(monkeypatch, capsys, _payload("PostToolUse"))

        assert code == 0
        assert output["hookSpecificOutput"]["updatedToolOutput"] == "sanitized output"

    def test_real_registry_output_guard_honors_public_disable(
        self, monkeypatch, capsys, isolated_trace
    ):
        """Disabling the output guard by its public name must prevent execution."""
        from fettle import dispatcher_registry

        def import_check(module):
            result = (
                CheckResult.block("disabled output guard executed")
                if module == "fettle.runtime_output_guard"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {},
            "dispatcher": {
                "global_budget_ms": 1000,
                "checks": {"runtime_output_guard": {"enabled": False}},
            },
        })

        code, output = _run_main(monkeypatch, capsys, _payload("PostToolUse"))

        assert code == 0
        assert output.get("decision") != "block"

    def test_real_registry_stop_quality_incomplete_result_blocks(
        self, monkeypatch, capsys, isolated_trace
    ):
        """The always-required Stop quality owner cannot disappear or fail open."""
        from fettle import dispatcher_registry

        def import_check(module):
            result = (
                CheckResult.unknown("stop quality unavailable", action="retry")
                if module == "fettle.stop_quality_gate"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {}, "dispatcher": {"global_budget_ms": 1000},
        })

        code, output = _run_main(monkeypatch, capsys, _payload("Stop"))

        assert code == 2
        assert "hookSpecificOutput" not in output
        assert "Required check 'stop_quality_gate' did not complete." in output["reason"]

    def test_real_registry_required_quality_gate_incomplete_result_blocks(
        self, monkeypatch, capsys, isolated_trace
    ):
        """An enforced test gate at Stop must reach the quality owner."""
        from fettle import dispatcher_registry

        def import_check(module):
            result = (
                CheckResult.unknown("quality evidence unavailable", action="retry")
                if module == "fettle.quality_gate"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"tests": {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"global_budget_ms": 1000},
        })

        code, output = _run_main(monkeypatch, capsys, _payload("Stop"))

        assert code == 2
        assert "Required check 'quality_gate' did not complete." in output["reason"]

    @pytest.mark.parametrize(("name", "event", "tool", "gate"), [
        ("authorship_gate", "PreToolUse", "Write", "authorship"),
        ("authorship_gate", "PreToolUse", "Edit", "authorship"),
        ("tdd_gate", "PreToolUse", "Write", "tdd"),
        ("tdd_gate", "PostToolUse", "Edit", "tdd"),
        ("bdd_gate", "PostToolUse", "Write", "bdd"),
        ("claims_gate", "PostToolUse", "Write", "claims"),
        ("claims_gate", "PostToolUse", "Edit", "claims"),
    ])
    def test_real_registry_lifecycle_gate_incomplete_result_blocks(
        self, tmp_path, monkeypatch, capsys, isolated_trace, name, event, tool, gate
    ):
        """An enforced lifecycle gate must run for each supported event and tool."""
        from fettle import dispatcher_registry

        def import_check(module):
            result = (
                CheckResult.unknown("lifecycle evidence unavailable", action="retry")
                if module == f"fettle.{name}"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {gate: {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload(event))
        payload["tool_name"] = tool
        payload["tool_input"]["file_path"] = str(tmp_path / "change.py")

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert f"Required check '{name}' did not complete." in output["reason"]

    @pytest.mark.parametrize(("name", "module", "gate", "tool"), [
        ("adapter_check", "fettle.adapter_check", "lint", "Write"),
        ("adapter_check", "fettle.adapter_check", "lint", "Edit"),
        ("complexity_check", "fettle.complexity_check", "complexity", "Write"),
        ("complexity_check", "fettle.complexity_check", "complexity", "Edit"),
    ])
    def test_real_registry_post_edit_enforcement_incomplete_result_blocks(
        self, tmp_path, monkeypatch, capsys, isolated_trace, name, module, gate, tool
    ):
        """Enforced Python analysis must run after every supported edit operation."""
        from fettle import dispatcher_registry

        def import_check(imported):
            result = (
                CheckResult.unknown("analysis evidence unavailable", action="retry")
                if imported == module
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {gate: {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = tool
        payload["tool_input"]["file_path"] = str(tmp_path / "change.py")

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert f"Required check '{name}' did not complete." in output["reason"]

    @pytest.mark.parametrize(("name", "module", "tool"), [
        ("boundary_rules", "fettle.boundary_rules", "Write"),
        ("boundary_rules", "fettle.boundary_rules", "Edit"),
        ("provenance_gate", "fettle.provenance_gate", "Write"),
    ])
    def test_real_registry_post_edit_integrity_violation_blocks(
        self, tmp_path, monkeypatch, capsys, isolated_trace, name, module, tool
    ):
        """A detected file-integrity violation must survive real dispatcher routing."""
        from fettle import dispatcher_registry

        marker = f"{name} detected a violation"

        def import_check(imported):
            result = CheckResult.block(marker) if imported == module else CheckResult.allow()
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {}, "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = tool
        payload["tool_input"]["file_path"] = str(tmp_path / "change.py")

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert output["decision"] == "block"
        assert marker in output["reason"]

    @pytest.mark.parametrize(("name", "module"), [
        ("boundary_rules", "fettle.boundary_rules"),
        ("provenance_gate", "fettle.provenance_gate"),
    ])
    def test_real_registry_post_edit_integrity_honors_public_disable(
        self, tmp_path, monkeypatch, capsys, isolated_trace, name, module
    ):
        """A named integrity-check disable must prevent that exact owner from running."""
        from fettle import dispatcher_registry

        def import_check(imported):
            result = (
                CheckResult.block("disabled integrity check executed")
                if imported == module
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {},
            "dispatcher": {
                "global_budget_ms": 1000,
                "checks": {name: {"enabled": False}},
            },
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = "Write"
        payload["tool_input"]["file_path"] = str(tmp_path / "change.py")

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("decision") != "block"

    def test_real_registry_records_push_for_later_ci_verification(
        self, tmp_path, monkeypatch, capsys, isolated_trace
    ):
        """A completed git push must reach the passive CI session recorder."""
        from fettle import ci_gate

        pushes = tmp_path / "pushes.jsonl"
        monkeypatch.setattr(ci_gate, "_head_sha", lambda cwd: "abc123")
        monkeypatch.setattr(ci_gate, "_pushes_path", lambda session_id: pushes)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"ci": {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = "Bash"
        payload["tool_input"]["command"] = "git push origin HEAD"

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("decision") != "block"
        entry = json.loads(pushes.read_text())
        assert entry["sha"] == "abc123"
        assert entry["command"] == "git push origin HEAD"

    @pytest.mark.parametrize(("name", "module", "tool"), [
        ("lean_sniffers", "fettle.lean_sniffers", "Write"),
        ("lean_sniffers", "fettle.lean_sniffers", "Edit"),
        ("tla_sync", "fettle.tla_sync", "Write"),
        ("tla_sync", "fettle.tla_sync", "Edit"),
        ("loop_detect", "fettle.loop_detect", "Write"),
        ("loop_detect", "fettle.loop_detect", "Edit"),
        ("loop_detect", "fettle.loop_detect", "Bash"),
        ("loop_detect", "fettle.loop_detect", "Read"),
        ("scope_creep", "fettle.scope_creep", "Write"),
        ("scope_creep", "fettle.scope_creep", "Edit"),
        ("scope_creep", "fettle.scope_creep", "Bash"),
    ])
    def test_real_registry_post_tool_diagnostic_is_visible(
        self, tmp_path, monkeypatch, capsys, isolated_trace, name, module, tool
    ):
        """Optional diagnostics must reach users on every registered tool route."""
        from fettle import dispatcher_registry

        marker = f"{name} diagnostic"

        def import_check(imported):
            result = CheckResult.advisory(marker) if imported == module else CheckResult.allow()
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {}, "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = tool
        payload["tool_input"]["file_path"] = str(tmp_path / "change.py")

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert marker in output["hookSpecificOutput"]["additionalContext"]

    @pytest.mark.parametrize(("name", "module"), [
        ("lean_sniffers", "fettle.lean_sniffers"),
        ("tla_sync", "fettle.tla_sync"),
        ("scope_creep", "fettle.scope_creep"),
    ])
    def test_real_registry_post_tool_diagnostic_honors_public_disable(
        self, tmp_path, monkeypatch, capsys, isolated_trace, name, module
    ):
        """A named optional diagnostic disable must prevent that owner from running."""
        from fettle import dispatcher_registry

        def import_check(imported):
            result = (
                CheckResult.block("disabled diagnostic executed")
                if imported == module
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {},
            "dispatcher": {
                "global_budget_ms": 1000,
                "checks": {name: {"enabled": False}},
            },
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = "Write"
        payload["tool_input"]["file_path"] = str(tmp_path / "change.py")

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("decision") != "block"

    def test_real_registry_post_bash_doc_violation_blocks(self, monkeypatch, capsys, isolated_trace):
        """An enforced documentation violation must survive the Bash result boundary."""
        from fettle import dispatcher_registry

        marker = "documentation update required"

        def import_check(imported):
            result = (
                CheckResult.block(marker)
                if imported == "fettle.post_bash_doc_check"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"docs": {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = "Bash"
        payload["tool_input"]["command"] = "git push origin HEAD"

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert marker in output["reason"]

    def test_real_registry_post_bash_doc_honors_public_disable(
        self, monkeypatch, capsys, isolated_trace
    ):
        """Disabling the named post-Bash check must prevent its owner from running."""
        from fettle import dispatcher_registry

        def import_check(imported):
            result = (
                CheckResult.block("disabled documentation check executed")
                if imported == "fettle.post_bash_doc_check"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"docs": {"enabled": True, "mode": "enforce"}},
            "dispatcher": {
                "global_budget_ms": 1000,
                "checks": {"post_bash_doc_check": {"enabled": False}},
            },
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = "Bash"

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("decision") != "block"

    def test_real_registry_tla_stop_advisory_is_visible(self, monkeypatch, capsys, isolated_trace):
        """The end-of-session TLA staleness advisory must reach the Stop response."""
        from fettle import dispatcher_registry

        marker = "TLA+ specification may be stale"

        def import_check(imported):
            result = CheckResult.advisory(marker) if imported == "fettle.tla_sync" else CheckResult.allow()
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {}, "dispatcher": {"global_budget_ms": 1000},
        })

        code, output = _run_main(monkeypatch, capsys, _payload("Stop"))

        assert code == 0
        assert marker in output["systemMessage"]

    def test_real_registry_tla_stop_honors_public_disable(
        self, monkeypatch, capsys, isolated_trace
    ):
        """Disabling the named TLA Stop check must prevent that owner from running."""
        from fettle import dispatcher_registry

        def import_check(imported):
            result = (
                CheckResult.block("disabled TLA Stop check executed")
                if imported == "fettle.tla_sync"
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {},
            "dispatcher": {
                "global_budget_ms": 1000,
                "checks": {"tla_sync_stop": {"enabled": False}},
            },
        })

        code, output = _run_main(monkeypatch, capsys, _payload("Stop"))

        assert code == 0
        assert output.get("decision") != "block"

    def test_real_registry_session_report_writes_at_stop(
        self, tmp_path, monkeypatch, capsys, isolated_trace
    ):
        """An enabled session report must write through the real Stop pipeline."""
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"session_report": {"enabled": True}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("Stop"))
        payload["cwd"] = str(tmp_path)

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("decision") != "block"
        report = json.loads((tmp_path / ".fettle" / "reports" / "s0-test.json").read_text())
        assert report["session_id"] == "s0-test"

    def test_real_registry_session_report_honors_public_disable(
        self, tmp_path, monkeypatch, capsys, isolated_trace
    ):
        """Disabling session reporting by name must prevent its durable write."""
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"session_report": {"enabled": True}},
            "dispatcher": {
                "global_budget_ms": 1000,
                "checks": {"session_report": {"enabled": False}},
            },
        })
        payload = json.loads(_payload("Stop"))
        payload["cwd"] = str(tmp_path)

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("decision") != "block"
        assert not (tmp_path / ".fettle" / "reports" / "s0-test.json").exists()

    def test_real_registry_worklog_advisory_is_visible(
        self, tmp_path, monkeypatch, capsys, isolated_trace
    ):
        """An enabled missing-worklog finding must reach the Stop response."""
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"worklog": {"enabled": True, "mode": "advisory"}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("Stop"))
        payload["cwd"] = str(tmp_path)

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert "no worklog entry" in output["systemMessage"]

    def test_real_registry_worklog_honors_public_disable(
        self, tmp_path, monkeypatch, capsys, isolated_trace
    ):
        """Disabling worklog by name must suppress its Stop advisory."""
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"worklog": {"enabled": True, "mode": "advisory"}},
            "dispatcher": {
                "global_budget_ms": 1000,
                "checks": {"worklog": {"enabled": False}},
            },
        })
        payload = json.loads(_payload("Stop"))
        payload["cwd"] = str(tmp_path)

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert "worklog" not in json.dumps(output).lower()

    def test_real_registry_bash_audit_writes_event(
        self, tmp_path, monkeypatch, capsys, isolated_trace
    ):
        """An enabled Bash audit must persist an event through PostToolUse."""
        from fettle import config

        monkeypatch.setattr(config, "state_dir", lambda session_id: tmp_path)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"bash_audit": {"enabled": True}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = "Bash"
        payload["tool_input"]["command"] = "python -m pytest"
        payload["tool_response"] = {"exit_code": 0, "duration_ms": 123}

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("decision") != "block"
        event = json.loads((tmp_path / "bash_events.jsonl").read_text())
        assert event["exit_code"] == 0
        assert event["duration_ms"] == 123

    def test_real_registry_bash_audit_honors_public_disable(
        self, tmp_path, monkeypatch, capsys, isolated_trace
    ):
        """Disabling Bash audit by name must prevent its event write."""
        from fettle import config

        monkeypatch.setattr(config, "state_dir", lambda session_id: tmp_path)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {"bash_audit": {"enabled": True}},
            "dispatcher": {
                "global_budget_ms": 1000,
                "checks": {"bash_audit": {"enabled": False}},
            },
        })
        payload = json.loads(_payload("PostToolUse"))
        payload["tool_name"] = "Bash"

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("decision") != "block"
        assert not (tmp_path / "bash_events.jsonl").exists()

    @pytest.mark.parametrize(("event", "tool", "first", "first_module", "second", "second_module"), [
        ("PreToolUse", "Bash", "destructive_guard", "fettle.destructive_guard",
         "artifact_gate", "fettle.artifact_gate"),
        ("PreToolUse", "Bash", "agent_spawn_gate", "fettle.agent_spawn_gate",
         "release_gate", "fettle.release_gate"),
        ("PostToolUse", "Write", "tdd_gate", "fettle.tdd_gate",
         "bdd_gate", "fettle.bdd_gate"),
        ("PreToolUse", "Bash", "deploy_gate", "fettle.deploy_gate",
         "artifact_gate", "fettle.artifact_gate"),
        ("PreToolUse", "Bash", "artifact_gate", "fettle.artifact_gate",
         "agent_spawn_gate", "fettle.agent_spawn_gate"),
        ("Stop", "Write", "verify_gate", "fettle.verify_gate",
         "ci_gate", "fettle.ci_gate"),
    ])
    def test_real_registry_preserves_safety_precedence(
        self, monkeypatch, capsys, isolated_trace, event, tool,
        first, first_module, second, second_module
    ):
        """When two checks block, the earlier safety/recovery decision must win."""
        from fettle import dispatcher_registry

        def import_check(imported):
            if imported == first_module:
                result = CheckResult.block(f"first:{first}")
            elif imported == second_module:
                result = CheckResult.block(f"second:{second}")
            else:
                result = CheckResult.allow()
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {}, "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload(event))
        payload["tool_name"] = tool

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert f"first:{first}" in output["reason"]
        assert f"second:{second}" not in output["reason"]

    @pytest.mark.parametrize(("name", "event", "tool", "suffix", "budget_ms"), [
        ("runtime_secret_guard", "PreToolUse", "Read", ".py", 100),
        ("runtime_output_guard", "PostToolUse", "Write", ".py", 100),
        ("capsule_guard", "PreToolUse", "Write", ".py", 20),
        ("config_protect", "PreToolUse", "Write", ".toml", 50),
        ("quality_gate", "Stop", "Write", ".py", 120),
        ("mcp_trust_gate", "PreToolUse", "Bash", ".py", 60),
        ("destructive_guard", "PreToolUse", "Bash", ".py", 50),
        ("agent_spawn_gate", "PreToolUse", "Bash", ".py", 30),
        ("commit_message", "PreToolUse", "Bash", ".py", 50),
        ("adapter_check", "PostToolUse", "Write", ".py", 150),
        ("lean_sniffers", "PostToolUse", "Write", ".py", 200),
        ("post_bash_doc_check", "PostToolUse", "Bash", ".py", 80),
        ("tla_sync", "PostToolUse", "Write", ".py", 10),
        ("tla_sync_stop", "Stop", "Write", ".py", 20),
        ("loop_detect", "PostToolUse", "Read", ".py", 50),
        ("scope_creep", "PostToolUse", "Bash", ".py", 50),
        ("stop_quality_gate", "Stop", "Write", ".py", 300),
        ("authorship_gate", "PreToolUse", "Write", ".py", 20),
        ("tdd_gate", "PostToolUse", "Write", ".py", 50),
        ("bdd_gate", "PostToolUse", "Write", ".py", 200),
        ("claims_gate", "PostToolUse", "Write", ".py", 100),
        ("complexity_check", "PostToolUse", "Write", ".py", 100),
        ("deploy_gate", "PreToolUse", "Bash", ".py", 80),
        ("release_gate", "PreToolUse", "Bash", ".py", 50),
        ("artifact_gate", "PreToolUse", "Bash", ".py", 40),
        ("boundary_rules", "PostToolUse", "Write", ".py", 50),
        ("provenance_gate", "PostToolUse", "Write", ".py", 30),
        ("ci_push_record", "PostToolUse", "Bash", ".py", 100),
        ("ci_gate", "Stop", "Write", ".py", 100),
        ("completion_gate", "Stop", "Write", ".py", 100),
        ("completion_manifest_gate", "PostToolUse", "Write", ".json", 100),
        ("coverage_gate", "Stop", "Write", ".py", 100),
        ("session_report", "Stop", "Write", ".py", 50),
        ("worklog", "Stop", "Write", ".py", 50),
        ("bash_audit", "PostToolUse", "Bash", ".py", 30),
    ])
    def test_real_registry_delivers_each_owner_budget(
        self, tmp_path, monkeypatch, capsys, isolated_trace,
        name, event, tool, suffix, budget_ms
    ):
        """Each owner receives its policy deadline through the dispatcher boundary."""
        from fettle import dispatcher_registry

        observed = []

        def run_check(ctx):
            observed.append(ctx.check_deadline_monotonic)
            return CheckResult.allow()

        monkeypatch.setattr(
            dispatcher_registry, "import_module",
            lambda imported: SimpleNamespace(run_check=run_check, record_push=run_check),
        )
        checks = {spec.name: {"enabled": spec.name == name}
                  for spec in dispatcher_registry.CHECKS}
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {},
            "dispatcher": {"global_budget_ms": 1000, "checks": checks},
        })
        monkeypatch.setattr(dispatcher_mod.time, "monotonic", lambda: 10.0)
        payload = json.loads(_payload(event))
        payload["tool_name"] = tool
        payload["tool_input"]["file_path"] = str(tmp_path / f"change{suffix}")

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 0
        assert output.get("decision") != "block"
        assert observed == [pytest.approx(10.0 + budget_ms / 1000.0)]

    @pytest.mark.parametrize(("name", "module", "gate", "event"), [
        ("deploy_gate", "fettle.deploy_gate", "deploy_safety", "PreToolUse"),
        ("release_gate", "fettle.release_gate", "release", "PreToolUse"),
        ("artifact_gate", "fettle.artifact_gate", "artifact_integrity", "PreToolUse"),
        ("artifact_gate", "fettle.artifact_gate", "artifact_integrity", "PostToolUse"),
    ])
    def test_real_registry_delivery_gate_incomplete_result_blocks(
        self, monkeypatch, capsys, isolated_trace, name, module, gate, event
    ):
        """An enforced delivery gate must reach its owner at each supported event."""
        from fettle import dispatcher_registry

        def import_check(imported):
            result = (
                CheckResult.unknown("delivery evidence unavailable", action="retry")
                if imported == module
                else CheckResult.allow()
            )
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": {gate: {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload(event))
        payload["tool_name"] = "Bash"

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert f"Required check '{name}' did not complete." in output["reason"]

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
