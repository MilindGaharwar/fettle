"""Tests for the completion contract, topology outcome report, and
`fettle brief` (v1.6 slice C)."""

import json
from pathlib import Path

from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.session_report import (
    REPORTS_RELPATH,
    compute_report,
    load_reports,
    run_check,
    write_report,
)


def _ctx(cwd, enabled=True, session_id="sess-c1"):
    config = {"gates": {"session_report": {"enabled": enabled}}}
    hook_input = HookInput(
        hook_event_name="Stop", tool_name=None, tool_input={},
        cwd=Path(cwd), session_id=session_id, raw={},
    )
    return HookContext(
        input=hook_input, config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0, global_deadline_monotonic=999999.0,
    )


# ─── completion report ───────────────────────────────────────────────────────


def test_compute_report_tolerates_empty_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    report = compute_report(str(tmp_path), "s-1")
    assert report["schema"] == 1
    assert report["session_id"] == "s-1"
    assert report["files_edited"] == []
    assert report["claims_held"] == []
    assert report["plan"] is None
    assert report["verify"] is None and report["ci"] is None


def test_report_joins_edits_plan_and_stamps(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    # edits.jsonl with a duplicate
    from fettle.config import state_dir
    edits = state_dir("s-2") / "edits.jsonl"
    edits.write_text(
        json.dumps({"file": str(tmp_path / "a.py")}) + "\n"
        + json.dumps({"file": str(tmp_path / "a.py")}) + "\n"
        + json.dumps({"file": str(tmp_path / "b.py")}) + "\n")
    # plan + stamps
    from fettle.session_plan import check_item, create_plan
    create_plan(tmp_path, "C work", ["one", "two"])
    check_item(tmp_path, "one")
    (tmp_path / ".fettle").mkdir(exist_ok=True)
    (tmp_path / ".fettle" / "verify.json").write_text('{"ok": true}')
    (tmp_path / ".fettle" / "ci-status.json").write_text('{"ok": false, "overall": "failure"}')

    report = compute_report(str(tmp_path), "s-2")
    assert report["files_edited_count"] == 2
    assert report["plan"] == {"title": "C work", "done": 1, "total": 2}
    assert report["verify"]["ok"] is True
    assert report["ci"]["ok"] is False


def test_write_and_load_reports_sanitized(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    path = write_report(str(tmp_path), "weird/../id")
    assert path is not None
    assert path.name == "weirdid.json"  # sanitized
    assert path.parent == tmp_path / REPORTS_RELPATH
    reports = load_reports(str(tmp_path))
    assert len(reports) == 1 and reports[0]["session_id"] == "weird/../id"


def test_run_check_disabled_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    result = run_check(_ctx(tmp_path, enabled=False))
    assert result.decision is Decision.ALLOW
    assert not (tmp_path / REPORTS_RELPATH).exists()


def test_run_check_enabled_writes_report_never_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    result = run_check(_ctx(tmp_path))
    assert result.decision is Decision.ALLOW
    assert (tmp_path / REPORTS_RELPATH / "sess-c1.json").is_file()


# ─── topology outcome report ─────────────────────────────────────────────────


def test_topology_report_without_manifest(tmp_path):
    from fettle.topology_apply import topology_report
    assert "error" in topology_report(str(tmp_path))


def test_topology_report_detects_actual_overlap(tmp_path, monkeypatch):
    from fettle import session_report, topology_apply, work_items

    monkeypatch.setattr(topology_apply, "load_manifest", lambda root: {
        "topology": "parallel-workers", "created_at": "2026-08-02T10:00:00",
        "items": [{"item": "wi-a"}, {"item": "wi-b"}],
    })
    monkeypatch.setattr(topology_apply, "topology_status", lambda root: {
        "topology": "parallel-workers", "workers": [
            {"item": "wi-a", "worktree": "x", "claimed": True, "session_id": "sa",
             "decisions": 10, "blocks": 1, "last_activity": "", "stop_loss_breached": False},
            {"item": "wi-b", "worktree": "y", "claimed": True, "session_id": "sb",
             "decisions": 5, "blocks": 0, "last_activity": "", "stop_loss_breached": False},
        ],
    })
    monkeypatch.setattr(work_items, "discover_work_items", lambda root: [])
    monkeypatch.setattr(session_report, "load_reports", lambda root: [
        {"session_id": "sa", "files_edited": ["src/shared.py", "src/a.py"],
         "verify": {"ok": True}, "ci": None, "plan": {"title": "t", "done": 2, "total": 2}},
        {"session_id": "sb", "files_edited": ["src/shared.py"],
         "verify": None, "ci": None, "plan": None},
    ])

    data = topology_apply.topology_report(str(tmp_path))
    assert data["prediction_held"] is False
    assert data["actual_overlaps"] == [
        {"a": "wi-a", "b": "wi-b", "files": ["src/shared.py"], "count": 1}]
    row_a = next(w for w in data["workers"] if w["item"] == "wi-a")
    assert row_a["predicted_unknown"] is True  # no scope declared
    assert row_a["verify_ok"] is True and row_a["ci_ok"] is False
    assert row_a["plan"] == {"title": "t", "done": 2, "total": 2}

    rendered = topology_apply.render_topology_report(data)
    assert "did NOT hold" in rendered and "wi-a ∩ wi-b" in rendered


def test_topology_report_prediction_held(tmp_path, monkeypatch):
    from fettle import session_report, topology_apply, work_items

    monkeypatch.setattr(topology_apply, "load_manifest", lambda root: {
        "topology": "parallel-workers", "created_at": "t", "items": []})
    monkeypatch.setattr(topology_apply, "topology_status", lambda root: {
        "topology": "parallel-workers", "workers": [
            {"item": "wi-a", "worktree": "x", "claimed": True, "session_id": "sa",
             "decisions": 3, "blocks": 0, "last_activity": "", "stop_loss_breached": False},
        ],
    })
    monkeypatch.setattr(work_items, "discover_work_items", lambda root: [])
    monkeypatch.setattr(session_report, "load_reports", lambda root: [])
    data = topology_apply.topology_report(str(tmp_path))
    assert data["prediction_held"] is True
    assert "(no completion report)" in topology_apply.render_topology_report(data)


# ─── fettle brief ────────────────────────────────────────────────────────────


def test_brief_offline_on_bare_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    from fettle.brief import compute_brief, render_brief
    data = compute_brief(tmp_path)
    assert data["repo"] == tmp_path.name
    assert data["plan"] is None
    assert data["claims"] == {}
    assert data["topology"] is None
    assert data["ci"] is None
    out = render_brief(data)
    assert "no cached verdict" in out and "plan      none active" in out


def test_brief_surfaces_plan_ci_and_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    from fettle.session_plan import create_plan
    create_plan(tmp_path, "Brief plan", ["a"])
    (tmp_path / ".fettle").mkdir(exist_ok=True)
    (tmp_path / ".fettle" / "ci-status.json").write_text(
        '{"ok": true, "sha": "abc123def456", "overall": "success"}')
    write_report(str(tmp_path), "child-1")

    from fettle.brief import compute_brief, render_brief
    data = compute_brief(tmp_path)
    assert data["plan"]["title"] == "Brief plan"
    assert data["ci"] == {"ok": True, "sha": "abc123def456", "overall": "success"}
    assert data["completion_reports"][0]["session_id"] == "child-1"
    out = render_brief(data)
    assert "success @ abc123def456" in out
    assert "completion report(s)" in out
