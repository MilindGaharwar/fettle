"""WP-S — SonarQube Integration Adapter.

Calls SonarQube API for quality gate status and issues.
Token via env var only. HTTPS required by default.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

from integration_base import IntegrationFinding, IntegrationReport, IntegrationStatus


class SonarQubeAdapter:
    name = "sonarqube"

    def is_available(self, config: dict) -> IntegrationStatus:
        cfg = config.get("integrations", {}).get("sonarqube", {})
        if not cfg.get("enabled", False):
            return IntegrationStatus.NOT_ENABLED
        if not cfg.get("endpoint") or not cfg.get("project_key"):
            return IntegrationStatus.MISCONFIGURED
        token_env = cfg.get("token_env", "SONAR_TOKEN")
        if not os.environ.get(token_env):
            return IntegrationStatus.MISCONFIGURED
        return IntegrationStatus.PASS

    def run(self, cwd: str, config: dict) -> IntegrationReport:
        cfg = config.get("integrations", {}).get("sonarqube", {})
        availability = self.is_available(config)
        if availability != IntegrationStatus.PASS:
            return IntegrationReport(status=availability, summary=availability.value)

        endpoint = cfg["endpoint"].rstrip("/")
        project_key = cfg["project_key"]
        token_env = cfg.get("token_env", "SONAR_TOKEN")
        token = os.environ.get(token_env, "")
        allow_insecure = cfg.get("allow_insecure", False)

        if not allow_insecure and not endpoint.startswith("https://"):
            return IntegrationReport(
                status=IntegrationStatus.MISCONFIGURED,
                summary="HTTPS required (set allow_insecure=true to override)",
            )

        try:
            gate_status = self._get_quality_gate(endpoint, project_key, token)
            issues = self._get_issues(endpoint, project_key, token)
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as e:
            return IntegrationReport(
                status=IntegrationStatus.UNAVAILABLE,
                summary="SonarQube unreachable: " + str(e)[:200],
            )

        findings = [
            IntegrationFinding(
                severity=i.get("severity", "MAJOR"),
                message=i.get("message", ""),
                file=i.get("component", "").split(":")[-1],
                line=i.get("line", 0),
                code=i.get("rule", ""),
            )
            for i in issues[:50]
        ]

        status = IntegrationStatus.PASS if gate_status == "OK" else IntegrationStatus.FAIL
        return IntegrationReport(
            status=status,
            findings=findings,
            summary="Quality gate: " + gate_status + " (" + str(len(issues)) + " issues)",
        )

    def _get_quality_gate(self, endpoint: str, project_key: str, token: str) -> str:
        url = endpoint + "/api/qualitygates/project_status?projectKey=" + project_key
        data = self._api_call(url, token)
        return data.get("projectStatus", {}).get("status", "UNKNOWN")

    def _get_issues(self, endpoint: str, project_key: str, token: str) -> list[dict]:
        url = (endpoint + "/api/issues/search?componentKeys=" + project_key
               + "&resolved=false&ps=50")
        data = self._api_call(url, token)
        return data.get("issues", [])

    def _api_call(self, url: str, token: str) -> dict:
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(1048576)
        return json.loads(body)


def run_command(config: dict, cwd: str) -> IntegrationReport:
    adapter = SonarQubeAdapter()
    return adapter.run(cwd, config)


def main():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import load_config
    from integration_base import format_integration_report

    cfg = load_config(cwd=".")
    report = run_command(cfg, ".")
    print(format_integration_report(report, "SonarQube"))
    return 0 if report.status == IntegrationStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
