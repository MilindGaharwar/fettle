"""WP-P — Security Review Command.

Orchestrates ruff S-rules + semgrep OWASP patterns to produce a
security-focused review. Scoped claims: runs available tools, does
NOT claim comprehensive OWASP coverage.

Supported: Python (full via ruff S + semgrep), TS/JS/Go (semgrep only).
"""

from __future__ import annotations

import json
import contextlib
import hashlib
import os
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fettle import __version__
from fettle.evidence import (
    EvidenceArtifact,
    EvidenceValidationContext,
    EvidenceValidationResult,
    ResultState,
    Validity,
    validate_artifact,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root (clone mode)


REPORT_RELPATH = ".fettle/security-review.json"
EVIDENCE_RELPATH = ".fettle/security-review.evidence.json"
PRODUCER_ID = "fettle.security.review"
RULESET_NAME = "security.yml"
_REQUIRED_TOOLS = {
    "ruff (S-rules, Python)",
    "semgrep (Fettle security rules)",
}

_CWE_MAP = {
    "S608": "CWE-89 (SQL Injection)",
    "S701": "CWE-79 (XSS)",
    "S110": "CWE-390 (Error Swallowing)",
    "S105": "CWE-798 (Hardcoded Credentials)",
    "S106": "CWE-798 (Hardcoded Credentials)",
    "S107": "CWE-798 (Hardcoded Credentials)",
    "S301": "CWE-502 (Insecure Deserialization)",
    "S302": "CWE-502 (Insecure Deserialization)",
    "S303": "CWE-328 (Weak Hash)",
    "S324": "CWE-328 (Weak Hash)",
    "S501": "CWE-295 (Improper Certificate Validation)",
    "S602": "CWE-78 (OS Command Injection)",
    "S603": "CWE-78 (OS Command Injection)",
    "S604": "CWE-78 (OS Command Injection)",
    "S605": "CWE-78 (OS Command Injection)",
    "S607": "CWE-78 (OS Command Injection)",
}

_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def _scan_args(target: str | list[str]) -> list[str]:
    return [target] if isinstance(target, str) else target


def _run_ruff_security(target: str | list[str]) -> tuple[list[dict], str | None]:
    """Run ruff with S-rules only. Returns (findings, error).

    A tool failure is returned, never swallowed — a security review that
    silently scanned nothing is worse than no review at all.
    """
    findings = []
    try:
        result = subprocess.run(
            ["ruff", "check", "--select", "S", "--output-format", "json",
             *_scan_args(target)],
            capture_output=True, text=True, timeout=60, env=_ENV,
        )
        if result.returncode not in {0, 1}:
            return findings, f"ruff: exit {result.returncode}: {result.stderr.strip()}"
        if result.stdout.strip():
            for item in json.loads(result.stdout):
                code = item.get("code", "")
                findings.append({
                    "file": item.get("filename", ""),
                    "line": item.get("location", {}).get("row", 0),
                    "code": code,
                    "message": item.get("message", ""),
                    "severity": "HIGH" if code in ("S608", "S701", "S602", "S301") else "MEDIUM",
                    "cwe": _CWE_MAP.get(code, ""),
                    "tool": "ruff",
                })
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
        return findings, f"ruff: {type(exc).__name__}: {exc}"
    return findings, None


def _run_semgrep_owasp(target: str | list[str]) -> tuple[list[dict], str | None]:
    """Run Semgrep with Fettle's pinned security rules. Returns findings/error."""
    findings = []
    try:
        rules = _security_rules_path()
        if not rules.is_file():
            return findings, f"semgrep: pinned ruleset is unavailable: {RULESET_NAME}"
        result = subprocess.run(
            ["semgrep", "scan", "--config", str(rules),
             "--json", "--quiet", "--metrics=off", *_scan_args(target)],
            capture_output=True, text=True, timeout=120, env=_ENV,
        )
        if result.returncode not in {0, 1}:
            return findings, f"semgrep: exit {result.returncode}: {result.stderr.strip()}"
        if result.stdout.strip():
            data = json.loads(result.stdout)
            for item in data.get("results", []):
                extra = item.get("extra", {})
                findings.append({
                    "file": item.get("path", ""),
                    "line": item.get("start", {}).get("line", 0),
                    "code": item.get("check_id", "").split(".")[-1],
                    "message": extra.get("message", item.get("check_id", "")),
                    "severity": extra.get("severity", "WARNING").upper(),
                    "cwe": extra.get("metadata", {}).get("cwe", ""),
                    "tool": "semgrep",
                })
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
        return findings, f"semgrep: {type(exc).__name__}: {exc}"
    return findings, None


def _has_tool(name: str) -> bool:
    import shutil
    if shutil.which(name):
        return True
    local = os.path.expanduser(f"~/.local/bin/{name}")
    return os.path.isfile(local) and os.access(local, os.X_OK)


def run_security_review(target: str | list[str], config: dict | None = None) -> dict:
    """Run security review on target path. Returns structured report."""
    findings: list[dict] = []
    tools_used: list[str] = []
    tools_missing: list[str] = []
    tool_errors: list[str] = []

    if _has_tool("ruff"):
        tools_used.append("ruff (S-rules, Python)")
        ruff_findings, ruff_error = _run_ruff_security(target)
        findings.extend(ruff_findings)
        if ruff_error:
            tool_errors.append(ruff_error)
    else:
        tools_missing.append("ruff")

    if _has_tool("semgrep"):
        tools_used.append("semgrep (Fettle security rules)")
        semgrep_findings, semgrep_error = _run_semgrep_owasp(target)
        findings.extend(semgrep_findings)
        if semgrep_error:
            tool_errors.append(semgrep_error)
    else:
        tools_missing.append("semgrep")

    # Deduplicate by file+line+code
    seen: set[str] = set()
    unique: list[dict] = []
    for f in findings:
        key = f"{f['file']}:{f['line']}:{f['code']}"
        if key not in seen:
            seen.add(key)
            unique.append(f)

    # Sort by severity then file
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "WARNING": 2}
    unique.sort(key=lambda f: (severity_order.get(f["severity"], 4), f["file"], f["line"]))

    error_rules = set((config or {}).get("severity", {}).get(
        "error_rules", ["BLE001", "S110", "S608", "S701"],
    ))
    blocking = [
        finding for finding in unique
        if finding["tool"] == "semgrep" or finding["code"] in error_rules
    ]
    scanned_paths = _scan_args(target)
    return {
        "findings": unique,
        "blocking_findings": blocking,
        "tools_used": tools_used,
        "tools_missing": tools_missing,
        "tool_errors": tool_errors,
        "target": "." if isinstance(target, list) else target,
        "scanned_paths": scanned_paths,
        "coverage_note": (
            "Python: Ruff S-rules plus Fettle's pinned Semgrep security rules. "
            "TS/JS/Go: pinned Semgrep security rules only. "
            "This is not comprehensive OWASP coverage."
        ),
    }


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    normalized = unicodedata.normalize("NFC", encoded).encode("utf-8")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _security_rules_path() -> Path:
    """Resolve only Fettle-owned rules; plugin overrides are not authoritative."""
    clone_rules = Path(__file__).resolve().parent.parent / "rules" / RULESET_NAME
    if clone_rules.is_file():
        return clone_rules
    return Path(__file__).resolve().parent / "_rules" / RULESET_NAME


