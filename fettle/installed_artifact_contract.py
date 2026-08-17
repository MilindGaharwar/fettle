"""Fail-closed validation for installed-artifact release evidence."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


SCHEMA_VERSION = "1"
_DIGEST = re.compile(r"[0-9a-f]{64}")
_UTC_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")
_POLICY_FIELDS = {"schema_version", "hosts"}
_HOST_POLICY_FIELDS = {
    "claim", "candidate_contract", "public_canary", "live_evidence",
    "live_evidence_max_age_days",
}
_REPORT_FIELDS = {
    "schema_version", "stage", "package", "environment", "bridge", "doctor", "hosts",
}
_PACKAGE_FIELDS = {"name", "version", "wheel"}
_WHEEL_FIELDS = {"filename", "sha256", "size"}
_ENVIRONMENT_FIELDS = {"python", "os", "architecture", "pipx", "checkout_independent"}
_BRIDGE_FIELDS = {"state", "version", "manifest_sha256"}
_HOST_FIELDS = {"registration", "transport", "live_evidence"}
_LIVE_FIELDS = {"state", "observed_at", "host_version", "reference"}


@dataclass(frozen=True)
class HostPolicy:
    claim: str
    live_evidence: str
    live_evidence_max_age_days: int


@dataclass(frozen=True)
class CapabilityPolicy:
    hosts: dict[str, HostPolicy]


@dataclass(frozen=True)
class LiveEvidence:
    state: str
    observed_at: datetime | None


@dataclass(frozen=True)
class HostEvidence:
    live_evidence: LiveEvidence


@dataclass(frozen=True)
class ContractReport:
    stage: str
    artifact_identity: tuple[str, str, str, int]
    hosts: dict[str, HostEvidence]
    complete: bool = True


@dataclass(frozen=True)
class ReleaseEvidenceResult:
    ok: bool
    claims: dict[str, str]
    errors: tuple[str, ...]


def _exact_fields(value: Mapping[str, object], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} has missing or unknown fields")


def _object(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _text(value: object, name: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum:
        raise ValueError(f"{name} must be non-empty bounded text")
    return value.strip()


def _digest(value: object, name: str) -> str:
    value = _text(value, name, maximum=64)
    if not _DIGEST.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _decode_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _read_json(value: str | bytes | Path | Mapping[str, object]) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, Path):
        raw = value.read_bytes()
    else:
        raw = value.encode() if isinstance(value, str) else value
    if len(raw) > 1024 * 1024 or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("contract evidence must be canonical UTF-8 JSON under 1 MiB")
    try:
        parsed = json.loads(raw, object_pairs_hook=_decode_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid contract JSON: {exc}") from exc
    return _object(parsed, "contract document")


def _default_policy_path() -> Path:
    return Path(__file__).with_name("host-capabilities.json")


def load_capability_policy(
    value: str | bytes | Path | Mapping[str, object] | None = None,
) -> CapabilityPolicy:
    document = _read_json(_default_policy_path() if value is None else value)
    _exact_fields(document, _POLICY_FIELDS, "capability policy")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("capability policy has an unsupported schema_version")
    raw_hosts = _object(document["hosts"], "capability policy hosts")
    if not raw_hosts:
        raise ValueError("capability policy must declare at least one host")
    hosts: dict[str, HostPolicy] = {}
    for host_name, raw_host in sorted(raw_hosts.items()):
        name = _text(host_name, "host name", maximum=64)
        host = _object(raw_host, f"{name} policy")
        _exact_fields(host, _HOST_POLICY_FIELDS, f"{name} policy")
        claim = _text(host["claim"], f"{name}.claim")
        if claim not in {"supported-installed", "contract-tested", "clone-only", "blocked", "unsupported"}:
            raise ValueError(f"{name}.claim is unsupported")
        for criterion in ("candidate_contract", "public_canary"):
            if host[criterion] != "required":
                raise ValueError(f"{name}.{criterion} must be required")
        live = _text(host["live_evidence"], f"{name}.live_evidence")
        if live not in {"required-for-claim", "not-required-for-claim"}:
            raise ValueError(f"{name}.live_evidence is unsupported")
        if claim == "supported-installed" and live != "required-for-claim":
            raise ValueError(f"{name}: supported-installed requires live evidence")
        hosts[name] = HostPolicy(
            claim=claim,
            live_evidence=live,
            live_evidence_max_age_days=_positive_int(
                host["live_evidence_max_age_days"], f"{name}.live_evidence_max_age_days",
            ),
        )
    return CapabilityPolicy(hosts)


def _instant(value: object, name: str) -> datetime:
    text = _text(value, name)
    if not _UTC_INSTANT.fullmatch(text):
        raise ValueError(f"{name} must be a UTC RFC 3339 instant")
    return datetime.fromisoformat(text[:-1] + "+00:00")


def validate_report(
    value: str | bytes | Path | Mapping[str, object],
    *,
    policy: CapabilityPolicy | None = None,
) -> ContractReport:
    policy = policy or load_capability_policy()
    document = _read_json(value)
    _exact_fields(document, _REPORT_FIELDS, "contract report")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("contract report has an unsupported schema_version")
    stage = _text(document["stage"], "stage")
    if stage not in {"candidate", "public"}:
        raise ValueError("stage must be candidate or public")

    package = _object(document["package"], "package")
    _exact_fields(package, _PACKAGE_FIELDS, "package")
    wheel = _object(package["wheel"], "package.wheel")
    _exact_fields(wheel, _WHEEL_FIELDS, "package.wheel")
    package_name = _text(package["name"], "package.name")
    version = _text(package["version"], "package.version")
    filename = _text(wheel["filename"], "package.wheel.filename")
    if package_name != "finefettle" or version not in filename or not filename.endswith(".whl"):
        raise ValueError("package identity does not describe a finefettle wheel")
    artifact_identity = (
        package_name, version, _digest(wheel["sha256"], "package.wheel.sha256"),
        _positive_int(wheel["size"], "package.wheel.size"),
    )

    environment = _object(document["environment"], "environment")
    _exact_fields(environment, _ENVIRONMENT_FIELDS, "environment")
    for field in ("python", "os", "architecture", "pipx"):
        _text(environment[field], f"environment.{field}")
    if environment["checkout_independent"] is not True:
        raise ValueError("environment must prove checkout independence")

    bridge = _object(document["bridge"], "bridge")
    _exact_fields(bridge, _BRIDGE_FIELDS, "bridge")
    if bridge["state"] != "pass" or bridge["version"] != version:
        raise ValueError("bridge must pass and match the package version")
    _digest(bridge["manifest_sha256"], "bridge.manifest_sha256")
    if document["doctor"] != "pass":
        raise ValueError("doctor must pass")

    raw_hosts = _object(document["hosts"], "hosts")
    if set(raw_hosts) != set(policy.hosts):
        raise ValueError("report host set does not match capability policy")
    hosts: dict[str, HostEvidence] = {}
    for host_name, raw_host in sorted(raw_hosts.items()):
        host = _object(raw_host, host_name)
        _exact_fields(host, _HOST_FIELDS, host_name)
        for criterion in ("registration", "transport"):
            if host[criterion] != "pass":
                raise ValueError(f"{host_name}.{criterion} must pass")
        live = _object(host["live_evidence"], f"{host_name}.live_evidence")
        _exact_fields(live, _LIVE_FIELDS, f"{host_name}.live_evidence")
        state = _text(live["state"], f"{host_name}.live_evidence.state")
        if state not in {"pass", "blocked"}:
            raise ValueError(f"{host_name}.live_evidence.state is unsupported")
        observed_at = None
        if state == "pass":
            observed_at = _instant(live["observed_at"], f"{host_name}.live_evidence.observed_at")
        elif live["observed_at"] is not None:
            raise ValueError(f"{host_name}: blocked live evidence cannot claim an observation time")
        _text(live["host_version"], f"{host_name}.live_evidence.host_version")
        _text(live["reference"], f"{host_name}.live_evidence.reference", maximum=512)
        hosts[host_name] = HostEvidence(LiveEvidence(state, observed_at))
    return ContractReport(stage, artifact_identity, hosts)


def validate_release_evidence(
    candidate: str | bytes | Path | Mapping[str, object],
    public: str | bytes | Path | Mapping[str, object],
    *,
    policy: CapabilityPolicy | None = None,
    now: datetime | None = None,
) -> ReleaseEvidenceResult:
    policy = policy or load_capability_policy()
    candidate_report = validate_report(candidate, policy=policy)
    public_report = validate_report(public, policy=policy)
    errors: list[str] = []
    if candidate_report.stage != "candidate":
        errors.append("candidate report has the wrong stage")
    if public_report.stage != "public":
        errors.append("public report has the wrong stage")
    if candidate_report.artifact_identity != public_report.artifact_identity:
        errors.append("public artifact identity does not match candidate")
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    claims: dict[str, str] = {}
    for host_name, host_policy in sorted(policy.hosts.items()):
        claims[host_name] = host_policy.claim
        if host_policy.live_evidence != "required-for-claim":
            continue
        for report_name, report in (("candidate", candidate_report), ("public", public_report)):
            live = report.hosts[host_name].live_evidence
            if live.state != "pass" or live.observed_at is None:
                errors.append(f"{host_name}: {report_name} live evidence did not pass")
                continue
            maximum_age = timedelta(days=host_policy.live_evidence_max_age_days)
            if live.observed_at > current or current - live.observed_at > maximum_age:
                errors.append(f"{host_name}: live evidence is stale")
                break
    return ReleaseEvidenceResult(not errors, claims, tuple(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate installed-artifact release evidence")
    parser.add_argument("candidate", type=Path)
    parser.add_argument("public", type=Path)
    parser.add_argument("--policy", type=Path, default=_default_policy_path())
    args = parser.parse_args(argv)
    try:
        result = validate_release_evidence(
            args.candidate, args.public, policy=load_capability_policy(args.policy),
        )
    except (OSError, ValueError) as exc:
        print(f"installed artifact evidence invalid: {exc}")
        return 1
    if not result.ok:
        print("installed artifact evidence failed: " + "; ".join(result.errors))
        return 1
    print("installed artifact evidence passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
