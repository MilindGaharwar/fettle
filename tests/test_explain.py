"""Tests for fettle.explain — human-readable trace explanation."""

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
