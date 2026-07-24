"""WP-S, T, U — Integration Adapter tests."""

import json
from unittest.mock import patch

from integration_base import IntegrationStatus, IntegrationReport, format_integration_report
from sonar_adapter import SonarQubeAdapter
from blackduck_adapter import BlackDuckAdapter
from pact_adapter import PactAdapter


class TestIntegrationBase:
    def test_format_report_pass(self):
        report = IntegrationReport(status=IntegrationStatus.PASS, summary="All good")
        output = format_integration_report(report, "TestTool")
        assert "PASS" in output
        assert "TestTool" in output

    def test_format_report_with_findings(self):
        from integration_base import IntegrationFinding
        report = IntegrationReport(
            status=IntegrationStatus.FAIL,
            findings=[IntegrationFinding(severity="HIGH", message="vuln found", file="app.py", line=5)],
            summary="1 issue",
        )
        output = format_integration_report(report, "Scanner")
        assert "FAIL" in output
        assert "vuln found" in output


class TestSonarQube:
    def test_not_enabled(self):
        adapter = SonarQubeAdapter()
        assert adapter.is_available({"integrations": {}}) == IntegrationStatus.NOT_ENABLED

    def test_misconfigured_no_endpoint(self):
        adapter = SonarQubeAdapter()
        cfg = {"integrations": {"sonarqube": {"enabled": True, "project_key": "x"}}}
        assert adapter.is_available(cfg) == IntegrationStatus.MISCONFIGURED

    def test_misconfigured_no_token(self):
        adapter = SonarQubeAdapter()
        cfg = {"integrations": {"sonarqube": {"enabled": True, "endpoint": "https://sq", "project_key": "x", "token_env": "MISSING_VAR"}}}
        with patch.dict("os.environ", {}, clear=False):
            assert adapter.is_available(cfg) == IntegrationStatus.MISCONFIGURED

    def test_run_unavailable(self):
        adapter = SonarQubeAdapter()
        cfg = {"integrations": {"sonarqube": {"enabled": True, "endpoint": "https://sq.example.com", "project_key": "proj", "token_env": "SQ_TOK"}}}
        with patch.dict("os.environ", {"SQ_TOK": "fake"}):
            report = adapter.run(".", cfg)
        assert report.status == IntegrationStatus.UNAVAILABLE

    def test_http_rejected(self):
        adapter = SonarQubeAdapter()
        cfg = {"integrations": {"sonarqube": {"enabled": True, "endpoint": "http://insecure", "project_key": "p", "token_env": "T"}}}
        with patch.dict("os.environ", {"T": "tok"}):
            report = adapter.run(".", cfg)
        assert report.status == IntegrationStatus.MISCONFIGURED
        assert "HTTPS" in report.summary


class TestBlackDuck:
    def test_not_enabled(self):
        adapter = BlackDuckAdapter()
        assert adapter.is_available({"integrations": {}}) == IntegrationStatus.NOT_ENABLED

    def test_cli_not_found(self):
        adapter = BlackDuckAdapter()
        cfg = {"integrations": {"blackduck": {"enabled": True, "cli_path": "nonexistent_binary", "token_env": "BD_TOK"}}}
        with patch.dict("os.environ", {"BD_TOK": "x"}):
            assert adapter.is_available(cfg) == IntegrationStatus.UNAVAILABLE

    def test_parse_sarif_empty(self):
        adapter = BlackDuckAdapter()
        report = adapter._parse_sarif("")
        assert report.status == IntegrationStatus.PASS

    def test_parse_sarif_with_findings(self):
        adapter = BlackDuckAdapter()
        sarif = json.dumps({
            "runs": [{"results": [
                {"level": "error", "message": {"text": "CVE-2024-1234"}, "ruleId": "CVE-2024-1234",
                 "locations": [{"physicalLocation": {"artifactLocation": {"uri": "package.json"}, "region": {"startLine": 5}}}]},
                {"level": "warning", "message": {"text": "Outdated lib"}, "ruleId": "DEP-001", "locations": []},
            ]}]
        })
        report = adapter._parse_sarif(sarif)
        assert report.status == IntegrationStatus.FAIL
        assert len(report.findings) == 2
        assert report.findings[0].severity == "CRITICAL"

    def test_parse_sarif_malformed(self):
        adapter = BlackDuckAdapter()
        report = adapter._parse_sarif("NOT JSON{{{")
        assert report.status == IntegrationStatus.UNAVAILABLE


class TestPact:
    def test_not_enabled(self):
        adapter = PactAdapter()
        assert adapter.is_available({"integrations": {}}) == IntegrationStatus.NOT_ENABLED

    def test_misconfigured_no_url(self):
        adapter = PactAdapter()
        cfg = {"integrations": {"pact": {"enabled": True, "token_env": "PACT_TOK"}}}
        assert adapter.is_available(cfg) == IntegrationStatus.MISCONFIGURED

    def test_http_rejected(self):
        adapter = PactAdapter()
        cfg = {"integrations": {"pact": {"enabled": True, "broker_url": "http://insecure", "token_env": "PT"}}}
        with patch.dict("os.environ", {"PT": "tok"}):
            report = adapter.run(".", cfg)
        assert report.status == IntegrationStatus.MISCONFIGURED

    def test_broker_unreachable(self):
        adapter = PactAdapter()
        cfg = {"integrations": {"pact": {"enabled": True, "broker_url": "https://pact.example.com", "token_env": "PT"}}}
        with patch.dict("os.environ", {"PT": "tok"}):
            report = adapter.run(".", cfg)
        assert report.status == IntegrationStatus.UNAVAILABLE

    def test_no_contracts_passes(self):
        adapter = PactAdapter()
        cfg = {"integrations": {"pact": {"enabled": True, "broker_url": "https://pact.example.com", "token_env": "PT"}}}
        with (patch.dict("os.environ", {"PT": "tok"}),
              patch.object(adapter, "_get_pacts", return_value=[])):
            report = adapter.run(".", cfg)
        assert report.status == IntegrationStatus.PASS
        assert "No contracts" in report.summary

    def test_failed_contract_reported(self):
        adapter = PactAdapter()
        cfg = {"integrations": {"pact": {"enabled": True, "broker_url": "https://pact.example.com", "token_env": "PT"}}}
        pacts = [
            {"consumer": {"name": "web"}, "provider": {"name": "api"}, "verificationStatus": "success"},
            {"consumer": {"name": "mobile"}, "provider": {"name": "api"}, "verificationStatus": "failed"},
        ]
        with (patch.dict("os.environ", {"PT": "tok"}),
              patch.object(adapter, "_get_pacts", return_value=pacts)):
            report = adapter.run(".", cfg)
        assert report.status == IntegrationStatus.FAIL
        assert len(report.findings) == 1
        assert "mobile" in report.findings[0].message
