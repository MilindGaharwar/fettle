"""Contracts for the adapter-backed PostToolUse dispatcher check."""

from pathlib import Path
import statistics
import time
from unittest.mock import patch

import pytest

from fettle.adapters import CheckRun
from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.finding import CheckFinding, EvidenceReference, FindingSeverity, ResultState
from fettle.adapter_check import run_check


@pytest.fixture(autouse=True)
def _no_semgrep_by_default():
    with (patch("fettle.adapters.typescript_adapter.semgrep_findings", return_value=[]),
          patch("fettle.adapters.go_adapter.semgrep_findings", return_value=[])):
        yield


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


def test_typescript_semgrep_violation_survives_adapter_route(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"web","scripts":{"lint":"eslint ."}}')
    target = tmp_path / "app.ts"
    target.write_text("console.log('debug')")
    finding = CheckFinding(
        checker="semgrep", severity=FindingSeverity.WARNING, file="app.ts", line=1,
        code="debug-print-ts", message="debug print",
    )
    with (patch("fettle.adapters.typescript_adapter.semgrep_findings", return_value=[finding]),
          patch("fettle.adapters.typescript_adapter.ToolRunner.run") as invoke):
        invoke.return_value.returncode = 0
        invoke.return_value.tool_missing = False
        invoke.return_value.timed_out = False
        invoke.return_value.stdout = ""
        invoke.return_value.stderr = ""
        result = run_check(_ctx(tmp_path, target))
    assert result.decision == Decision.ADVISORY
    assert result.findings[0].code == "debug-print-ts"


def test_go_semgrep_error_is_not_clean(tmp_path):
    (tmp_path / "go.mod").write_text("module example.test/app\n")
    target = tmp_path / "app.go"
    target.write_text("package app")
    error = CheckFinding(
        checker="semgrep-adapter", severity=FindingSeverity.INFO, file="", line=0,
        message="semgrep not available: timed out", blocking=False,
    )
    with (patch("fettle.adapters.go_adapter.semgrep_findings", return_value=[error]),
          patch("fettle.adapters.go_adapter.ToolRunner.run") as invoke):
        invoke.return_value.returncode = 0
        invoke.return_value.tool_missing = False
        invoke.return_value.timed_out = False
        invoke.return_value.stdout = ""
        invoke.return_value.stderr = ""
        result = run_check(_ctx(tmp_path, target))
    assert result.result_state == ResultState.TOOL_ERROR
    assert "semgrep" in (result.message or "")


def test_adapter_hook_routing_p95_stays_within_budget(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"web"}')
    target = tmp_path / "app.ts"
    target.write_text("const x = 1")
    clean = CheckRun(ResultState.PASS, scope="changed")
    ctx = _ctx(tmp_path, target)

    with (patch("fettle.adapter_check.detect_profile") as detect,
          patch("fettle.adapter_check.run_adapter_check", return_value=clean)):
        from fettle.workspace import Workspace

        detect.return_value.workspaces = [Workspace(
            name="web", path=".", language="typescript", marker="package.json",
        )]
        durations = []
        for _ in range(100):
            start = time.perf_counter_ns()
            assert run_check(ctx).decision == Decision.ALLOW
            durations.append((time.perf_counter_ns() - start) / 1_000_000)

    p95_ms = statistics.quantiles(durations, n=100, method="inclusive")[94]
    assert p95_ms < 150
