"""Tests for session plans (v1.6 slice A) — plan files, gate acceptance,
worklog scope=session, and Stop reconciliation."""

import time
from pathlib import Path

import pytest

from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.session_plan import (
    active_plan,
    check_item,
    create_plan,
    parse_plan,
    render_status,
)
from fettle.worklog import _today, run_check


# ─── plan files ──────────────────────────────────────────────────────────────


def test_create_and_parse_roundtrip(tmp_path):
    path = create_plan(tmp_path, "Fix the widget", ["write test", "fix bug"],
                       session_id="s-1")
    plan = parse_plan(path)
    assert plan is not None
    assert plan["title"] == "Fix the widget"
    assert plan["session"] == "s-1"
    assert plan["total"] == 2 and plan["done"] == 0
    assert [i["text"] for i in plan["items"]] == ["write test", "fix bug"]


def test_create_requires_items(tmp_path):
    with pytest.raises(ValueError):
        create_plan(tmp_path, "Empty", [])


def test_filename_collision_gets_suffix(tmp_path):
    p1 = create_plan(tmp_path, "Same title", ["a"])
    p2 = create_plan(tmp_path, "Same title", ["b"])
    assert p1 != p2
    assert p2.stem.endswith("-2")


def test_parse_rejects_non_plan_markdown(tmp_path):
    plans = tmp_path / ".fettle" / "plans"
    plans.mkdir(parents=True)
    f = plans / "notes.md"
    f.write_text("# Just notes\n- [ ] looks like an item\n")
    assert parse_plan(f) is None


def test_active_plan_fresh_and_stale(tmp_path):
    path = create_plan(tmp_path, "Fresh", ["step"])
    assert active_plan(tmp_path) is not None
    # age the file beyond the window
    import os
    old = time.time() - 48 * 3600
    os.utime(path, (old, old))
    assert active_plan(tmp_path, max_age_hours=24.0) is None


def test_check_item_ticks_first_match(tmp_path):
    create_plan(tmp_path, "Plan", ["write TEST first", "fix bug", "write test docs"])
    ok, msg = check_item(tmp_path, "write test")
    assert ok and msg == "write TEST first"  # case-insensitive, first match
    plan = active_plan(tmp_path)
    assert plan["done"] == 1
    ok2, _ = check_item(tmp_path, "no such step")
    assert not ok2


def test_render_status(tmp_path):
    create_plan(tmp_path, "Render me", ["a", "b"])
    check_item(tmp_path, "a")
    out = render_status(active_plan(tmp_path))
    assert "1/2 done" in out and "[x] a" in out and "[ ] b" in out
    assert "No active session plan" in render_status(None)


# ─── plan gate acceptance (quality_gate.scan_planning) ───────────────────────


def _plan_cfg(**over):
    cfg = {"enabled": True, "threshold": 3, "plan_dir": "docs",
           "max_age_hours": 1, "session_plans": True, "risk_paths": []}
    cfg.update(over)
    return cfg


def _scan(tmp_path, monkeypatch, cfg):
    from fettle import quality_gate
    edited = [str(tmp_path / f"mod{i}.py") for i in range(3)]
    monkeypatch.setattr(quality_gate, "_load_tracking", lambda: edited)
    monkeypatch.setattr(quality_gate, "_save_tracking", lambda files: None)
    target = tmp_path / "mod0.py"
    target.write_text("x = 1\n")
    return quality_gate.scan_planning(str(target), str(tmp_path), cfg)


def test_scan_planning_triggers_without_any_plan(tmp_path, monkeypatch):
    findings = _scan(tmp_path, monkeypatch, _plan_cfg())
    assert findings and "PLANNING" in findings[0]
    assert "fettle plan start" in findings[0]


def test_scan_planning_accepts_session_plan(tmp_path, monkeypatch):
    create_plan(tmp_path, "Multi-file change", ["do it"])
    assert _scan(tmp_path, monkeypatch, _plan_cfg()) == []


def test_scan_planning_session_plans_opt_out(tmp_path, monkeypatch):
    create_plan(tmp_path, "Multi-file change", ["do it"])
    findings = _scan(tmp_path, monkeypatch, _plan_cfg(session_plans=False))
    assert findings and "PLANNING" in findings[0]


# ─── worklog scope=session + reconciliation ──────────────────────────────────