def _assessment_context(cwd: str, config: dict) -> dict:
    from fettle.changeset import get_changed_files
    from fettle.source_snapshot import working_snapshot

    snapshot_result = working_snapshot(cwd)
    if snapshot_result.get("status") != "completed":
        raise ValueError(str(snapshot_result.get("message") or "cannot identify working source"))
    snapshot = snapshot_result["snapshot"]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True,
        timeout=5,
    )
    scope_rows = sorted({
        (item.path.replace("\\", "/"), item.status.value)
        for item in get_changed_files(cwd)
    })
    source = {"snapshot_digest": "sha256:" + snapshot["digest"]}
    if revision.returncode == 0 and revision.stdout.strip():
        source["revision"] = revision.stdout.strip()
    return {
        "source": source,
        "policy_digest": _json_digest(config),
        "scope_digest": _json_digest(scope_rows),
        "scope_paths": [path for path, status in scope_rows if status != "deleted"],
    }


def _producer_digest() -> str:
    digest = hashlib.sha256(Path(__file__).read_bytes())
    rules = _security_rules_path()
    digest.update(b"\0")
    digest.update(rules.read_bytes())
    return "sha256:" + digest.hexdigest()


def _report_projection(report: dict) -> dict:
    return {
        key: value for key, value in report.items()
        if key not in {"canonical_evidence", "canonical_observation_id"}
    }


def _artifact_reference(artifact: EvidenceArtifact) -> dict:
    return {
        "artifact_digest": artifact.artifact_digest,
        "kind": artifact.kind,
        "schema_version": artifact.schema_version,
        "expected": {
            "source_snapshot_digest": artifact.source["snapshot_digest"],
            "policy_digest": artifact.policy_digest,
            "scope_digest": artifact.scope_digest,
            "producer_id": artifact.producer["id"],
        },
    }


