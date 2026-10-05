"""Tests for fettle.dispatcher_registry — check selection logic."""

import io
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from fettle import dispatcher as dispatcher_mod
from fettle.dispatcher_registry import CHECKS, select_checks
from fettle.dispatcher_types import CheckResult, Decision, HookContext, HookInput


@pytest.fixture
def isolated_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))


def _payload(event: str = "PostToolUse") -> str:
    return json.dumps({
        "hook_event_name": event,
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/x.py"},
        "cwd": "/tmp",
        "session_id": "s0-test",
    })


def _run_main(monkeypatch, capsys, stdin_text: str) -> tuple[int, dict]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    rc = dispatcher_mod.main()
    out = capsys.readouterr().out.strip().splitlines()[-1]
    return rc, json.loads(out)


class TestRequiredRegistryRouting:
    @pytest.mark.parametrize(("name", "event", "tool", "gates"), [
        ("runtime_secret_guard", "PreToolUse", "Read", {}),
        ("mcp_trust_gate", "PreToolUse", "Bash", {
            "mcp_trust": {"enabled": True, "mode": "enforce"},
        }),
        ("mcp_trust_gate", "PreToolUse", "Write", {
            "mcp_trust": {"enabled": True, "mode": "enforce"},
        }),
        ("mcp_trust_gate", "PreToolUse", "Edit", {
            "mcp_trust": {"enabled": True, "mode": "enforce"},
        }),
        ("destructive_guard", "PreToolUse", "Bash", {
            "destructive": {"enabled": True, "mode": "enforce"},
        }),
    ])
    def test_real_registry_routes_required_gate_to_its_runner(
        self, monkeypatch, capsys, isolated_trace, name, event, tool, gates
    ):
        """Required gate routing must reach its owner through the real registry."""
        from fettle import dispatcher_registry

        marker = f"{name} enforced"

        def import_check(module):
            result = CheckResult.block(marker) if module == f"fettle.{name}" else CheckResult.allow()
            return SimpleNamespace(run_check=lambda _ctx: result)

        monkeypatch.setattr(dispatcher_registry, "import_module", import_check)
        monkeypatch.setattr(dispatcher_mod, "load_config", lambda cwd, **kwargs: {
            "gates": gates,
            "dispatcher": {"global_budget_ms": 1000},
        })
        payload = json.loads(_payload(event))
        payload["tool_name"] = tool

        code, output = _run_main(monkeypatch, capsys, json.dumps(payload))

        assert code == 2
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert marker in output["reason"]


def _ctx(tmp_path, event="PreToolUse", tool="Write", tool_input=None):
    inp = HookInput(
        hook_event_name=event,
        tool_name=tool,
        tool_input=tool_input or {"file_path": str(tmp_path / "x.py")},
        cwd=tmp_path,
        session_id="test",
        raw={},
    )
    return HookContext(
        input=inp,
        config={"gates": {}, "dispatcher": {}},
        plugin_root=tmp_path,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )


class TestCheckRegistry:
    def test_checks_tuple_not_empty(self):
        assert len(CHECKS) > 0

    def test_all_checks_have_names(self):
        for spec in CHECKS:
            assert spec.name, f"check at order {spec.order} has no name"

    def test_no_duplicate_names(self):
        names = [s.name for s in CHECKS]
        assert len(names) == len(set(names))

    def test_select_checks_returns_sorted(self, tmp_path):
        ctx = _ctx(tmp_path, event="PreToolUse", tool="Write")
        selected = select_checks(ctx)
        orders = [s.order for s in selected]
        assert orders == sorted(orders)