def _ctx(cwd, scope="daily", session_id="sess-1"):
    config = {"gates": {"worklog": {"enabled": True, "mode": "advisory",
                                    "scope": scope}}}
    hook_input = HookInput(
        hook_event_name="Stop", tool_name=None, tool_input={},
        cwd=Path(cwd), session_id=session_id, raw={},
    )
    return HookContext(
        input=hook_input, config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0, global_deadline_monotonic=999999.0,
    )


def _write_worklog(cwd: Path) -> Path:
    d = cwd / ".fettle" / "worklog"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{_today()}.md"
    f.write_text(f"# Worklog: {_today()}\n\n## Completed\n- Did the thing\n")
    return f


def test_worklog_session_scope_stale_entry_invalid(tmp_path, monkeypatch):
    f = _write_worklog(tmp_path)
    import os
    old = time.time() - 7200
    os.utime(f, (old, old))
    from fettle import trace
    monkeypatch.setattr(trace, "get_recent_decisions",
                        lambda limit=20: [{"session_id": "sess-1", "ts": time.time() - 60}])
    result = run_check(_ctx(tmp_path, scope="session"))
    assert result.decision is not Decision.ALLOW
    assert "not updated during this session" in result.message


def test_worklog_session_scope_fresh_entry_valid(tmp_path, monkeypatch):
    _write_worklog(tmp_path)  # mtime = now
    from fettle import trace
    monkeypatch.setattr(trace, "get_recent_decisions",
                        lambda limit=20: [{"session_id": "sess-1", "ts": time.time() - 60}])
    result = run_check(_ctx(tmp_path, scope="session"))
    assert result.decision is Decision.ALLOW


def test_worklog_session_scope_fails_open_without_trace(tmp_path, monkeypatch):
    f = _write_worklog(tmp_path)
    import os
    old = time.time() - 7200
    os.utime(f, (old, old))
    from fettle import trace
    monkeypatch.setattr(trace, "get_recent_decisions", lambda limit=20: [])
    result = run_check(_ctx(tmp_path, scope="session"))
    assert result.decision is Decision.ALLOW  # no evidence -> daily behavior


def test_worklog_reconciliation_surfaces_unchecked_items(tmp_path):
    _write_worklog(tmp_path)
    create_plan(tmp_path, "Big task", ["step one", "step two"])
    check_item(tmp_path, "step one")
    result = run_check(_ctx(tmp_path))
    assert result.decision is not Decision.ALLOW  # advisory
    assert "1/2 done" in result.message and "step two" in result.message


def test_worklog_reconciliation_silent_when_plan_complete(tmp_path):
    _write_worklog(tmp_path)
    create_plan(tmp_path, "Small task", ["only step"])
    check_item(tmp_path, "only step")
    result = run_check(_ctx(tmp_path))
    assert result.decision is Decision.ALLOW


def test_worklog_missing_message_includes_reconciliation(tmp_path):
    create_plan(tmp_path, "Task", ["a step"])
    result = run_check(_ctx(tmp_path))
    assert result.decision is not Decision.ALLOW
    assert "no worklog" in result.message
    assert "0/1 done" in result.message


# ─── CLI ─────────────────────────────────────────────────────────────────────


def test_cli_plan_start_status_check(tmp_path, monkeypatch, capsys):
    import argparse
    from fettle import cli, paths
    monkeypatch.setattr(paths, "find_repo_root", lambda *a, **k: str(tmp_path))

    ns = argparse.Namespace(plan_action="start", title="CLI plan",
                            item=["first", "second"], json=False)
    with pytest.raises(SystemExit) as e:
        cli.cmd_plan(ns)
    assert e.value.code == 0
    assert "2 steps" in capsys.readouterr().out

    ns = argparse.Namespace(plan_action="check", text="first", json=False)
    with pytest.raises(SystemExit) as e:
        cli.cmd_plan(ns)
    assert e.value.code == 0

    ns = argparse.Namespace(plan_action="status", json=False)
    with pytest.raises(SystemExit) as e:
        cli.cmd_plan(ns)
    assert e.value.code == 0
    assert "1/2 done" in capsys.readouterr().out


def test_cli_plan_start_without_items_exits_2(tmp_path, monkeypatch, capsys):
    import argparse
    from fettle import cli, paths
    monkeypatch.setattr(paths, "find_repo_root", lambda *a, **k: str(tmp_path))
    ns = argparse.Namespace(plan_action="start", title="Empty", item=[], json=False)
    with pytest.raises(SystemExit) as e:
        cli.cmd_plan(ns)
    assert e.value.code == 2
