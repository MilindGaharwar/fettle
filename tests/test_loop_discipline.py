"""WP-C — Discipline link pilot: loop_detect -> discipline-debugging.

Tests that loop_detect injects a discipline reminder when firing,
handles absent disciplines gracefully, and respects cooldown.
"""

import os
from pathlib import Path
from unittest.mock import patch

from dispatcher_types import Decision, HookContext, HookInput


def _make_ctx(config_overrides: dict | None = None, session_id: str = "test-disc"):
    config = {
        "gates": {
            "loop_detect": {"enabled": True, "threshold": 3, "window": 7},
            "discipline_link": {
                "enabled": True,
                "skills_path": "~/.claude/plugins/disciplines/skills",
                "cooldown_seconds": 300,
            },
        },
    }
    if config_overrides:
        for k, v in config_overrides.items():
            if isinstance(v, dict) and isinstance(config["gates"].get(k), dict):
                config["gates"][k].update(v)
            else:
                config["gates"][k] = v

    hook_input = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Edit",
        tool_input={"file_path": "/tmp/test.py", "old_string": "x", "new_string": "y"},
        cwd=Path("/tmp"),
        session_id=session_id,
        raw={},
    )
    return HookContext(
        input=hook_input,
        config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


def _trigger_loop(ctx, tmp_path, count=3):
    """Fire loop_detect enough times to trigger the advisory."""
    from loop_detect import run_check

    state_dir = str(tmp_path / "sessions")
    results = []
    with patch.dict(os.environ, {"FETTLE_LOOP_STATE_DIR": state_dir}):
        for _ in range(count):
            results.append(run_check(ctx))
    return results


def test_discipline_reminder_appended_when_present(tmp_path):
    """With disciplines installed, reminder appears on first threshold trigger."""
    skill_dir = tmp_path / "skills" / "discipline-debugging"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: discipline-debugging\n---\n"
        "# Debugging\n\n"
        "Observe the actual error before hypothesizing. "
        "Form one falsifiable hypothesis and test it with the smallest possible action."
    )

    cfg = {"discipline_link": {
        "enabled": True,
        "skills_path": str(tmp_path / "skills"),
        "cooldown_seconds": 300,
    }}
    ctx = _make_ctx(config_overrides=cfg, session_id="disc-present")

    results = _trigger_loop(ctx, tmp_path, count=3)
    first_trigger = results[-1]
    assert first_trigger.decision == Decision.ADVISORY
    assert "Discipline reminder:" in first_trigger.message
    assert "Observe" in first_trigger.message or "hypothesis" in first_trigger.message


def test_fallback_when_disciplines_absent(tmp_path):
    """Without disciplines plugin, fallback reminder is used."""
    cfg = {"discipline_link": {
        "enabled": True,
        "skills_path": str(tmp_path / "nonexistent"),
        "cooldown_seconds": 300,
    }}
    ctx = _make_ctx(config_overrides=cfg, session_id="disc-absent")

    results = _trigger_loop(ctx, tmp_path, count=3)
    first_trigger = results[-1]
    assert first_trigger.decision == Decision.ADVISORY
    assert "Discipline reminder:" in first_trigger.message
    assert "Pause and inspect" in first_trigger.message


def test_cooldown_suppresses_repeated_reminder(tmp_path):
    """After first trigger, cooldown prevents repeated reminder."""
    skill_dir = tmp_path / "skills" / "discipline-debugging"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: discipline-debugging\n---\n"
        "# Debugging\n\nFirst sentence here. Second sentence here."
    )

    cfg = {"discipline_link": {
        "enabled": True,
        "skills_path": str(tmp_path / "skills"),
        "cooldown_seconds": 300,
    }}
    ctx = _make_ctx(config_overrides=cfg, session_id="disc-cooldown")

    state_dir = str(tmp_path / "sessions")
    from loop_detect import run_check

    with patch.dict(os.environ, {"FETTLE_LOOP_STATE_DIR": state_dir}):
        # Trigger 3 times to hit threshold — first trigger gets reminder
        for _ in range(3):
            r1 = run_check(ctx)
        assert "Discipline reminder:" in r1.message

        # 4th call: same session, within cooldown — no reminder
        r2 = run_check(ctx)
        assert r2.decision == Decision.ADVISORY
        assert "Discipline reminder:" not in r2.message


def test_disabled_discipline_link_no_reminder(tmp_path):
    """When discipline_link is disabled, no reminder is injected."""
    cfg = {"discipline_link": {"enabled": False}}
    ctx = _make_ctx(config_overrides=cfg, session_id="disc-disabled")

    results = _trigger_loop(ctx, tmp_path, count=4)
    last = results[-1]
    assert last.decision == Decision.ADVISORY
    assert "Discipline reminder:" not in last.message
