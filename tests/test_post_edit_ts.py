"""Tests for fettle.post_edit_ts — TS/JS semgrep antipattern checks."""

from unittest.mock import patch

from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.post_edit_ts import TS_EXTENSIONS, run_check


def _ctx(tmp_path, file_path="", config=None):
    inp = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Write",
        tool_input={"file_path": file_path},
        cwd=tmp_path,
        session_id="test",
        raw={},
    )
    return HookContext(
        input=inp,
        config=config or {"gates": {"lint": {"enabled": True, "mode": "advisory"}}},
        plugin_root=tmp_path,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )


class TestRunCheckFiltering:
    def test_non_ts_file_allows(self, tmp_path):
        ctx = _ctx(tmp_path, file_path=str(tmp_path / "x.py"))
        assert run_check(ctx).decision == Decision.ALLOW

    def test_missing_file_allows(self, tmp_path):
        ctx = _ctx(tmp_path, file_path=str(tmp_path / "gone.tsx"))
        assert run_check(ctx).decision == Decision.ALLOW

    def test_lint_disabled_allows(self, tmp_path):
        ts = tmp_path / "app.ts"
        ts.write_text("const x = 1;")
        ctx = _ctx(tmp_path, file_path=str(ts),
                   config={"gates": {"lint": {"enabled": False, "mode": "advisory"}}})
        assert run_check(ctx).decision == Decision.ALLOW

    def test_no_semgrep_allows(self, tmp_path):
        ts = tmp_path / "app.tsx"
        ts.write_text("export default function App() {}")
        with patch("fettle.post_edit_ts._resolve_tool", return_value=None):
            ctx = _ctx(tmp_path, file_path=str(ts))
            assert run_check(ctx).decision == Decision.ALLOW

    def test_no_rules_file_allows(self, tmp_path):
        ts = tmp_path / "app.ts"
        ts.write_text("const x = 1;")
        with patch("fettle.post_edit_ts._resolve_tool", return_value="/usr/bin/semgrep"):
            ctx = _ctx(tmp_path, file_path=str(ts))
            assert run_check(ctx).decision == Decision.ALLOW


class TestTsExtensions:
    def test_all_frontend_extensions_covered(self):
        assert ".ts" in TS_EXTENSIONS
        assert ".tsx" in TS_EXTENSIONS
        assert ".js" in TS_EXTENSIONS
        assert ".jsx" in TS_EXTENSIONS
        assert ".py" not in TS_EXTENSIONS
