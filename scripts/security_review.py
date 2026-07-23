"""WP-P — Security Review Command.

Orchestrates ruff S-rules + semgrep OWASP patterns to produce a
security-focused review. Scoped claims: runs available tools, does
NOT claim comprehensive OWASP coverage.

Supported: Python (full via ruff S + semgrep), TS/JS/Go (semgrep only).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))


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


def _run_ruff_security(target: str) -> list[dict]:
    """Run ruff with S-rules only (Python security checks)."""
    findings = []
    try:
        result = subprocess.run(
            ["ruff", "check", "--select", "S", "--output-format", "json", target],
            capture_output=True, text=True, timeout=60, env=_ENV,
        )
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
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return findings


def _run_semgrep_owasp(target: str) -> list[dict]:
    """Run semgrep with OWASP rules if available."""
    findings = []
    try:
        result = subprocess.run(
            ["semgrep", "scan", "--config", "p/owasp-top-ten",
             "--json", "--quiet", "--metrics=off", target],
            capture_output=True, text=True, timeout=120, env=_ENV,
        )
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
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return findings


def _has_tool(name: str) -> bool:
    import shutil
    if shutil.which(name):
        return True
    local = os.path.expanduser(f"~/.local/bin/{name}")
    return os.path.isfile(local) and os.access(local, os.X_OK)


def run_security_review(target: str) -> dict:
    """Run security review on target path. Returns structured report."""
    findings: list[dict] = []
    tools_used: list[str] = []
    tools_missing: list[str] = []

    if _has_tool("ruff"):
        tools_used.append("ruff (S-rules, Python)")
        findings.extend(_run_ruff_security(target))
    else:
        tools_missing.append("ruff")

    if _has_tool("semgrep"):
        tools_used.append("semgrep (p/owasp-top-ten, multi-language)")
        findings.extend(_run_semgrep_owasp(target))
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

    return {
        "findings": unique,
        "tools_used": tools_used,
        "tools_missing": tools_missing,
        "target": target,
        "coverage_note": (
            "Python: ruff S-rules + semgrep OWASP. "
            "TS/JS/Go: semgrep only. "
            "This is NOT comprehensive OWASP coverage — it runs available tools."
        ),
    }


def format_report(report: dict) -> str:
    """Format the report as human-readable markdown."""
    lines = ["# Security Review: " + report["target"], ""]
    lines.append("**Tools used:** " + ", ".join(report["tools_used"] or ["none"]))
    if report["tools_missing"]:
        lines.append("**Tools missing:** " + ", ".join(report["tools_missing"]))
    lines.append("**Note:** " + report["coverage_note"])
    lines.append("")

    findings = report["findings"]
    if not findings:
        lines.append("## No security findings detected.")
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

    report = run_security_review(args.path)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))

    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
