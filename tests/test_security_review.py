"""WP-P — Security Review Command tests."""

import json
import textwrap
from unittest.mock import patch, MagicMock

from fettle.security_review import (
    run_security_review,
    format_report,
    _run_ruff_security,
    _run_semgrep_owasp,
)


def test_ruff_security_finds_sql_injection(tmp_path):
    src = tmp_path / "app.py"
    # The in-string nosemgrep exempts this intentional fixture from repo-level
    # semgrep scans; the test itself exercises ruff (S608), which ignores it.
    src.write_text(textwrap.dedent("""
        def get_user(user_id):
            query = f"SELECT * FROM users WHERE id = {user_id}"  # nosemgrep
            return db.execute(query)
    """))
    findings = _run_ruff_security(str(tmp_path))
    sql_findings = [f for f in findings if f["code"] == "S608"]
    assert len(sql_findings) >= 1
    assert sql_findings[0]["cwe"] == "CWE-89 (SQL Injection)"


def test_ruff_missing_returns_empty(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("x = 1\n")
    with patch("fettle.security_review.subprocess.run", side_effect=FileNotFoundError):
        findings = _run_ruff_security(str(tmp_path))
    assert findings == []


def test_semgrep_missing_returns_empty(tmp_path):
    with patch("fettle.security_review.subprocess.run", side_effect=FileNotFoundError):
        findings = _run_semgrep_owasp(str(tmp_path))
    assert findings == []


def test_semgrep_parses_results(tmp_path):
    mock_output = json.dumps({
        "results": [{
            "check_id": "python.lang.security.injection.sql-injection",
            "path": "app.py",
            "start": {"line": 5},
            "extra": {
                "message": "SQL injection detected",
                "severity": "ERROR",
                "metadata": {"cwe": "CWE-89"},
            },
        }]
    })
    mock_result = MagicMock()
    mock_result.stdout = mock_output
    mock_result.returncode = 0

    with patch("fettle.security_review.subprocess.run", return_value=mock_result):
        findings = _run_semgrep_owasp(str(tmp_path))
    assert len(findings) == 1
    assert findings[0]["cwe"] == "CWE-89"
    assert findings[0]["tool"] == "semgrep"


def test_full_review_deduplicates(tmp_path):
    src = tmp_path / "app.py"
    src.write_text('query = f"SELECT * FROM t WHERE id = {x}"\n')  # nosemgrep: sql-fstring — intentional vulnerable fixture

    report = run_security_review(str(tmp_path))
    # Same finding from both tools should be deduped
    keys = [f"{f['file']}:{f['line']}:{f['code']}" for f in report["findings"]]
    assert len(keys) == len(set(keys))


def test_clean_code_no_findings(tmp_path):
    src = tmp_path / "clean.py"
    src.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    report = run_security_review(str(tmp_path))
    assert report["findings"] == []


def test_format_report_with_findings():
    report = {
        "findings": [
            {"file": "app.py", "line": 5, "code": "S608", "message": "SQL injection",
             "severity": "HIGH", "cwe": "CWE-89 (SQL Injection)", "tool": "ruff"},
        ],
        "tools_used": ["ruff (S-rules, Python)"],
        "tools_missing": ["semgrep"],
        "target": "src/",
        "coverage_note": "Limited coverage.",
    }
    output = format_report(report)
    assert "HIGH" in output
    assert "CWE-89" in output
    assert "semgrep" in output
    assert "Findings (1)" in output


def test_format_report_no_findings():
    report = {
        "findings": [],
        "tools_used": ["ruff"],
        "tools_missing": [],
        "target": ".",
        "coverage_note": "OK",
    }
    output = format_report(report)
    assert "No security findings" in output
