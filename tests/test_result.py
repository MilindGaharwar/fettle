"""Tests for scripts/result.py — result taxonomy."""

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from result import (
    Finding, ResultStatus, Severity,
    make_pass, make_violation, make_tool_error, make_config_error, make_skipped,
)


def test_pass_result():
    r = make_pass()
    assert r.status == ResultStatus.PASS
    assert not r.has_errors
    assert not r.findings


def test_violation_result():
    findings = [
        Finding(tool="ruff", severity=Severity.ERROR, path="test.py", line=10, code="F401", message="unused import"),
    ]
    r = make_violation(findings, tool_name="ruff")
    assert r.status == ResultStatus.VIOLATION
    assert r.has_errors
    assert len(r.findings) == 1


def test_tool_error_result():
    r = make_tool_error("ruff", "not found in PATH")
    assert r.status == ResultStatus.TOOL_ERROR
    assert "ruff" in r.message
    assert "not found" in r.message


def test_config_error_result():
    r = make_config_error("invalid .fettle.toml")
    assert r.status == ResultStatus.CONFIG_ERROR
    assert "invalid" in r.message


def test_skipped_result():
    r = make_skipped("file not in scope")
    assert r.status == ResultStatus.SKIPPED


def test_hook_output_pass_is_empty():
    r = make_pass()
    output = r.to_hook_output()
    assert output == {}


def test_hook_output_violation_has_context():
    findings = [
        Finding(tool="semgrep", severity=Severity.ERROR, path="app.py", line=5, code="sql-fstring", message="SQL injection"),
    ]
    r = make_violation(findings)
    output = r.to_hook_output(hook_event="PostToolUse")
    assert "hookSpecificOutput" in output
    assert "SQL injection" in output["hookSpecificOutput"]["additionalContext"]


def test_hook_output_block_on_error():
    findings = [
        Finding(tool="ruff", severity=Severity.ERROR, path="x.py", line=1, code="BLE001", message="bare except"),
    ]
    r = make_violation(findings)
    output = r.to_hook_output(block=True)
    assert output.get("decision") == "block"


def test_hook_output_no_block_on_warning():
    findings = [
        Finding(tool="ruff", severity=Severity.WARNING, path="x.py", line=1, code="SIM101", message="simplify"),
    ]
    r = make_violation(findings)
    output = r.to_hook_output(block=True)
    assert "decision" not in output


def test_finding_to_dict():
    f = Finding(tool="ruff", severity=Severity.ERROR, path="test.py", line=10, code="F401", message="unused")
    d = f.to_dict()
    assert d["tool"] == "ruff"
    assert d["severity"] == "error"
    assert d["line"] == 10
