"""Tests for fettle.sarif — SARIF output format."""

from fettle.sarif import findings_to_sarif


class TestFindingsToSarif:
    def test_empty_findings(self):
        result = findings_to_sarif([])
        assert result["$schema"]
        assert result["version"] == "2.1.0"
        assert len(result["runs"]) == 1
        assert result["runs"][0]["results"] == []

    def test_single_finding(self):
        findings = [{"file": "app.py", "line": 5, "code": "E001",
                     "severity": "error", "message": "syntax error", "tool": "ruff"}]
        result = findings_to_sarif(findings)
        results = result["runs"][0]["results"]
        assert len(results) == 1
        assert results[0]["ruleId"] == "E001"
        assert results[0]["message"]["text"] == "syntax error"

    def test_multiple_findings(self):
        findings = [
            {"file": "a.py", "line": 1, "code": "E1", "severity": "error", "message": "m1"},
            {"file": "b.py", "line": 2, "code": "W1", "severity": "warning", "message": "m2"},
        ]
        result = findings_to_sarif(findings)
        assert len(result["runs"][0]["results"]) == 2

    def test_severity_mapping(self):
        findings = [
            {"file": "x.py", "line": 1, "code": "E", "severity": "error", "message": "e"},
            {"file": "x.py", "line": 2, "code": "W", "severity": "warning", "message": "w"},
            {"file": "x.py", "line": 3, "code": "I", "severity": "info", "message": "i"},
        ]
        result = findings_to_sarif(findings)
        levels = [r["level"] for r in result["runs"][0]["results"]]
        assert "error" in levels
        assert "warning" in levels
