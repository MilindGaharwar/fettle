"""Tests for fettle.brief — orchestrator poll endpoint."""

from unittest.mock import patch

from fettle.brief import compute_brief, render_brief


class TestComputeBrief:
    def test_empty_repo(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        with patch("fettle.session_plan.active_plan", return_value=None), \
             patch("fettle.work_items.load_claims", return_value={}), \
             patch("fettle.topology_apply.load_manifest", return_value=None), \
             patch("fettle.rules_cmd.list_rules", return_value=[]), \
             patch("fettle.session_report.load_reports", return_value=[]), \
             patch("fettle.report.compute_effectiveness", return_value={"error": "no data"}):
            result = compute_brief(tmp_path)
        assert isinstance(result, dict)
        assert result["plan"] is None
        assert result["claims"] == {}
        assert result["repo"] == tmp_path.name

    def test_with_active_plan(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        plan = {"title": "my plan", "done": 1, "total": 3, "items": []}
        with patch("fettle.session_plan.active_plan", return_value=plan), \
             patch("fettle.work_items.load_claims", return_value={}), \
             patch("fettle.topology_apply.load_manifest", return_value=None), \
             patch("fettle.rules_cmd.list_rules", return_value=[]), \
             patch("fettle.session_report.load_reports", return_value=[]), \
             patch("fettle.report.compute_effectiveness", return_value={"error": "no data"}):
            result = compute_brief(tmp_path)
        assert result["plan"]["title"] == "my plan"


class TestRenderBrief:
    def test_renders_plan(self):
        data = {
            "repo": "myrepo",
            "plan": {"title": "fix bugs", "done": 2, "total": 4},
            "claims": {},
            "topology": None,
            "ci": None,
            "verify": None,
            "open_proposals": [],
            "top_friction": [],
            "completion_reports": [],
        }
        output = render_brief(data)
        assert "fix bugs" in output
        assert "2/4" in output

    def test_renders_no_plan(self):
        data = {
            "repo": "myrepo",
            "plan": None,
            "claims": {},
            "topology": None,
            "ci": None,
            "verify": None,
            "open_proposals": [],
            "top_friction": [],
            "completion_reports": [],
        }
        output = render_brief(data)
        assert "none active" in output
