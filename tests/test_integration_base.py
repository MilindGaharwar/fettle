"""Tests for fettle.integration_base — shared adapter protocol and formatting."""

from fettle.integration_base import (
    IntegrationFinding,
    IntegrationReport,
    IntegrationStatus,
    format_integration_report,
)


class TestIntegrationStatus:
    def test_values(self):
        assert IntegrationStatus.PASS == "pass"
        assert IntegrationStatus.FAIL == "fail"
        assert IntegrationStatus.UNAVAILABLE == "unavailable"


class TestFormatReport:
    def test_pass_report(self):
        report = IntegrationReport(status=IntegrationStatus.PASS, summary="All clear")
        out = format_integration_report(report, "SonarQube")
        assert "SonarQube" in out
        assert "PASS" in out
        assert "All clear" in out

    def test_findings_included(self):
        findings = [
            IntegrationFinding(severity="high", message="SQL injection", file="app.py", line=10),
            IntegrationFinding(severity="medium", message="Unused import"),
        ]
        report = IntegrationReport(status=IntegrationStatus.FAIL, findings=findings)
        out = format_integration_report(report, "BlackDuck")
        assert "FAIL" in out
        assert "app.py:10" in out
        assert "SQL injection" in out
        assert "Unused import" in out

    def test_tool_version_shown(self):
        report = IntegrationReport(status=IntegrationStatus.PASS, tool_version="9.8.0")
        out = format_integration_report(report, "Tool")
        assert "9.8.0" in out

    def test_empty_findings(self):
        report = IntegrationReport(status=IntegrationStatus.PASS)
        out = format_integration_report(report, "Pact")
        assert "PASS" in out

    def test_report_has_stable_evidence_id(self):
        report = IntegrationReport(status=IntegrationStatus.FAIL, summary="failed")
        assert report.evidence_id.startswith("ev-")
        assert report.evidence[0].evidence_id == report.evidence_id
