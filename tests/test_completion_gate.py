"""Completion evidence hook and release integration tests."""

from __future__ import annotations

import shutil
import subprocess
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


def test_done_work_item_edit_blocks_without_completion_manifest(tmp_path):
    from fettle.completion_gate import run_check

    root = tmp_path / "repo"
    item = root / "docs" / "backlog" / "feature.md"
    item.parent.mkdir(parents=True)
    item.write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n---\n"
        "\n## Resolution\nShipped.\n",
        encoding="utf-8",
    )
    ctx = _ctx(root, event="PostToolUse", target=item)

    result = run_check(ctx)

    assert result.decision == Decision.BLOCK
    assert "feature-x" in result.message


def test_stop_blocks_changed_v2_done_work_item_without_manifest(tmp_path):
    from fettle.completion_gate import run_check

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    item = root / "docs" / "backlog" / "feature.md"
    item.parent.mkdir(parents=True)
    item.write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n---\n"
        "\n## Resolution\nShipped.\n",
        encoding="utf-8",
    )

    result = run_check(_ctx(root))

    assert result.decision == Decision.BLOCK
    assert "feature-x" in result.message


def test_stop_blocks_committed_v2_done_work_item_without_manifest(tmp_path):
    from fettle.completion_gate import run_check

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@fettle.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    item = root / "docs" / "backlog" / "feature.md"
    item.parent.mkdir(parents=True)
    item.write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n---\n"
        "\n## Resolution\nShipped.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "done without evidence"], cwd=root, check=True)

    result = run_check(_ctx(root))

    assert result.decision == Decision.BLOCK
    assert "feature-x" in result.message


def test_post_edit_blocks_malformed_marked_work_item(tmp_path):
    from fettle.completion_gate import run_check

    root = tmp_path / "repo"
    item = root / "docs" / "backlog" / "feature.md"
    item.parent.mkdir(parents=True)
    item.write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n",
        encoding="utf-8",
    )

    result = run_check(_ctx(root, event="PostToolUse", target=item))

    assert result.decision == Decision.BLOCK
    assert "malformed work item" in result.message


def test_stop_blocks_new_v1_work_item_but_allows_tracked_legacy_v1(tmp_path):
    from fettle.completion_gate import run_check

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@fettle.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    item_dir = root / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    legacy = item_dir / "legacy.md"
    legacy.write_text(
        "---\nfettle-work-item: v1\nid: legacy-x\nstatus: done\n---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "legacy item"], cwd=root, check=True)
    assert run_check(_ctx(root)).decision == Decision.ALLOW
    (item_dir / "new.md").write_text(
        "---\nfettle-work-item: v1\nid: new-x\nstatus: open\n---\n",
        encoding="utf-8",
    )

    result = run_check(_ctx(root))

    assert result.decision == Decision.BLOCK
    assert "new-x" in result.message
    assert "fettle-work-item: v2" in result.message


def test_post_edit_allows_tracked_legacy_v1_work_item(tmp_path):
    from fettle.completion_gate import run_check

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@fettle.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    item = root / "docs" / "backlog" / "legacy.md"
    item.parent.mkdir(parents=True)
    item.write_text(
        "---\nfettle-work-item: v1\nid: legacy-x\nstatus: open\n---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "legacy item"], cwd=root, check=True)
    item.write_text(
        "---\nfettle-work-item: v1\nid: legacy-x\nstatus: claimed\n---\n",
        encoding="utf-8",
    )

    result = run_check(_ctx(root, event="PostToolUse", target=item))

    assert result.decision == Decision.ALLOW


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
