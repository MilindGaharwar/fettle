"""Tests for fettle.junit — JUnit XML output for CI dashboards."""

import xml.etree.ElementTree as ET

from fettle.junit import findings_to_junit


class TestFindingsToJunit:
    def test_empty_findings_produces_passing_case(self):
        xml_str = findings_to_junit([])
        root = ET.fromstring(xml_str)
        suite = root.find("testsuite")
        assert suite.get("failures") == "0"
        cases = suite.findall("testcase")
        assert len(cases) == 1
        assert cases[0].get("name") == "no-findings"

    def test_error_finding_becomes_failure(self):
        findings = [{"file": "app.py", "line": 10, "code": "E001",
                     "severity": "error", "message": "bad thing", "tool": "ruff"}]
        xml_str = findings_to_junit(findings)
        root = ET.fromstring(xml_str)
        suite = root.find("testsuite")
        assert suite.get("failures") == "1"
        case = suite.find("testcase")
        assert case.get("classname") == "app.py"
        assert "E001" in case.get("name")
        failure = case.find("failure")
        assert failure.get("type") == "error"
        assert "bad thing" in failure.get("message")

    def test_warning_finding_type(self):
        findings = [{"file": "x.py", "line": 1, "code": "W001",
                     "severity": "warning", "message": "warn"}]
        xml_str = findings_to_junit(findings)
        root = ET.fromstring(xml_str)
        failure = root.find(".//failure")
        assert failure.get("type") == "warning"

    def test_multiple_findings(self):
        findings = [
            {"file": "a.py", "line": 1, "code": "E1", "severity": "error", "message": "m1"},
            {"file": "b.py", "line": 2, "code": "W1", "severity": "warning", "message": "m2"},
            {"file": "c.py", "line": 3, "code": "I1", "severity": "info", "message": "m3"},
        ]
        xml_str = findings_to_junit(findings)
        root = ET.fromstring(xml_str)
        suite = root.find("testsuite")
        assert suite.get("tests") == "3"
        assert suite.get("failures") == "1"
        cases = suite.findall("testcase")
        assert len(cases) == 3

    def test_custom_suite_name(self):
        xml_str = findings_to_junit([], suite_name="my-project")
        root = ET.fromstring(xml_str)
        suite = root.find("testsuite")
        assert suite.get("name") == "my-project"

    def test_valid_xml_declaration(self):
        xml_str = findings_to_junit([])
        assert xml_str.startswith("<?xml")