class TestSelectChecks:
    def test_pretooluse_read_selects_runtime_secret_guard(self, tmp_path):
        ctx = _ctx(tmp_path, event="PreToolUse", tool="Read")
        names = [spec.name for spec in select_checks(ctx)]
        assert names[0] == "runtime_secret_guard"

    def test_pretooluse_mcp_selects_runtime_secret_guard(self, tmp_path):
        ctx = _ctx(tmp_path, event="PreToolUse", tool="mcp__filesystem__read_file")
        names = [spec.name for spec in select_checks(ctx)]
        assert names[0] == "runtime_secret_guard"

    def test_pretooluse_write_returns_checks(self, tmp_path):
        ctx = _ctx(tmp_path, event="PreToolUse", tool="Write")
        selected = select_checks(ctx)
        assert len(selected) > 0
        names = [s.name for s in selected]
        assert "capsule_guard" in names

    def test_stop_event_returns_stop_checks(self, tmp_path):
        ctx = _ctx(tmp_path, event="Stop", tool=None, tool_input={})
        selected = select_checks(ctx)
        names = [s.name for s in selected]
        assert any("stop" in n or "quality_gate" in n or "session_report" in n
                   for n in names)

    def test_disabled_check_excluded(self, tmp_path):
        inp = HookInput(
            hook_event_name="PreToolUse", tool_name="Write",
            tool_input={"file_path": "x.py"}, cwd=tmp_path,
            session_id="t", raw={},
        )
        ctx = HookContext(
            input=inp,
            config={"gates": {}, "dispatcher": {"disabled_checks": ["capsule_guard"]}},
            plugin_root=tmp_path,
            hook_start_monotonic=0.0,
            global_deadline_monotonic=9999.0,
        )
        selected = select_checks(ctx)
        names = [s.name for s in selected]
        assert "capsule_guard" not in names

    def test_supported_languages_use_one_adapter_check(self, tmp_path):
        for suffix in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"):
            target = tmp_path / f"x{suffix}"
            target.write_text("")
            ctx = _ctx(
                tmp_path, event="PostToolUse", tool="Write",
                tool_input={"file_path": str(target)},
            )
            names = [spec.name for spec in select_checks(ctx)]
            assert "adapter_check" in names
            assert "post_edit_ts" not in names
            assert "post_edit_go" not in names


class TestLazyRegistry:
    # WP-13 (audit M-03): importing the registry must not import gate modules.
    def test_registry_import_pulls_no_gate_modules(self):
        code = (
            "import sys\n"
            "import fettle.dispatcher_registry\n"
            "heavy = [m for m in sys.modules if m in ("
            "'fettle.quality_gate', 'fettle.verify_gate', 'fettle.ci_gate',"
            "'fettle.mcp_trust_gate', 'fettle.runtime_secret_guard', "
            "'fettle.lean_sniffers', 'fettle.post_edit')]\n"
            "assert not heavy, heavy\n"
        )
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr

    def test_lazy_runner_delegates_to_module(self, tmp_path, monkeypatch):
        import fettle.loop_detect as loop_detect
        seen = {}

        def fake_run(ctx):
            seen["ctx"] = ctx
            return CheckResult.advisory("delegated")

        monkeypatch.setattr(loop_detect, "run_check", fake_run)
        spec = next(s for s in CHECKS if s.name == "loop_detect")
        ctx = _ctx(tmp_path, event="PostToolUse", tool="Write")
        result = spec.run(ctx)
        assert result.decision == Decision.ADVISORY
        assert result.message == "delegated"
        assert seen["ctx"] is ctx


def _ctx_with(tmp_path, event, tool, gates, raw=None):
    inp = HookInput(
        hook_event_name=event, tool_name=tool, tool_input={},
        cwd=tmp_path, session_id="t", raw=raw or {},
    )
    return HookContext(
        input=inp, config={"gates": gates}, plugin_root=tmp_path,
        hook_start_monotonic=0.0, global_deadline_monotonic=9999.0,
    )


