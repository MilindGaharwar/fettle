"""WP-U — Pact Contract Testing Adapter.

Calls Pact Broker API for contract verification status.
Token via env var. HTTPS required. Response capped.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

from fettle.integration_base import IntegrationFinding, IntegrationReport, IntegrationStatus


class PactAdapter:
    name = "pact"

    def is_available(self, config: dict) -> IntegrationStatus:
        cfg = config.get("integrations", {}).get("pact", {})
        if not cfg.get("enabled", False):
            return IntegrationStatus.NOT_ENABLED
        if not cfg.get("broker_url"):
            return IntegrationStatus.MISCONFIGURED
        token_env = cfg.get("token_env", "PACT_BROKER_TOKEN")
        if not os.environ.get(token_env):
            return IntegrationStatus.MISCONFIGURED
        return IntegrationStatus.PASS

    def run(self, cwd: str, config: dict) -> IntegrationReport:
        cfg = config.get("integrations", {}).get("pact", {})
        availability = self.is_available(config)
        if availability != IntegrationStatus.PASS:
            return IntegrationReport(status=availability, summary=availability.value)

        broker_url = cfg["broker_url"].rstrip("/")
        token_env = cfg.get("token_env", "PACT_BROKER_TOKEN")
        token = os.environ.get(token_env, "")

        if not broker_url.startswith("https://"):
            allow_insecure = cfg.get("allow_insecure", False)
            if not allow_insecure:
                return IntegrationReport(
                    status=IntegrationStatus.MISCONFIGURED,
                    summary="HTTPS required for Pact broker",
                )

        try:
            pacts = self._get_pacts(broker_url, token)
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as e:
            return IntegrationReport(
                status=IntegrationStatus.UNAVAILABLE,
                summary="Pact broker unreachable: " + str(e)[:200],
            )

        if not pacts:
            return IntegrationReport(
                status=IntegrationStatus.PASS,
                summary="No contracts found",
            )

        findings: list[IntegrationFinding] = []
        failed_count = 0

        for pact in pacts:
            verification = pact.get("verificationStatus", "unknown")
            consumer = pact.get("consumer", {}).get("name", "?")
            provider = pact.get("provider", {}).get("name", "?")

            if verification != "success":
                failed_count += 1
                findings.append(IntegrationFinding(
                    severity="HIGH" if verification == "failed" else "MEDIUM",
                    message=consumer + " → " + provider + ": " + verification,
                    code="contract-" + verification,
                ))

        status = IntegrationStatus.FAIL if failed_count > 0 else IntegrationStatus.PASS
        return IntegrationReport(
            status=status,
            findings=findings[:20],
            summary=str(len(pacts)) + " contracts, " + str(failed_count) + " unverified/failed",
        )

    def _get_pacts(self, broker_url: str, token: str) -> list[dict]:
        url = broker_url + "/pacts/latest"
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Bearer " + token)
        req.add_header("Accept", "application/hal+json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(1048576)
        data = json.loads(body)
        return data.get("pacts", data.get("_embedded", {}).get("pacts", []))


def run_command(config: dict, cwd: str) -> IntegrationReport:
    adapter = PactAdapter()
    return adapter.run(cwd, config)


def main():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
    from fettle.config import load_config
    from fettle.integration_base import format_integration_report

    cfg = load_config(cwd=".")
    report = run_command(cfg, ".")
    print(format_integration_report(report, "Pact Broker"))
    return 0 if report.status == IntegrationStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
