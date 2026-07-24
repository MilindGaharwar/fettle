"""WP-V — Architecture Boundary Rules Gate tests."""

import textwrap
from pathlib import Path

from fettle.dispatcher_types import Decision, HookContext, HookInput


def _make_ctx(file_path: str, cwd: str, rules: list[dict], enabled: bool = True):
    config = {
        "gates": {
            "architecture_boundaries": {
                "enabled": enabled,
                "rules": rules,
            },
        },
    }
    hook_input = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Edit",
        tool_input={"file_path": file_path},
        cwd=Path(cwd),
        session_id="test-boundary",
        raw={},
    )
    return HookContext(
        input=hook_input,
        config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


def test_disabled_allows(tmp_path):
    from fettle.boundary_rules import run_check
    src = tmp_path / "ui" / "page.py"
    src.parent.mkdir()
    src.write_text("from infrastructure import db\n")
    ctx = _make_ctx(str(src), str(tmp_path), rules=[], enabled=False)
    assert run_check(ctx).decision == Decision.ALLOW


def test_no_rules_allows(tmp_path):
    from fettle.boundary_rules import run_check
    src = tmp_path / "ui" / "page.py"
    src.parent.mkdir()
    src.write_text("from infrastructure import db\n")
    ctx = _make_ctx(str(src), str(tmp_path), rules=[])
    assert run_check(ctx).decision == Decision.ALLOW


def test_allowed_import_passes(tmp_path):
    from fettle.boundary_rules import run_check
    src = tmp_path / "ui" / "page.py"
    src.parent.mkdir()
    src.write_text("from domain import models\n")
    rules = [{"from": "ui/**", "to": "domain/**", "allow": True}]
    ctx = _make_ctx(str(src), str(tmp_path), rules=rules)
    assert run_check(ctx).decision == Decision.ALLOW


def test_denied_import_advisory(tmp_path):
    from fettle.boundary_rules import run_check
    src = tmp_path / "domain" / "service.py"
    src.parent.mkdir()
    src.write_text("from infrastructure import database\n")
    rules = [{"from": "domain/**", "to": "infrastructure/**", "allow": False}]
    ctx = _make_ctx(str(src), str(tmp_path), rules=rules)
    result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "boundary" in result.message.lower() or "violat" in result.message.lower()


def test_non_matching_rule_allows(tmp_path):
    from fettle.boundary_rules import run_check
    src = tmp_path / "utils" / "helpers.py"
    src.parent.mkdir()
    src.write_text("from infrastructure import cache\n")
    rules = [{"from": "domain/**", "to": "infrastructure/**", "allow": False}]
    ctx = _make_ctx(str(src), str(tmp_path), rules=rules)
    assert run_check(ctx).decision == Decision.ALLOW


def test_non_python_file_skipped(tmp_path):
    from fettle.boundary_rules import run_check
    src = tmp_path / "config.toml"
    src.write_text("[database]\nurl = 'postgres://'\n")
    rules = [{"from": "**", "to": "**", "allow": False}]
    ctx = _make_ctx(str(src), str(tmp_path), rules=rules)
    assert run_check(ctx).decision == Decision.ALLOW


def test_multiple_violations_reported(tmp_path):
    from fettle.boundary_rules import run_check
    src = tmp_path / "ui" / "page.py"
    src.parent.mkdir()
    src.write_text(textwrap.dedent("""
        from infrastructure import db
        from infrastructure import cache
        from infrastructure import queue
    """))
    rules = [{"from": "ui/**", "to": "infrastructure/**", "allow": False}]
    ctx = _make_ctx(str(src), str(tmp_path), rules=rules)
    result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "denied" in result.message
