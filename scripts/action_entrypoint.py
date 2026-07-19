"""Fettle GitHub Action execution and SARIF output."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys


def main() -> int:
    mode = os.environ.get("INPUT_MODE", "advisory").lower()
    if mode not in {"advisory", "enforce"}:
        print(f"::error::Invalid mode '{mode}'; expected advisory or enforce", file=sys.stderr)
        return 2
    sarif_enabled = os.environ.get("INPUT_SARIF", "true").lower() == "true"
    config_path = os.environ.get("INPUT_CONFIG", "")
    paths = shlex.split(os.environ.get("INPUT_PATHS", "."))
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    runner_temp = os.environ.get("RUNNER_TEMP", "/tmp")

    cmd = [sys.executable, "-m", "fettle", "check", "--json", "--all"]
    if config_path:
        os.environ["FETTLE_CONFIG"] = os.path.abspath(config_path)

    all_findings: list[dict] = []
    scan_failed = False
    for path in paths:
        scan_path = os.path.abspath(path)
        result = subprocess.run(
            [*cmd, "--root", scan_path],
            capture_output=True,
            text=True,
        )
        parsed = False
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                findings = data.get("findings", []) if isinstance(data, dict) else data
                all_findings.extend(findings)
                parsed = True
            except json.JSONDecodeError:
                print(f"::error::Could not parse fettle output for path '{path}'")
                print(result.stdout[:500], file=sys.stderr)
        if result.returncode not in (0, 1) or not parsed:
            scan_failed = True
        for line in result.stderr.strip().splitlines()[:10]:
            print(f"::debug::{line}")

    findings_count = len(all_findings)
    has_errors = any(str(f.get("severity", "")).lower() == "error" for f in all_findings)

    findings_path = os.path.join(runner_temp, "fettle-findings.json")
    with open(findings_path, "w") as f:
        json.dump(all_findings, f)

    sarif_file = ""
    if sarif_enabled:
        sarif_file = os.path.join(runner_temp, "fettle.sarif")
        with open(sarif_file, "w") as f:
            json.dump(_findings_to_sarif(all_findings), f, indent=2)

    exit_code = 2 if scan_failed else (1 if mode == "enforce" and has_errors else 0)
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"findings_count={findings_count}\n")
            f.write(f"sarif_file={sarif_file}\n")
            f.write(f"exit_code={exit_code}\n")

    print(f"Fettle: {findings_count} finding(s), mode={mode}, exit_code={exit_code}")
    if all_findings:
        errors = [f for f in all_findings if str(f.get("severity", "")).lower() == "error"]
        warnings = [f for f in all_findings if str(f.get("severity", "")).lower() != "error"]
        if errors:
            print(f"  {len(errors)} error(s), {len(warnings)} warning(s)")
        for finding in all_findings[:20]:
            sev = finding.get("severity", "info").upper()
            loc = f"{finding.get('file', '')}:{finding.get('line', '')}"
            print(f"  [{sev}] {loc} {finding.get('code', '')} - {finding.get('message', '')}")
        if findings_count > 20:
            print(f"  ... and {findings_count - 20} more")
    return exit_code


def _findings_to_sarif(findings: list[dict]) -> dict:
    """Convert findings to SARIF 2.1.0 format."""
    results = []
    rules: dict[str, dict] = {}
    for finding in findings:
        rule_id = finding.get("code", finding.get("rule", "unknown"))
        severity = str(finding.get("severity", "warning")).lower()
        file_path = finding.get("file", finding.get("path", ""))
        line = finding.get("line", 1)
        message = finding.get("message", "")
        sarif_level = {"error": "error", "warning": "warning", "info": "note"}.get(severity, "warning")
        rules.setdefault(rule_id, {
            "id": rule_id,
            "shortDescription": {"text": message[:100]},
            "defaultConfiguration": {"level": sarif_level},
        })
        results.append({
            "ruleId": rule_id,
            "level": sarif_level,
            "message": {"text": message},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": file_path},
                    "region": {"startLine": line},
                },
            }] if file_path else [],
        })
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "fettle",
                    "informationUri": "https://github.com/MilindGaharwar/fettle",
                    "rules": list(rules.values()),
                },
            },
            "results": results,
        }],
    }


if __name__ == "__main__":
    sys.exit(main())
