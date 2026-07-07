#!/usr/bin/env python3
"""Fettle SARIF output — convert findings to Static Analysis Results Interchange Format.

SARIF is the standard format for GitHub code scanning, VS Code, and enterprise tools.

Usage:
    python3 sarif.py --root . > fettle.sarif
    python3 quality_scan.py --root . --json | python3 sarif.py --from-json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


def findings_to_sarif(findings: list[dict], tool_name: str = "fettle") -> dict:
    """Convert Fettle findings to SARIF format."""
    results = []
    rules = {}

    for f in findings:
        rule_id = f.get("code", f.get("rule", "unknown"))
        severity = f.get("severity", "warning")
        file_path = f.get("file", f.get("path", ""))
        line = f.get("line", 1)
        message = f.get("message", "")
        sarif_level = {
            "error": "error",
            "warning": "warning",
            "info": "note",
        }.get(severity, "warning")

        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": message[:100]},
                "defaultConfiguration": {"level": sarif_level},
            }

        result = {
            "ruleId": rule_id,
            "level": sarif_level,
            "message": {"text": message},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": file_path},
                    "region": {"startLine": line},
                },
            }] if file_path else [],
        }
        results.append(result)

    sarif = {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [{
            "tool": {
                "driver": {
                    "name": "fettle",
                    "version": "0.4.0",
                    "informationUri": "https://github.com/MilindGaharwar/fettle",
                    "rules": list(rules.values()),
                },
            },
            "results": results,
        }],
    }
    return sarif


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle SARIF output")
    parser.add_argument("--from-json", action="store_true", help="Read findings JSON from stdin")
    parser.add_argument("--root", help="Project root for scanning")
    args = parser.parse_args()

    if args.from_json:
        data = json.load(sys.stdin)
        findings = data.get("findings", data) if isinstance(data, dict) else data
    elif args.root:
        from config import load_config
        from quality_scan import scan_project
        cfg = load_config(args.root)
        results = scan_project(args.root, cfg, json_output=True)
        findings = results.get("findings", [])
    else:
        print("Use --from-json or --root PATH", file=sys.stderr)
        sys.exit(1)

    sarif = findings_to_sarif(findings)
    print(json.dumps(sarif, indent=2))


if __name__ == "__main__":
    main()