def _security_artifact(cwd: str, report: dict, config: dict) -> EvidenceArtifact:
    context = _assessment_context(cwd, config)
    findings = report.get("blocking_findings", [])
    return EvidenceArtifact.create(
        kind=PRODUCER_ID,
        producer={
            "id": PRODUCER_ID,
            "version": __version__,
            "implementation_digest": _producer_digest(),
        },
        result_state="violation" if findings else "pass",
        completeness="complete",
        trust_class="authoritative",
        source=context["source"],
        policy_digest=context["policy_digest"],
        scope_digest=context["scope_digest"],
        observation_id="security-" + uuid.uuid4().hex,
        observed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        payload={
            "findings_count": len(findings),
            "observations_count": len(report.get("findings", [])),
            "raw_report_digest": _json_digest(_report_projection(report)),
            "ruleset": RULESET_NAME,
            "tools": sorted(report.get("tools_used", [])),
        },
    )


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = ""
    finally:
        if temporary:
            with contextlib.suppress(OSError):
                os.unlink(temporary)


def _write_review(cwd: str, report: dict, config: dict) -> str | None:
    """Persist the raw report and, only when complete, its canonical sidecar."""
    root = Path(cwd)
    report_path = root / REPORT_RELPATH
    evidence_path = root / EVIDENCE_RELPATH
    with contextlib.suppress(OSError):
        evidence_path.unlink()
    retained = dict(_report_projection(report))
    retained.setdefault("scanned_paths", [str(retained.get("target") or ".")])
    error_rules = set(config.get("severity", {}).get("error_rules", []))
    observations = retained.get("findings")
    retained["blocking_findings"] = [
        finding for finding in observations
        if isinstance(finding, dict)
        and (finding.get("tool") == "semgrep" or finding.get("code") in error_rules)
    ] if isinstance(observations, list) else []
    complete = (
        set(retained.get("tools_used", [])) == _REQUIRED_TOOLS
        and retained.get("tools_missing") == []
        and retained.get("tool_errors") == []
        and isinstance(observations, list)
        and len(retained["blocking_findings"]) <= len(observations)
    )
    try:
        if complete:
            target = Path(str(retained.get("target") or "."))
            candidate = target if target.is_absolute() else root / target
            try:
                target_relative = candidate.resolve().relative_to(root.resolve())
            except ValueError as exc:
                raise ValueError("security review target must be inside the repository") from exc
            retained["target"] = target_relative.as_posix() or "."
            for key in ("findings", "blocking_findings"):
                portable_findings = []
                for finding in retained[key]:
                    if not isinstance(finding, dict):
                        raise ValueError("security finding must be an object")
                    finding_path = Path(str(finding.get("file") or ""))
                    absolute = finding_path if finding_path.is_absolute() else root / finding_path
                    try:
                        relative = absolute.resolve().relative_to(root.resolve())
                    except ValueError as exc:
                        raise ValueError("security finding path must be inside the repository") from exc
                    portable_findings.append({**finding, "file": relative.as_posix()})
                retained[key] = portable_findings
            scope_paths = set(_assessment_context(cwd, config)["scope_paths"])
            scanned_paths = set()
            for path in retained["scanned_paths"]:
                scan_path = Path(str(path))
                absolute = scan_path if scan_path.is_absolute() else root / scan_path
                try:
                    relative = absolute.resolve().relative_to(root.resolve())
                except ValueError as exc:
                    raise ValueError("security review path must be inside the repository") from exc
                scanned_paths.add(relative.as_posix() or ".")
            retained["scanned_paths"] = sorted(scanned_paths)
            if "." not in scanned_paths and not scope_paths <= scanned_paths:
                complete = False
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", ".fettle/security-review.json"],
                cwd=cwd, timeout=5,
            )
            if ignored.returncode != 0:
                raise ValueError(".fettle/ must be ignored before security evidence can be canonical")
            if complete:
                artifact = _security_artifact(cwd, retained, config)
                _write_bytes_atomic(evidence_path, artifact.to_bytes())
                retained["canonical_evidence"] = _artifact_reference(artifact)
                retained["canonical_observation_id"] = artifact.observation_id
        _write_bytes_atomic(
            report_path, (json.dumps(retained, indent=2) + "\n").encode("utf-8"),
        )
    except (OSError, subprocess.TimeoutExpired, TypeError, ValueError) as exc:
        with contextlib.suppress(OSError):
            evidence_path.unlink()
        return str(exc) or type(exc).__name__
    report.clear()
    report.update(retained)
    return None


