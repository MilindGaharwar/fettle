"""Contracts for the adapter-backed PostToolUse dispatcher check."""

from pathlib import Path
from unittest.mock import patch

from fettle.adapters import CheckRun
from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.finding import CheckFinding, EvidenceReference, FindingSeverity, ResultState
from fettle.adapter_check import run_check


def _ctx(tmp_path: Path, file_path: Path, *, mode: str = "advisory") -> HookContext:
    return HookContext(
        input=HookInput(
            hook_event_name="PostToolUse", tool_name="Edit",
            tool_input={"file_path": str(file_path)}, cwd=tmp_path,
            session_id="adapter-test", raw={},
        ),
        config={"gates": {"lint": {"enabled": True, "mode": mode}}},
        plugin_root=tmp_path,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )


def test_routes_nested_typescript_file_to_its_workspace(tmp_path):
    app = tmp_path / "apps" / "web"
    app.mkdir(parents=True)
    (app / "package.json").write_text('{"name":"web","devDependencies":{"typescript":"1"}}')
    target = app / "src" / "app.ts"
    target.parent.mkdir()
    target.write_text("const x = 1")
    clean = CheckRun(ResultState.PASS, scope="changed")

    with patch("fettle.adapter_check.run_adapter_check", return_value=clean) as invoke:
        result = run_check(_ctx(tmp_path, target))

    assert result.decision == Decision.ALLOW
    workspace = invoke.call_args.args[2]
    assert workspace.path == "apps/web"
    assert invoke.call_args.args[3] == [str(target)]


def test_violation_preserves_structured_transport_and_mode(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"web","devDependencies":{"typescript":"1"}}')
    target = tmp_path / "app.ts"
    target.write_text("const x = 1")
    finding = CheckFinding(
        checker="eslint", severity=FindingSeverity.ERROR, file="app.ts", line=1,
        code="no-unused-vars", message="unused", action="remove x",
        rerun_command="npm exec -- eslint app.ts",
    )
    run = CheckRun(
        ResultState.VIOLATION, [finding],
        [EvidenceReference("ev-eslint", "command")], "changed",
    )

    with patch("fettle.adapter_check.run_adapter_check", return_value=run):
        result = run_check(_ctx(tmp_path, target, mode="enforce"))

    assert result.decision == Decision.BLOCK
    assert result.findings == [finding]
    assert result.evidence == run.evidence
    assert "no-unused-vars" in (result.message or "")


def test_tool_error_is_actionable_not_clean(tmp_path):
    (tmp_path / "go.mod").write_text("module example.test/app\n")
    target = tmp_path / "app.go"
    target.write_text("package app")
    run = CheckRun(
        ResultState.TOOL_ERROR,
        evidence=[EvidenceReference("ev-go", "command")],
        scope="changed", tool_error="go not found",
    )

    with patch("fettle.adapter_check.run_adapter_check", return_value=run):
        result = run_check(_ctx(tmp_path, target))

    assert result.result_state == ResultState.TOOL_ERROR
    assert result.decision == Decision.ADVISORY
    assert "go not found" in (result.message or "")


def test_unsupported_file_is_neutral(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("docs")
    assert run_check(_ctx(tmp_path, target)).decision == Decision.ALLOW
