"""Tests for fettle.explain — human-readable trace explanation."""

import json

from fettle.explain import explain_entry


class TestExplainEntry:
    def test_pass_entry(self):
        entry = {"hook": "PostToolUse", "status": "pass", "tool": "ruff",
                 "file": "app.py", "timestamp": "2026-01-01T00:00:00",
                 "findings": [], "duration_ms": 45.2}
        output = explain_entry(entry)
        assert "PostToolUse" in output
        assert "pass" in output
        assert "ruff" in output
        assert "app.py" in output
        assert "No issues found" in output
        assert "45ms" in output

    def test_violation_entry(self):
        entry = {"hook": "PostToolUse", "status": "violation", "tool": "semgrep",
                 "file": "x.py", "timestamp": "2026-01-01T00:00:00",
                 "findings": [{"code": "E001", "message": "bad", "file": "x.py", "line": 10}]}
        output = explain_entry(entry)
        assert "violation" in output
        assert "E001" in output
        assert "bad" in output
        assert "noqa" in output or "nosemgrep" in output

    def test_tool_error_entry(self):
        entry = {"hook": "PostToolUse", "status": "tool_error", "tool": "ruff",
                 "file": "", "timestamp": "2026-01-01T00:00:00", "findings": []}
        output = explain_entry(entry)
        assert "Tool error" in output
        assert "fettle doctor" in output

    def test_config_error_entry(self):
        entry = {"hook": "dispatcher", "status": "config_error",
                 "timestamp": "2026-01-01T00:00:00", "findings": []}
        output = explain_entry(entry)
        assert "Configuration error" in output

    def test_many_findings_truncated(self):
        findings = [{"code": f"E{i:03d}", "message": f"issue {i}",
                     "file": "x.py", "line": i} for i in range(10)]
        entry = {"hook": "PostToolUse", "status": "violation", "tool": "ruff",
                 "file": "x.py", "timestamp": "2026-01-01T00:00:00",
                 "findings": findings}
        output = explain_entry(entry)
        assert "and 5 more" in output

    def test_detailed_entry_shows_action_rerun_and_evidence(self):
        entry = {
            "hook": "PostToolUse", "status": "violation", "timestamp": "now",
            "findings": [{"code": "E001", "message": "bad", "file": "x.py",
                          "line": 4, "impact": "request can fail",
                          "action": "handle the error", "rerun_command": "ruff check x.py",
                          "evidence_id": "ev-123"}],
            "evidence": [{"evidence_id": "ev-123", "kind": "command",
                          "exit_code": 1, "duration_ms": 12}],
        }
        output = explain_entry(entry, detailed=True)
        assert "request can fail" in output
        assert "handle the error" in output
        assert "ruff check x.py" in output
        assert "ev-123" in output

    def test_json_entry_is_stable_machine_output(self):
        entry = {"hook": "verify", "status": "unknown", "findings": [],
                 "evidence": [{"evidence_id": "ev-1", "kind": "command"}]}
        assert json.loads(explain_entry(entry, json_output=True)) == entry
