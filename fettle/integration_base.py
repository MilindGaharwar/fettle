"""Shared IntegrationAdapter protocol for external tool integrations.

All vendor adapters implement this interface. Provides 5-state result
model and configurable fail-open/fail-closed behavior.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from fettle import __version__
from fettle.evidence import (
    EvidenceArtifact,
    EvidenceReference as CanonicalEvidenceReference,
)
from fettle.finding import EvidenceReference
from fettle.trace import build_evidence


class IntegrationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"
    MISCONFIGURED = "misconfigured"
    NOT_ENABLED = "not_enabled"


@dataclass
class IntegrationFinding:
    severity: str
    message: str
    file: str = ""
    line: int = 0
    code: str = ""
    url: str = ""


def integration_binding(value: object) -> str:
    """Return a full canonical digest for an integration binding."""
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(
        unicodedata.normalize("NFC", encoded).encode("utf-8")
    ).hexdigest()


def _producer_digest() -> str:
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _artifact_path(path: str, path_context: str) -> str:
    if not path:
        return ""
    if len(path) >= 3 and path[1] == ":" and path[2] in {"/", "\\"}:
        path = path.replace("\\", "/").rsplit("/", 1)[-1]
    candidate = Path(path)
    if candidate.is_absolute() and path_context:
        try:
            path = candidate.resolve().relative_to(Path(path_context).resolve()).as_posix()
        except ValueError:
            path = candidate.name
    elif candidate.is_absolute():
        path = candidate.name
    normalized = posixpath.normpath(path.replace("\\", "/"))
    if normalized == ".." or normalized.startswith("../"):
        return Path(normalized).name
    return "" if normalized == "." else normalized


_RESULT_STATES = {
    IntegrationStatus.PASS: "pass",
    IntegrationStatus.FAIL: "violation",
    IntegrationStatus.UNAVAILABLE: "tool_error",
    IntegrationStatus.MISCONFIGURED: "unknown",
    IntegrationStatus.NOT_ENABLED: "not_applicable",
}


@dataclass
class IntegrationReport:
    status: IntegrationStatus
    findings: list[IntegrationFinding] = field(default_factory=list)
    summary: str = ""
    tool_version: str | None = None
    evidence_id: str = ""
    evidence: list[EvidenceReference] = field(default_factory=list)
    provider: str = "integration"
    tool_identity: str = "integration"
    trust_class: str = "external"
    completeness: str = ""
    determinism: str = "provider-controlled"
    applicability: str = ""
    source_binding: str = ""
    policy_binding: str = ""
    scope_binding: str = ""
    path_context: str = ""
    canonical_evidence: bool = True
    canonical_artifact: EvidenceArtifact | None = field(default=None, init=False)
    canonical_reference: CanonicalEvidenceReference | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not self.evidence_id:
            artifact = build_evidence(
                "integration", exit_code=0 if self.status == IntegrationStatus.PASS else 1,
                tool_version=self.tool_version or "", scope=self.status.value,
            )
            self.evidence_id = artifact["evidence_id"]
        if not self.evidence:
            self.evidence = [EvidenceReference(self.evidence_id, "integration")]
        if not self.completeness:
            self.completeness = (
                "complete"
                if self.status in {
                    IntegrationStatus.PASS,
                    IntegrationStatus.FAIL,
                    IntegrationStatus.NOT_ENABLED,
                }
                else "unknown"
            )
        if not self.applicability:
            self.applicability = (
                "not_applicable"
                if self.status == IntegrationStatus.NOT_ENABLED
                else "unknown"
                if self.status == IntegrationStatus.MISCONFIGURED
                else "applicable"
            )
        if not self.canonical_evidence:
            return

        domain_report = {
            "status": self.status.value,
            "summary": self.summary or None,
            "tool_version": self.tool_version,
            "evidence_id": self.evidence_id,
            "evidence": [reference.to_dict() for reference in self.evidence],
            "findings": [
                {
                    "severity": finding.severity or None,
                    "message": finding.message or None,
                    "file": _artifact_path(finding.file, self.path_context) or None,
                    "line": finding.line,
                    "code": finding.code or None,
                    "url": finding.url or None,
                }
                for finding in self.findings
            ],
        }
        report_binding = integration_binding(domain_report)
        self.source_binding = self.source_binding or report_binding
        self.policy_binding = self.policy_binding or integration_binding({"policy": "unspecified"})
        self.scope_binding = self.scope_binding or integration_binding({
            "provider": self.provider,
            "path_context": _artifact_path(self.path_context, self.path_context),
        })
        self.canonical_artifact = EvidenceArtifact.create(
            kind="fettle.integration",
            producer={
                "id": "fettle.integration",
                "version": __version__,
                "implementation_digest": _producer_digest(),
            },
            result_state=_RESULT_STATES[self.status],
            completeness=self.completeness,
            trust_class=self.trust_class,
            source={"snapshot_digest": self.source_binding},
            policy_digest=self.policy_binding,
            scope_digest=self.scope_binding,
            observation_id="integration-" + uuid.uuid4().hex,
            observed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            payload={
                "applicability": self.applicability,
                "determinism": self.determinism,
                "domain_report": domain_report,
                "domain_report_digest": report_binding,
                "provider": self.provider,
                "tool_identity": self.tool_identity,
            },
        )
        self.canonical_reference = CanonicalEvidenceReference(
            artifact_digest=self.canonical_artifact.artifact_digest,
            kind=self.canonical_artifact.kind,
            expected={
                "source_snapshot_digest": self.source_binding,
                "policy_digest": self.policy_binding,
                "scope_digest": self.scope_binding,
                "producer_id": self.canonical_artifact.producer["id"],
            },
        )


class IntegrationAdapter(Protocol):
    name: str

    def is_available(self, config: dict[str, Any]) -> IntegrationStatus: ...

    def run(self, cwd: str, config: dict[str, Any]) -> IntegrationReport: ...


def format_integration_report(report: IntegrationReport, adapter_name: str) -> str:
    """Format an integration report as human-readable output."""
    lines = ["## " + adapter_name + " — " + report.status.value.upper()]
    if report.summary:
        lines.append(report.summary)
    if report.tool_version:
        lines.append("Tool version: " + report.tool_version)
    lines.append("")

    if report.findings:
        for f in report.findings[:20]:
            loc = (f.file + ":" + str(f.line)) if f.file else ""
            lines.append("- [" + f.severity + "] " + loc + " " + f.message)
        lines.append("")

    return "\n".join(lines)
