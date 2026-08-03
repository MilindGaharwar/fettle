"""WP-S, T, U — Integration Adapter tests."""

import json
from unittest.mock import patch

from fettle.integration_base import IntegrationStatus, IntegrationReport, format_integration_report
from fettle.sonar_adapter import SonarQubeAdapter
from fettle.blackduck_adapter import BlackDuckAdapter
from fettle.pact_adapter import PactAdapter


class TestIntegrationBase:
    def test_format_report_pass(self):
        report = IntegrationReport(status=IntegrationStatus.PASS, summary="All good")
        output = format_integration_report(report, "TestTool")
        assert "PASS" in output
        assert "TestTool" in output

    def test_format_report_with_findings(self):
        from fettle.integration_base import IntegrationFinding
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


class TestCliIntegrations:
    """WP-14b — `fettle integrations` CLI wiring (audit C14)."""

    @staticmethod
    def _args(name=None, as_json=False):
        import argparse
        return argparse.Namespace(name=name, json=as_json)

    @staticmethod
    def _report(status, summary="", findings=None):
        return IntegrationReport(status=status, summary=summary,
                                 findings=findings or [])

    def _run(self, monkeypatch, reports, name=None, as_json=False):
        """Invoke cmd_integrations with each adapter's run_command stubbed."""
        import pytest
        import fettle.blackduck_adapter
        import fettle.pact_adapter
        import fettle.sonar_adapter
        from fettle import cli
        modules = {"sonarqube": fettle.sonar_adapter,
                   "blackduck": fettle.blackduck_adapter,
                   "pact": fettle.pact_adapter}
        for key, module in modules.items():
            report = reports.get(key, self._report(IntegrationStatus.NOT_ENABLED))
            monkeypatch.setattr(module, "run_command",
                                lambda cfg, cwd, _r=report: _r)
        with pytest.raises(SystemExit) as exc:
            cli.cmd_integrations(self._args(name=name, as_json=as_json))
        return exc.value.code

    def test_all_pass_exits_zero(self, monkeypatch, capsys):
        code = self._run(monkeypatch, {
            "sonarqube": self._report(IntegrationStatus.PASS, "clean"),
            "pact": self._report(IntegrationStatus.PASS, "verified"),
        })
        assert code == 0
        out = capsys.readouterr().out
        assert "SonarQube" in out and "Pact" in out
        assert "Black Duck" not in out  # NOT_ENABLED skipped in run-all mode

    def test_failure_exits_one(self, monkeypatch, capsys):
        code = self._run(monkeypatch, {
            "sonarqube": self._report(IntegrationStatus.PASS),
            "pact": self._report(IntegrationStatus.FAIL, "1 contract failed"),
        })
        assert code == 1

    def test_misconfigured_exits_two(self, monkeypatch, capsys):
        code = self._run(monkeypatch, {
            "sonarqube": self._report(IntegrationStatus.MISCONFIGURED, "no token"),
            "pact": self._report(IntegrationStatus.FAIL),
        })
        assert code == 2  # environment error trumps findings

    def test_unavailable_exits_two(self, monkeypatch, capsys):
        code = self._run(monkeypatch, {
            "blackduck": self._report(IntegrationStatus.UNAVAILABLE, "cli missing"),
        })
        assert code == 2

    def test_none_enabled_exits_zero_with_note(self, monkeypatch, capsys):
        code = self._run(monkeypatch, {})
        assert code == 0
        assert "No integrations enabled" in capsys.readouterr().out

    def test_named_adapter_runs_only_that_one(self, monkeypatch, capsys):
        code = self._run(monkeypatch, {
            "sonarqube": self._report(IntegrationStatus.PASS),
            "pact": self._report(IntegrationStatus.FAIL),
        }, name="sonarqube")
        assert code == 0
        assert "Pact" not in capsys.readouterr().out

    def test_named_disabled_adapter_exits_two(self, monkeypatch, capsys):
        code = self._run(monkeypatch, {}, name="blackduck")
        assert code == 2  # explicitly asked for a disabled integration

    def test_json_output_shape(self, monkeypatch, capsys):
        from fettle.integration_base import IntegrationFinding
        code = self._run(monkeypatch, {
            "sonarqube": self._report(
                IntegrationStatus.FAIL, "1 issue",
                findings=[IntegrationFinding(severity="HIGH", message="vuln",
                                             file="app.py", line=5, code="S1")]),
        }, as_json=True)
        assert code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["integrations"][0]["name"] == "sonarqube"
        assert payload["integrations"][0]["status"] == "fail"
        assert payload["integrations"][0]["findings"][0] == {
            "severity": "HIGH", "message": "vuln", "file": "app.py",
            "line": 5, "code": "S1"}

    def test_parser_accepts_integrations_subcommand(self, monkeypatch):
        from fettle import cli
        called = {}
        monkeypatch.setattr(cli, "cmd_integrations",
                            lambda args: called.update(vars(args)))
        monkeypatch.setattr("sys.argv", ["fettle", "integrations", "pact", "--json"])
        cli.main()
        assert called["name"] == "pact" and called["json"] is True

    def test_defaults_declare_integrations_section(self):
        from fettle.config import DEFAULTS
        for name in ("sonarqube", "blackduck", "pact"):
            assert DEFAULTS["integrations"][name]["enabled"] is False
            assert DEFAULTS["integrations"][name]["token_env"]
