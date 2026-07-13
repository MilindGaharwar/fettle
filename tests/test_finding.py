"""Tests for scripts/finding.py — WP-69 structured finding/result schema.

The canonical format all checkers emit. Every downstream consumer
(runner, hooks, CI comparison, dashboard) reads this schema.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from finding import (
    CheckFinding,
    CheckResult,
    Confidence,
    FindingSeverity,
    sort_findings,
    to_json,
    to_human,
    to_sarif,
    redact_finding,
    SCHEMA_VERSION,
)


# --- Serialization ---


def test_finding_serializes_to_json():
    f = CheckFinding(
        checker="ruff",
        severity=FindingSeverity.ERROR,
        file="src/app.py",
        line=10,
        column=5,
        message="unused import os",
        code="F401",
        suggested_fix="Remove `import os`",
        rerun_command="ruff check src/app.py",
    )
    data = f.to_dict()
    assert data["checker"] == "ruff"
    assert data["severity"] == "error"
    assert data["file"] == "src/app.py"
    assert data["line"] == 10
    assert data["column"] == 5
    assert data["message"] == "unused import os"
    assert data["suggested_fix"] == "Remove `import os`"
    assert data["rerun_command"] == "ruff check src/app.py"
    # roundtrip via JSON
    text = json.dumps(data)
    parsed = json.loads(text)
    assert parsed == data


def test_finding_serializes_to_human_readable():
    f = CheckFinding(
        checker="semgrep",
        severity=FindingSeverity.ERROR,
        file="api/routes.py",
        line=42,
        message="SQL injection via f-string",
        code="sql-fstring",
    )
    line = f.to_human()
    assert "ERROR" in line
    assert "api/routes.py:42" in line
    assert "sql-fstring" in line
    assert "SQL injection" in line


def test_findings_sorted_deterministically():
    findings = [
        CheckFinding(checker="ruff", severity=FindingSeverity.WARNING, file="b.py", line=5, message="simplify"),
        CheckFinding(checker="ruff", severity=FindingSeverity.ERROR, file="a.py", line=10, message="bare except"),
        CheckFinding(checker="ruff", severity=FindingSeverity.ERROR, file="a.py", line=3, message="unused import"),
        CheckFinding(checker="semgrep", severity=FindingSeverity.INFO, file="c.py", line=1, message="note"),
    ]
    sorted_f = sort_findings(findings)
    # Sorted by: file ASC, line ASC, severity DESC (error first)
    assert sorted_f[0].file == "a.py" and sorted_f[0].line == 3
    assert sorted_f[1].file == "a.py" and sorted_f[1].line == 10
    assert sorted_f[2].file == "b.py"
    assert sorted_f[3].file == "c.py"


def test_secret_values_redacted_in_output():
    f = CheckFinding(
        checker="gitleaks",
        severity=FindingSeverity.ERROR,
        file="config.py",
        line=5,
        message="AWS key found: AKIAIOSFODNN7EXAMPLE",
        raw_tool_output="match: AKIAIOSFODNN7EXAMPLE secret_value=abcdef123",
    )
    redacted = redact_finding(f)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted.message
    assert "REDACTED" in redacted.message or "***" in redacted.message
    assert "abcdef123" not in (redacted.raw_tool_output or "")


def test_long_output_truncated():
    long_output = "x" * 5000
    f = CheckFinding(
        checker="ruff",
        severity=FindingSeverity.ERROR,
        file="big.py",
        line=1,
        message="error",
        raw_tool_output=long_output,
    )
    data = f.to_dict()
    assert len(data.get("raw_tool_output", "")) <= 2048


def test_multiple_workspaces_grouped():
    findings = [
        CheckFinding(checker="ruff", severity=FindingSeverity.ERROR, file="backend/app.py", line=1, message="e1", workspace="backend"),
        CheckFinding(checker="eslint", severity=FindingSeverity.ERROR, file="frontend/App.tsx", line=1, message="e2", workspace="frontend"),
        CheckFinding(checker="ruff", severity=FindingSeverity.WARNING, file="backend/util.py", line=5, message="w1", workspace="backend"),
    ]
    human = to_human(findings)
    # Workspace sections should appear
    assert "backend" in human
    assert "frontend" in human


def test_sarif_export_valid():
    findings = [
        CheckFinding(
            checker="ruff",
            severity=FindingSeverity.ERROR,
            file="src/app.py",
            line=10,
            column=5,
            message="unused import",
            code="F401",
        ),
    ]
    sarif = to_sarif(findings)
    assert sarif["$schema"] == "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"
    assert sarif["version"] == "2.1.0"
    runs = sarif["runs"]
    assert len(runs) == 1
    results = runs[0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "F401"
    assert results[0]["level"] == "error"
    loc = results[0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "src/app.py"
    assert loc["region"]["startLine"] == 10


def test_schema_version_included():
    f = CheckFinding(checker="ruff", severity=FindingSeverity.ERROR, file="x.py", line=1, message="err")
    data = f.to_dict()
    assert data.get("schema_version") == SCHEMA_VERSION


def test_empty_findings_produces_clean_output():
    human = to_human([])
    assert human.strip() == "" or "No findings" in human
    json_out = to_json([])
    parsed = json.loads(json_out)
    assert parsed["findings"] == []
    assert parsed["schema_version"] == SCHEMA_VERSION


# --- CheckResult ---


def test_check_result_aggregation():
    findings = [
        CheckFinding(checker="ruff", severity=FindingSeverity.ERROR, file="a.py", line=1, message="err", blocking=True),
        CheckFinding(checker="ruff", severity=FindingSeverity.WARNING, file="b.py", line=2, message="warn"),
    ]
    result = CheckResult(findings=findings, duration_ms=150.0)
    assert result.has_blocking
    assert result.error_count == 1
    assert result.warning_count == 1
    assert result.exit_code == 2


def test_check_result_no_blocking():
    findings = [
        CheckFinding(checker="ruff", severity=FindingSeverity.WARNING, file="b.py", line=2, message="warn"),
    ]
    result = CheckResult(findings=findings, duration_ms=50.0)
    assert not result.has_blocking
    assert result.exit_code == 1


def test_check_result_pass():
    result = CheckResult(findings=[], duration_ms=10.0)
    assert result.exit_code == 0


# --- Confidence ---


def test_confidence_ordering():
    assert Confidence.HIGH.weight > Confidence.MEDIUM.weight > Confidence.LOW.weight


# --- Blocking logic ---


def test_error_is_blocking_by_default():
    f = CheckFinding(checker="ruff", severity=FindingSeverity.ERROR, file="x.py", line=1, message="err")
    assert f.blocking is True


def test_warning_is_not_blocking_by_default():
    f = CheckFinding(checker="ruff", severity=FindingSeverity.WARNING, file="x.py", line=1, message="warn")
    assert f.blocking is False


def test_info_is_not_blocking():
    f = CheckFinding(checker="ruff", severity=FindingSeverity.INFO, file="x.py", line=1, message="note")
    assert f.blocking is False


def test_blocking_override():
    f = CheckFinding(checker="ruff", severity=FindingSeverity.WARNING, file="x.py", line=1, message="warn", blocking=True)
    assert f.blocking is True
