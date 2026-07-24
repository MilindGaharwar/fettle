"""WP-145 — JUnit XML output for enterprise CI dashboards.

Converts normalized findings (the `fettle check --json` shape) into JUnit XML,
the lingua franca of CI result panes (GitLab, Jenkins, Azure DevOps, Bamboo).

Mapping:
- one <testsuite name="fettle"> per report
- one <testcase> per finding; classname = file, name = "code @ line"
- error-severity findings  -> <failure type="error">
- warning/info findings    -> <failure type="warning"> (visible but dashboards
  can filter on type); suites report failures = error count only
- zero findings            -> single passing "no-findings" testcase so the
  suite never shows up empty
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def findings_to_junit(findings: list[dict[str, Any]], suite_name: str = "fettle") -> str:
    """Render findings as a JUnit XML string."""
    errors = [f for f in findings if str(f.get("severity", "")).lower() == "error"]
    suite = ET.Element("testsuite", {
        "name": suite_name,
        "tests": str(max(len(findings), 1)),
        "failures": str(len(errors)),
        "errors": "0",
        "skipped": "0",
    })

    if not findings:
        ET.SubElement(suite, "testcase", {
            "classname": suite_name,
            "name": "no-findings",
        })
    for f in findings:
        file = str(f.get("file", ""))
        line = f.get("line", 0)
        code = str(f.get("code", "unknown"))
        severity = str(f.get("severity", "info")).lower()
        case = ET.SubElement(suite, "testcase", {
            "classname": file or suite_name,
            "name": f"{code} @ line {line}",
        })
        failure = ET.SubElement(case, "failure", {
            "type": "error" if severity == "error" else "warning",
            "message": str(f.get("message", ""))[:512],
        })
        failure.text = f"{file}:{line} {code} [{severity}] ({f.get('tool', '')})"

    root = ET.Element("testsuites", {
        "tests": suite.get("tests", "0"),
        "failures": suite.get("failures", "0"),
    })
    root.append(suite)
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
