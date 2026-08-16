"""Tests for fettle.integration_base — shared adapter protocol and formatting."""

import pytest

from fettle.evidence import EvidenceArtifact, EvidenceReference as CanonicalEvidenceReference
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


@pytest.mark.parametrize(
    ("status", "result_state", "completeness", "applicability"),
    [
        (IntegrationStatus.PASS, "pass", "complete", "applicable"),
        (IntegrationStatus.FAIL, "violation", "complete", "applicable"),
        (IntegrationStatus.UNAVAILABLE, "tool_error", "unknown", "applicable"),
        (IntegrationStatus.MISCONFIGURED, "unknown", "unknown", "unknown"),
        (IntegrationStatus.NOT_ENABLED, "not_applicable", "complete", "not_applicable"),
    ],
)
def test_all_statuses_have_explicit_canonical_evidence(
    status, result_state, completeness, applicability,
):
    report = IntegrationReport(
        status=status,
        provider="example",
        tool_identity="example-cli",
        determinism="deterministic",
    )

    assert report.completeness == completeness
    assert report.applicability == applicability
    assert isinstance(report.canonical_artifact, EvidenceArtifact)
    assert report.canonical_artifact.result_state == result_state
    assert report.canonical_artifact.payload["domain_report"]["status"] == status.value
    assert report.canonical_artifact.payload["domain_report"]["tool_version"] is None
    artifact = report.canonical_artifact.to_dict()
    assert artifact["payload"]["domain_report"]["evidence"] == [
        {"evidence_id": report.evidence_id, "kind": "integration"},
    ]
    assert report.canonical_artifact.payload["provider"] == "example"
    assert report.canonical_artifact.payload["tool_identity"] == "example-cli"
    assert report.canonical_artifact.payload["determinism"] == "deterministic"
    assert isinstance(report.canonical_reference, CanonicalEvidenceReference)
    assert report.canonical_reference.artifact_digest == report.canonical_artifact.artifact_digest
    assert report.canonical_reference.expected == {
        "source_snapshot_digest": report.source_binding,
        "policy_digest": report.policy_binding,
        "scope_digest": report.scope_binding,
        "producer_id": "fettle.integration",
    }


def test_canonical_evidence_normalizes_finding_path(tmp_path):
    source = tmp_path / "src" / "app.py"
    report = IntegrationReport(
        status=IntegrationStatus.FAIL,
        findings=[IntegrationFinding(severity="high", message="issue", file=str(source))],
        path_context=str(tmp_path),
    )

    finding = report.canonical_artifact.payload["domain_report"]["findings"][0]
    assert finding["file"] == "src/app.py"
    assert report.findings[0].file == str(source)


def test_canonical_evidence_handles_empty_finding_and_windows_path():
    report = IntegrationReport(
        status=IntegrationStatus.FAIL,
        findings=[IntegrationFinding(severity="", message="", file=r"C:\repo\app.py")],
    )

    finding = report.canonical_artifact.to_dict()["payload"]["domain_report"]["findings"][0]
    assert finding["severity"] is None
    assert finding["message"] is None
    assert finding["file"] == "app.py"


def test_canonical_evidence_can_be_rolled_back():
    report = IntegrationReport(
        status=IntegrationStatus.PASS,
        canonical_evidence=False,
    )

    assert report.canonical_artifact is None
    assert report.canonical_reference is None
    assert report.evidence_id.startswith("ev-")
    assert report.evidence[0].evidence_id == report.evidence_id


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
