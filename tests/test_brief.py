"""Tests for fettle.brief — orchestrator poll endpoint."""

import json
import subprocess
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

    def test_stale_verify_stamp_is_not_reported_green(self, tmp_path, monkeypatch):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@fettle.invalid"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
        source = tmp_path / "app.py"
        source.write_text("value = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
        from fettle.config import load_config
        from fettle.verify_gate import _capture_pre_run_state, _write_stamp
        stamp = {
            "ok": True, "exit_code": 0, "result_state": "pass",
            "command": "pytest", "scope": "full", "impacted": [],
        }
        _capture_pre_run_state(str(tmp_path), stamp)
        _write_stamp(str(tmp_path), stamp, load_config(str(tmp_path)))
        source.write_text("value = 2\n")
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        with patch("fettle.session_plan.active_plan", return_value=None), \
             patch("fettle.work_items.load_claims", return_value={}), \
             patch("fettle.topology_apply.load_manifest", return_value=None), \
             patch("fettle.rules_cmd.list_rules", return_value=[]), \
             patch("fettle.session_report.load_reports", return_value=[]), \
             patch("fettle.report.compute_effectiveness", return_value={}):
            result = compute_brief(tmp_path)

        assert result["verify"]["state"] == "stale"
        assert result["verify"]["ok"] is False


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
