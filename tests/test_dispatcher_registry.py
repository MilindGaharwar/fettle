"""Tests for fettle.dispatcher_registry — check selection logic."""

import subprocess
import sys

from fettle.dispatcher_registry import CHECKS, select_checks
from fettle.dispatcher_types import CheckResult, Decision, HookContext, HookInput


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
            "'fettle.mcp_trust_gate', 'fettle.lean_sniffers', 'fettle.post_edit')]\n"
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
