"""TR-1 contracts for the shipped hook path."""

from __future__ import annotations

import json
from pathlib import Path

from fettle import bridge
from fettle.dispatcher_registry import CHECKS
from fettle.dispatcher_types import HookContext, HookInput
from fettle.finding import ResultState
from fettle.lsp_server import main as lsp_main
from fettle.paths import find_project_root


ROOT = Path(__file__).parents[1]


def _ctx(root: Path, *, event: str = "Stop", tool: str | None = None,
         tool_input: dict | None = None, gates: dict | None = None) -> HookContext:
    return HookContext(
        input=HookInput(
            hook_event_name=event,
            tool_name=tool,
            tool_input=tool_input or {},
            cwd=root,
            session_id="tr1-malformed-reader",
            raw={},
        ),
        config={"gates": gates or {}},
        plugin_root=ROOT,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


def test_find_project_root_prefers_git_over_nested_policy(tmp_path):
    root = tmp_path / "project"
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".fettle.toml").write_text("", encoding="utf-8")
    (root / "a" / ".fettle.toml").write_text("", encoding="utf-8")

    assert find_project_root(nested) == root


def test_shipped_launchers_use_isolated_python_and_fail_loudly():
    command = bridge.dispatcher_command()
    transport = bridge._opencode_transport()
    launcher = (ROOT / "fettle/run.sh").read_text(encoding="utf-8")

    assert " -P -m fettle.dispatcher" in command
    assert '["-P", "-m", "fettle.dispatcher"]' in transport
    assert 'exec "$PYTHON" -P "$SCRIPT_DIR/$TARGET" "$@"' in launcher
    assert "exit 1" in launcher


def test_claude_registration_is_fail_closed_and_routes_all_post_tools():
    hooks = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
    pre = hooks["PreToolUse"][0]

    assert pre["onFailure"] == "block"
    assert hooks["PostToolUse"][0]["matcher"] == "*"


def test_installed_bridge_registration_matches_claude_failure_contract(tmp_path):
    bridge._write_tree(tmp_path / "bridge", tmp_path / "published")
    hooks = json.loads((tmp_path / "bridge/hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]

    assert hooks["PreToolUse"][0]["onFailure"] == "block"
    assert hooks["PostToolUse"][0]["matcher"] == "*"


def test_enforce_capable_checks_declare_policy_owners():
    expected = {
        "worklog": ("worklog",),
        "post_bash_doc_check": ("docs",),
        "boundary_rules": ("boundary",),
        "provenance_gate": ("provenance",),
        "runtime_output_guard": ("runtime_output",),
    }

    assert {spec.name: spec.policy_gates for spec in CHECKS if spec.name in expected} == expected


def test_lsp_main_remains_the_server_entry_point():
    assert lsp_main.__doc__ == "Entry point for the LSP server."


def test_enforcement_readers_preserve_malformed_journal_as_unknown(tmp_path, monkeypatch):
    journal = tmp_path / "edits.jsonl"
    journal.write_text("not-json\n", encoding="utf-8")
    monkeypatch.setenv("FETTLE_EDIT_TRACKING", str(journal))
    (tmp_path / "coverage.json").write_text('{"files": {}}', encoding="utf-8")

    from fettle.coverage_gate import run_check as coverage_check
    from fettle.post_bash_doc_check import run_check as docs_check
    from fettle.quality_gate import run_check as quality_check
    from fettle.stop_quality_gate import run_check as stop_quality_check

    results = (
        coverage_check(_ctx(tmp_path, gates={"coverage": {"enabled": True}})),
        docs_check(_ctx(
            tmp_path,
            event="PostToolUse",
            tool="Bash",
            tool_input={"command": "git push"},
            gates={"docs": {"enabled": True, "mode": "enforce"}},
        )),
        quality_check(_ctx(tmp_path, gates={})),
        stop_quality_check(_ctx(tmp_path)),
    )

    assert all(result.result_state == ResultState.UNKNOWN for result in results)