class TestQualityRequiresExecution:
    """`quality_gate`'s `required_when` predicate (dispatcher_registry.py)."""

    def _spec(self):
        return next(spec for spec in CHECKS if spec.name == "quality_gate")

    @pytest.mark.parametrize("enabled", [True, False])
    def test_stop_event_follows_tests_gate(self, tmp_path, enabled):
        ctx = _ctx_with(tmp_path, "Stop", None, {"tests": {"enabled": enabled}})
        assert self._spec().required_when(ctx) is enabled

    @pytest.mark.parametrize("enabled", [True, False])
    def test_stop_hook_active_follows_tests_gate_regardless_of_tool(self, tmp_path, enabled):
        ctx = _ctx_with(tmp_path, "PreToolUse", "Bash", {"tests": {"enabled": enabled}},
                        raw={"stop_hook_active": False})
        assert self._spec().required_when(ctx) is enabled

    def test_non_pretooluse_event_is_false(self, tmp_path):
        ctx = _ctx_with(tmp_path, "PostToolUse", "Write",
                        {"ux_spec": {"enabled": True}, "plan": {"enabled": True}})
        assert self._spec().required_when(ctx) is False

    def test_pretooluse_wrong_tool_is_false(self, tmp_path):
        ctx = _ctx_with(tmp_path, "PreToolUse", "Bash",
                        {"ux_spec": {"enabled": True}})
        assert self._spec().required_when(ctx) is False

    @pytest.mark.parametrize("tool", ["Write", "Edit"])
    @pytest.mark.parametrize("gate", ["ux_spec", "plan"])
    def test_pretooluse_write_or_edit_follows_ux_spec_or_plan_gate(self, tmp_path, tool, gate):
        ctx = _ctx_with(tmp_path, "PreToolUse", tool, {gate: {"enabled": True}})
        assert self._spec().required_when(ctx) is True

    @pytest.mark.parametrize("mode,expected", [("enforce", True), ("strict", True), ("advisory", False)])
    def test_pretooluse_bootstrap_mode_gates_result(self, tmp_path, mode, expected):
        ctx = _ctx_with(tmp_path, "PreToolUse", "Write",
                        {"ci_bootstrap": {"enabled": True, "mode": mode}})
        assert self._spec().required_when(ctx) is expected

    def test_pretooluse_bootstrap_disabled_is_false_even_in_enforce_mode(self, tmp_path):
        ctx = _ctx_with(tmp_path, "PreToolUse", "Write",
                        {"ci_bootstrap": {"enabled": False, "mode": "enforce"}})
        assert self._spec().required_when(ctx) is False

    def test_pretooluse_no_gates_is_false(self, tmp_path):
        ctx = _ctx_with(tmp_path, "PreToolUse", "Write", {})
        assert self._spec().required_when(ctx) is False


class TestRequiredWhenPredicates:
    """`capsule_guard` and `mcp_trust_gate`'s inline `required_when` lambdas."""

    @pytest.mark.parametrize("value,expected", [("1", True), ("", False), (None, False)])
    def test_capsule_guard_follows_policy_capsule_env(self, tmp_path, monkeypatch, value, expected):
        if value is None:
            monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
        else:
            monkeypatch.setenv("FETTLE_POLICY_CAPSULE", value)
        spec = next(spec for spec in CHECKS if spec.name == "capsule_guard")
        ctx = _ctx_with(tmp_path, "PreToolUse", "Bash", {})
        assert spec.required_when(ctx) is expected

    @pytest.mark.parametrize("enabled,expected", [(True, True), (False, False)])
    def test_mcp_trust_gate_follows_its_own_config_key(self, tmp_path, enabled, expected):
        spec = next(spec for spec in CHECKS if spec.name == "mcp_trust_gate")
        ctx = _ctx_with(tmp_path, "PreToolUse", "Bash", {"mcp_trust": {"enabled": enabled}})
        assert spec.required_when(ctx) is expected

    def test_mcp_trust_gate_missing_config_is_false(self, tmp_path):
        spec = next(spec for spec in CHECKS if spec.name == "mcp_trust_gate")
        ctx = _ctx_with(tmp_path, "PreToolUse", "Bash", {})
        assert spec.required_when(ctx) is False