def validate_canonical_evidence(
    cwd: str, config: dict, report: dict,
) -> EvidenceValidationResult:
    """Validate security evidence and its exact raw-report reference."""
    def failure(validity: Validity) -> EvidenceValidationResult:
        return EvidenceValidationResult(
            validity, ResultState.UNKNOWN,
            "python -m fettle.security_review --path . --json",
        )

    reference = report.get("canonical_evidence")
    if not isinstance(reference, dict):
        return failure(Validity.MALFORMED)
    if reference.get("schema_version") != "1" or reference.get("kind") != PRODUCER_ID:
        return failure(Validity.UNSUPPORTED)
    expected = reference.get("expected")
    if not isinstance(expected, dict):
        return failure(Validity.MALFORMED)
    try:
        assessment = _assessment_context(cwd, config)
        context = EvidenceValidationContext(
            kind=PRODUCER_ID,
            source_snapshot_digest=assessment["source"]["snapshot_digest"],
            source_revision=assessment["source"].get("revision"),
            policy_digest=assessment["policy_digest"],
            scope_digest=assessment["scope_digest"],
            producer_id=PRODUCER_ID,
            producer_versions=frozenset({__version__}),
            producer_implementation_digest=_producer_digest(),
            recovery_action="python -m fettle.security_review --path . --json",
        )
        content = (Path(cwd) / EVIDENCE_RELPATH).read_bytes()
    except FileNotFoundError:
        return failure(Validity.MISSING)
    except (OSError, subprocess.TimeoutExpired, TypeError, ValueError):
        return failure(Validity.UNAVAILABLE)
    result = validate_artifact(content, context)
    if result.validity != Validity.VALID:
        return result
    try:
        artifact = json.loads(content)
        requested = {
            "source_snapshot_digest": context.source_snapshot_digest,
            "policy_digest": context.policy_digest,
            "scope_digest": context.scope_digest,
            "producer_id": context.producer_id,
        }
        if reference.get("artifact_digest") != artifact["artifact_digest"]:
            return failure(Validity.TAMPERED)
        if report.get("canonical_observation_id") != artifact["observation_id"]:
            return failure(Validity.DUPLICATE_ID)
        if expected != requested:
            return failure(Validity.MALFORMED)
        if artifact["payload"]["raw_report_digest"] != _json_digest(_report_projection(report)):
            return failure(Validity.TAMPERED)
    except (KeyError, TypeError, json.JSONDecodeError):
        return failure(Validity.MALFORMED)
    return result


def format_report(report: dict) -> str:
    """Format the report as human-readable markdown."""
    lines = ["# Security Review: " + report["target"], ""]
    lines.append("**Tools used:** " + ", ".join(report["tools_used"] or ["none"]))
    if report["tools_missing"]:
        lines.append("**Tools missing:** " + ", ".join(report["tools_missing"]))
    if report.get("tool_errors"):
        lines.append("")
        lines.append("## ⚠ INCOMPLETE REVIEW — tool failures")
        for err in report["tool_errors"]:
            lines.append("- " + err)
        lines.append("Findings below may be missing entire tool coverage. "
                     "Fix the environment and re-run.")
    lines.append("**Note:** " + report["coverage_note"])
    lines.append("")

    findings = report.get("blocking_findings", report["findings"])
    if not findings:
        lines.append("## No blocking security findings detected.")
        if report["findings"]:
            lines.append(f"\nAdvisory observations: {len(report['findings'])}")
        return "\n".join(lines)

    lines.append("## Findings (" + str(len(findings)) + ")")
    lines.append("")

    for f in findings:
        cwe = " [" + f["cwe"] + "]" if f["cwe"] else ""
        lines.append(
            "- **" + f["severity"] + "** " + f["file"] + ":" + str(f["line"]) +
            " — " + f["code"] + cwe
        )
        lines.append("  " + f["message"])
        lines.append("")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fettle security review")
    parser.add_argument("--path", default=".", help="Target path to scan")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    try:
        root = subprocess.run(
            ["git", "-C", args.path, "rev-parse", "--show-toplevel"],
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        from fettle.config import load_config

        config = load_config(root)
        report = run_security_review(args.path, config)
        persistence_error = _write_review(root, report, config)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        report = run_security_review(args.path)
        persistence_error = "target is not inside an available Git repository"

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))

    # Exit contract mirrors `fettle check`: 0 clean, 1 findings, 2 env/tool
    # failure. A partial security scan is an environment failure, not a pass.
    if persistence_error:
        print(f"Security evidence unavailable: {persistence_error}", file=sys.stderr)
        return 2
    if report["tools_missing"] or report["tool_errors"]:
        return 2
    return 1 if report.get("blocking_findings", report["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
