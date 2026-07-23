"""Tests for worklog gate and utilities."""

import os
from pathlib import Path

from dispatcher_types import Decision, HookContext, HookInput
from worklog import _has_valid_entry, _today, create_template, run_check


def _make_ctx(cwd: str, enabled: bool = True, mode: str = "advisory"):
    config = {
        "gates": {"worklog": {"enabled": enabled, "mode": mode}},
    }
    hook_input = HookInput(
        hook_event_name="Stop",
        tool_name=None,
        tool_input={},
        cwd=Path(cwd),
        session_id="test-worklog",
        raw={},
    )
    return HookContext(
        input=hook_input,
        config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


def test_no_worklog_file_invalid(tmp_path):
    valid, reason = _has_valid_entry(tmp_path / "nonexistent.md")
    assert valid is False
    assert "no worklog" in reason


def test_empty_file_invalid(tmp_path):
    f = tmp_path / "today.md"
    f.write_text("")
    valid, reason = _has_valid_entry(f)
    assert valid is False
    assert "too short" in reason


def test_missing_completed_section_invalid(tmp_path):
    f = tmp_path / "today.md"
    f.write_text("# Worklog: 2026-07-23\n\n## Notes\n- did stuff\n- more stuff\n")
    valid, reason = _has_valid_entry(f)
    assert valid is False
    assert "Completed" in reason


def test_valid_entry(tmp_path):
    f = tmp_path / "today.md"
    f.write_text(
        "# Worklog: 2026-07-23\n\n"
        "## Completed\n"
        "- Shipped the worklog feature\n"
        "- Fixed 3 tests\n\n"
        "## Next Actions\n"
        "- Deploy to prod\n"
    )
    valid, reason = _has_valid_entry(f)
    assert valid is True


def test_create_template(tmp_path):
    path = create_template(str(tmp_path))
    assert os.path.isfile(path)
    content = Path(path).read_text()
    assert "## Completed" in content
    assert _today() in content


def test_create_template_idempotent(tmp_path):
    path1 = create_template(str(tmp_path))
    Path(path1).write_text("# Custom content\n## Completed\n- item\n")
    path2 = create_template(str(tmp_path))
    assert path1 == path2
    assert "Custom content" in Path(path2).read_text()


def test_run_check_disabled_allows(tmp_path):
    ctx = _make_ctx(str(tmp_path), enabled=False)
    result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_run_check_no_entry_advisory(tmp_path):
    ctx = _make_ctx(str(tmp_path), enabled=True, mode="advisory")
    result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "worklog" in result.message.lower()


def test_run_check_no_entry_enforce_blocks(tmp_path):
    ctx = _make_ctx(str(tmp_path), enabled=True, mode="enforce")
    result = run_check(ctx)
    assert result.decision == Decision.BLOCK


def test_run_check_valid_entry_allows(tmp_path):
    worklog_dir = tmp_path / ".fettle" / "worklog"
    worklog_dir.mkdir(parents=True)
    (worklog_dir / f"{_today()}.md").write_text(
        f"# Worklog: {_today()}\n\n## Completed\n- Did the thing\n"
    )
    ctx = _make_ctx(str(tmp_path), enabled=True)
    result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_run_check_does_not_create_template(tmp_path):
    """Hook should NOT create files as a side-effect — only the command does."""
    ctx = _make_ctx(str(tmp_path), enabled=True, mode="advisory")
    run_check(ctx)
    template = tmp_path / ".fettle" / "worklog" / f"{_today()}.md"
    assert not template.is_file()


def test_create_template_via_function(tmp_path):
    """create_template() explicitly creates the file (for /fettle:worklog command)."""
    path = create_template(str(tmp_path))
    assert os.path.isfile(path)
    content = Path(path).read_text()
    assert "## Completed" in content
