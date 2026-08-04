"""Tests for fettle.dispatcher_types — core types for the dispatcher."""

from fettle.dispatcher_types import CheckResult, CheckSpec, Decision, HookContext, HookInput
from fettle.finding import CheckFinding, EvidenceReference, FindingSeverity, ResultState


class TestCheckResult:
    def test_allow(self):
        r = CheckResult.allow()
        assert r.decision == Decision.ALLOW
        assert r.result_state == ResultState.PASS
        assert r.message is None

    def test_advisory(self):
        r = CheckResult.advisory("warning msg")
        assert r.decision == Decision.ADVISORY
        assert r.result_state == ResultState.VIOLATION
        assert r.message == "warning msg"

    def test_block(self):
        r = CheckResult.block("denied", hook_specific_output={"key": "val"})
        assert r.decision == Decision.BLOCK
        assert r.result_state == ResultState.VIOLATION
        assert r.message == "denied"
        assert r.hook_specific_output == {"key": "val"}

    def test_block_no_hso(self):
        r = CheckResult.block("x")
        assert r.hook_specific_output == {}

    def test_tool_error_is_explicit_and_actionable(self):
        r = CheckResult.tool_error(
            "ruff could not execute",
            action="Install ruff and rerun `ruff check .`.",
        )
        assert r.decision == Decision.ADVISORY
        assert r.result_state == ResultState.TOOL_ERROR
        assert r.action == "Install ruff and rerun `ruff check .`."

    def test_unknown_is_never_pass(self):
        r = CheckResult.unknown(
            "analysis timed out",
            action="Run `fettle verify`.",
        )
        assert r.result_state == ResultState.UNKNOWN
        assert r.decision != Decision.ALLOW

    def test_structured_findings_and_evidence_are_carried(self):
        finding = CheckFinding(
            checker="ruff",
            severity=FindingSeverity.ERROR,
            file="app.py",
            line=1,
            message="unused import",
        )
        evidence = EvidenceReference(evidence_id="ev-1", kind="command")
        r = CheckResult.advisory("fix import", findings=[finding], evidence=[evidence])
        assert r.findings == [finding]
        assert r.evidence == [evidence]

    def test_direct_block_construction_cannot_report_pass(self):
        r = CheckResult(decision=Decision.BLOCK, message="denied")
        assert r.result_state == ResultState.VIOLATION


class TestHookContext:
    def _ctx(self, tmp_path, tool_input=None):
        inp = HookInput(
            hook_event_name="PreToolUse",
            tool_name="Write",
            tool_input=tool_input or {"file_path": str(tmp_path / "x.py")},
            cwd=tmp_path,
            session_id="s1",
            raw={},
        )
        return HookContext(
            input=inp, config={}, plugin_root=tmp_path,
            hook_start_monotonic=0.0, global_deadline_monotonic=9999.0,
        )

    def test_event_property(self, tmp_path):
        ctx = self._ctx(tmp_path)
        assert ctx.event == "PreToolUse"

    def test_target_path(self, tmp_path):
        ctx = self._ctx(tmp_path, {"file_path": str(tmp_path / "a.py")})
        assert ctx.target_path == tmp_path / "a.py"

    def test_target_path_relative(self, tmp_path):
        ctx = self._ctx(tmp_path, {"file_path": "src/main.py"})
        assert ctx.target_path == tmp_path / "src/main.py"

    def test_target_path_none(self, tmp_path):
        ctx = self._ctx(tmp_path, {"command": "ls"})
        assert ctx.target_path is None

    def test_target_ext(self, tmp_path):
        ctx = self._ctx(tmp_path, {"file_path": "app.tsx"})
        assert ctx.target_ext == ".tsx"


class TestCheckSpec:
    def test_matches_event(self, tmp_path):
        spec = CheckSpec(name="test", run=lambda c: CheckResult.allow(),
                         events=frozenset({"PreToolUse"}))
        ctx = TestHookContext()._ctx(tmp_path)
        assert spec.matches(ctx) is True

    def test_no_match_wrong_event(self, tmp_path):
        spec = CheckSpec(name="test", run=lambda c: CheckResult.allow(),
                         events=frozenset({"Stop"}))
        ctx = TestHookContext()._ctx(tmp_path)
        assert spec.matches(ctx) is False

    def test_matches_tool_filter(self, tmp_path):
        spec = CheckSpec(name="test", run=lambda c: CheckResult.allow(),
                         events=frozenset({"PreToolUse"}),
                         tools=frozenset({"Write"}))
        ctx = TestHookContext()._ctx(tmp_path)
        assert spec.matches(ctx) is True

    def test_no_match_wrong_tool(self, tmp_path):
        spec = CheckSpec(name="test", run=lambda c: CheckResult.allow(),
                         events=frozenset({"PreToolUse"}),
                         tools=frozenset({"Bash"}))
        ctx = TestHookContext()._ctx(tmp_path)
        assert spec.matches(ctx) is False

    def test_matches_extension_filter(self, tmp_path):
        spec = CheckSpec(name="test", run=lambda c: CheckResult.allow(),
                         events=frozenset({"PreToolUse"}),
                         extensions=frozenset({".py"}))
        ctx = TestHookContext()._ctx(tmp_path, {"file_path": "x.py"})
        assert spec.matches(ctx) is True

    def test_is_enabled_default(self):
        spec = CheckSpec(name="test", run=lambda c: None,
                         events=frozenset({"PreToolUse"}))
        assert spec.is_enabled({}) is True

    def test_is_enabled_disabled_list(self):
        spec = CheckSpec(name="mycheck", run=lambda c: None,
                         events=frozenset({"PreToolUse"}))
        cfg = {"dispatcher": {"disabled_checks": ["mycheck"]}}
        assert spec.is_enabled(cfg) is False

    def test_is_enabled_explicit_override(self):
        spec = CheckSpec(name="mycheck", run=lambda c: None,
                         events=frozenset({"PreToolUse"}),
                         enabled_by_default=False)
        cfg = {"dispatcher": {"checks": {"mycheck": {"enabled": True}}}}
        assert spec.is_enabled(cfg) is True
