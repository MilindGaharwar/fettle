"""TR-1 contracts for the shipped hook path."""

from __future__ import annotations

import json
from pathlib import Path

from fettle import bridge
from fettle.dispatcher_registry import CHECKS
from fettle.lsp_server import main as lsp_main
from fettle.paths import find_project_root


ROOT = Path(__file__).parents[1]


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
