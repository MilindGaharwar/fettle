"""Tests for fettle report --lineage — delegation forest (WP-158, A6)."""

import pytest

from fettle.lineage_report import compute_lineage, render_lineage_tree
from fettle.trace import log_decision


@pytest.fixture
def trace_env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.delenv("FETTLE_PARENT_SESSION", raising=False)
    monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
    return tmp_path


def _log(monkeypatch, session_id, parent="", capsule="", tool="Edit",
         status="pass", hook="dispatcher"):
    if parent:
        monkeypatch.setenv("FETTLE_PARENT_SESSION", parent)
    else:
        monkeypatch.delenv("FETTLE_PARENT_SESSION", raising=False)
    if capsule:
        monkeypatch.setenv("FETTLE_POLICY_CAPSULE", f"/x/{capsule}.json")
    else:
        monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
    log_decision(hook=hook, status=status, tool=tool, session_id=session_id)


class TestForest:
    def test_three_level_forest(self, trace_env, monkeypatch):
        _log(monkeypatch, "root-a")
        _log(monkeypatch, "child-b", parent="root-a", capsule="b" * 16)
        _log(monkeypatch, "grandchild-c", parent="child-b", capsule="c" * 16)
        data = compute_lineage(days=1)
        assert data["total_sessions"] == 3
        assert data["roots"] == ["root-a"]
        assert data["children"]["root-a"] == ["child-b"]
        assert data["children"]["child-b"] == ["grandchild-c"]
        assert data["sessions"]["child-b"]["capsule_digest"] == "b" * 16

    def test_orphan_parent_becomes_root(self, trace_env, monkeypatch):
        _log(monkeypatch, "child-x", parent="never-traced")
        data = compute_lineage(days=1)
        assert data["roots"] == ["child-x"]

    def test_counts_edits_blocks_advisories(self, trace_env, monkeypatch):
        _log(monkeypatch, "s1", tool="Edit", status="pass")
        _log(monkeypatch, "s1", tool="Bash", status="blocked")
        _log(monkeypatch, "s1", tool="Write", status="violation")
        counts = compute_lineage(days=1)["sessions"]["s1"]["counts"]
        assert counts["edits"] == 2
        assert counts["blocks"] == 1
        assert counts["advisories"] == 1

    def test_no_data_error(self, trace_env):
        assert "error" in compute_lineage(days=1)


class TestUngoverned:
    def test_flagged_when_enforced_and_no_capsule(self, trace_env, monkeypatch):
        _log(monkeypatch, "naked", tool="Edit")
        _log(monkeypatch, "clothed", capsule="d" * 16, tool="Edit")
        monkeypatch.setattr("fettle.lineage_report._agent_spawn_enforced", lambda: True)
        data = compute_lineage(days=1)
        assert data["sessions"]["naked"]["ungoverned"] is True
        assert data["sessions"]["clothed"]["ungoverned"] is False

    def test_not_flagged_when_advisory(self, trace_env, monkeypatch):
        _log(monkeypatch, "naked", tool="Edit")
        monkeypatch.setattr("fettle.lineage_report._agent_spawn_enforced", lambda: False)
        assert compute_lineage(days=1)["sessions"]["naked"]["ungoverned"] is False


class TestRender:
    def test_tree_renders_flag_and_digests(self, trace_env, monkeypatch):
        _log(monkeypatch, "root-a", tool="Edit")
        _log(monkeypatch, "child-b", parent="root-a", capsule="e" * 16)
        monkeypatch.setattr("fettle.lineage_report._agent_spawn_enforced", lambda: True)
        out = render_lineage_tree(compute_lineage(days=1))
        assert "root-a" in out
        assert "└─ child-b" in out
        assert "e" * 16 in out
        assert "UNGOVERNED" in out

    def test_error_rendered(self, trace_env):
        assert "No trace data" in render_lineage_tree(compute_lineage(days=1))
