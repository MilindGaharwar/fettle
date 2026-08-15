"""Completion evidence hook and release integration tests."""

from __future__ import annotations

import shutil
from pathlib import Path

from fettle.dispatcher_types import Decision, HookContext, HookInput


FIXTURES = Path(__file__).parent / "fixtures" / "completion"


def _ctx(
    root: Path, event: str = "Stop", command: str = "", target: Path | None = None,
) -> HookContext:
    tool = "Bash" if command else "Edit" if target else None
    tool_input = {"command": command} if command else {"file_path": str(target)} if target else {}
    return HookContext(
        input=HookInput(event, tool, tool_input, root, "test", {}),
        config={"gates": {"completion": {"enabled": True, "mode": "enforce"}}},
        plugin_root=root,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )


def _fixture(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    shutil.copytree(FIXTURES / name, root)
    return root


def test_stop_blocks_invalid_complete_claim(tmp_path):
    from fettle.completion_gate import run_check

    result = run_check(_ctx(_fixture(tmp_path, "p63-regression")))

    assert result.decision == Decision.BLOCK
    assert "P63" in result.message


def test_stop_allows_honest_in_progress_manifest(tmp_path):
    from fettle.completion_gate import run_check

    assert run_check(_ctx(_fixture(tmp_path, "timeout"))).decision == Decision.ALLOW


def test_changed_completion_manifest_blocks_immediately(tmp_path):
    from fettle.completion_gate import run_check

    root = _fixture(tmp_path, "p63-regression")
    ctx = _ctx(root, event="PostToolUse", target=root / "docs/completion/P63.json")

    assert run_check(ctx).decision == Decision.BLOCK


def test_unrelated_json_edit_skips_completion_validation(tmp_path):
    from fettle.completion_gate import run_check

    root = _fixture(tmp_path, "p63-regression")
    ctx = _ctx(root, event="PostToolUse", target=root / "package.json")

    assert run_check(ctx).decision == Decision.ALLOW


def test_release_blocks_invalid_complete_claim(tmp_path):
    from fettle.release_gate import run_check

    root = _fixture(tmp_path, "p63-regression")
    (root / "CHANGELOG.md").write_text("## v1.2.3\n")
    ctx = _ctx(root, event="PreToolUse", command="git tag v1.2.3")
    ctx.config["gates"]["release"] = {
        "enabled": True,
        "mode": "enforce",
        "changelog_path": "CHANGELOG.md",
        "check_breaking_changes": False,
    }

    result = run_check(ctx)

    assert result.decision == Decision.BLOCK
    assert "completion" in result.message.lower()
