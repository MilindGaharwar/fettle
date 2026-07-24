"""WP-T — Black Duck / Polaris SCA Adapter.

Invokes CLI tool, parses SARIF output, reports CVEs and license violations.
Token via env var. Subprocess timeout enforced. Output capped.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from integration_base import IntegrationFinding, IntegrationReport, IntegrationStatus


_SEVERITY_MAP = {
    "error": "CRITICAL",
    "warning": "HIGH",
    "note": "MEDIUM",
    "none": "LOW",
}


class BlackDuckAdapter:
    name = "blackduck"

    def is_available(self, config: dict) -> IntegrationStatus:
        cfg = config.get("integrations", {}).get("blackduck", {})
        if not cfg.get("enabled", False):
            return IntegrationStatus.NOT_ENABLED
        cli_path = cfg.get("cli_path", "polaris")
        if not shutil.which(cli_path) and not os.path.isfile(cli_path):
            return IntegrationStatus.UNAVAILABLE
        token_env = cfg.get("token_env", "POLARIS_TOKEN")
        if not os.environ.get(token_env):
            return IntegrationStatus.MISCONFIGURED
        return IntegrationStatus.PASS

    def run(self, cwd: str, config: dict) -> IntegrationReport:
        cfg = config.get("integrations", {}).get("blackduck", {})
        availability = self.is_available(config)
        if availability != IntegrationStatus.PASS:
            return IntegrationReport(status=availability, summary=availability.value)

        cli_path = cfg.get("cli_path", "polaris")
        timeout_s = int(cfg.get("scan_timeout_s", 300))
        token_env = cfg.get("token_env", "POLARIS_TOKEN")

        env = {**os.environ, token_env: os.environ.get(token_env, "")}

        try:
            result = subprocess.run(
                [cli_path, "analyze", "--output-format", "sarif"],
                capture_output=True, text=True, timeout=timeout_s,
                cwd=cwd, env=env, shell=False,
            )
        except subprocess.TimeoutExpired:
            return IntegrationReport(
                status=IntegrationStatus.UNAVAILABLE,
                summary="Scan timed out after " + str(timeout_s) + "s",
            )
        except (FileNotFoundError, OSError) as e:
            return IntegrationReport(
                status=IntegrationStatus.UNAVAILABLE,
                summary="CLI error: " + str(e)[:200],
            )

        stdout = result.stdout[:1048576]
        return self._parse_sarif(stdout)

    def _parse_sarif(self, output: str) -> IntegrationReport:
        if not output.strip():
            return IntegrationReport(status=IntegrationStatus.PASS, summary="No findings")

        try:
            data = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return IntegrationReport(
                status=IntegrationStatus.UNAVAILABLE,
                summary="Failed to parse SARIF output",
            )

        findings: list[IntegrationFinding] = []
        for run in data.get("runs", []):
            for result in run.get("results", []):
                level = result.get("level", "warning")
                message = result.get("message", {}).get("text", "")
                rule_id = result.get("ruleId", "")
                locations = result.get("locations", [])
                file_path = ""
                line = 0
                if locations:
                    phys = locations[0].get("physicalLocation", {})
                    file_path = phys.get("artifactLocation", {}).get("uri", "")
                    line = phys.get("region", {}).get("startLine", 0)

                findings.append(IntegrationFinding(
                    severity=_SEVERITY_MAP.get(level, "MEDIUM"),
                    message=message[:200],
                    file=file_path,
                    line=line,
                    code=rule_id,
                ))

        has_critical = any(f.severity == "CRITICAL" for f in findings)
        status = IntegrationStatus.FAIL if has_critical else IntegrationStatus.PASS
        return IntegrationReport(
            status=status,
            findings=findings[:50],
            summary=str(len(findings)) + " finding(s)",
        )


def run_command(config: dict, cwd: str) -> IntegrationReport:
    adapter = BlackDuckAdapter()
    return adapter.run(cwd, config)


def main():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import load_config
    from integration_base import format_integration_report

    cfg = load_config(cwd=".")
    report = run_command(cfg, ".")
    print(format_integration_report(report, "Black Duck / Polaris"))
    return 0 if report.status == IntegrationStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
