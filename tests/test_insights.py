"""Tests for fettle/insights.py — read-only digest (WP-163, C4)."""

import json

import pytest

from fettle.evolution import MIN_OCCURRENCES
from fettle.insights import compute_insights, render_insights
from fettle.trace import log_decision


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("FETTLE_PARENT_SESSION", raising=False)
    monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    return root


class TestEmpty:
    def test_all_sources_empty(self, env):
        data = compute_insights(env, days=7)
        assert data["friction"]["total_decisions"] == 0
        assert data["signatures"] == []
        assert data["rule_pipeline"]["pending_proposals"] == 0
        assert data["lineage_anomalies"] == []
        out = render_insights(data)
        assert "no trace activity" in out
        assert "Lineage anomalies: 0" in out

    def test_json_serializable(self, env):
        json.dumps(compute_insights(env, days=7))


class TestPopulated:
    def test_sections_composed(self, env, monkeypatch):
        # friction + a signature
        for _ in range(MIN_OCCURRENCES):
            log_decision(hook="post_edit", status="violation", tool="Edit",
                         session_id="sess-1",
                         findings=[{"code": "ins-test-code", "message": "boom"}])
        # a pending proposal
        proposed = env / "rules" / "proposed"
        proposed.mkdir(parents=True)
        (proposed / "ins-other-rule.yml").write_text(
            "rules:\n  - id: ins-other-rule\n    pattern: ''\n")
        # an ungoverned session (enforce mode + edits + no capsule)
        monkeypatch.setattr(
            "fettle.lineage_report._agent_spawn_enforced", lambda: True)
        log_decision(hook="dispatcher", status="pass", tool="Edit",
                     session_id="sess-2")

        data = compute_insights(env, days=7)
        assert data["friction"]["total_decisions"] >= MIN_OCCURRENCES
        assert any(s["key"] == "post_edit/ins-test-code" for s in data["signatures"])
        assert data["rule_pipeline"]["pending_proposals"] == 1
        assert any(a["session_id"] == "sess-2" for a in data["lineage_anomalies"])

        out = render_insights(data)
        assert "post_edit/ins-test-code" in out
        assert "draftable" in out
        assert "1 pending proposal" in out
        assert "ungoverned session sess-2" in out

    def test_read_only(self, env):
        """The digest must not create files anywhere in the repo (D-C5)."""
        before = sorted(p for p in env.rglob("*"))
        compute_insights(env, days=7)
        assert sorted(p for p in env.rglob("*")) == before
