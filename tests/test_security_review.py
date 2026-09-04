"""WP-P — Security Review Command tests."""

import json
import subprocess
import textwrap
from unittest.mock import patch, MagicMock

from fettle.config import load_config
from fettle.evidence import ResultState, Validity
from fettle.security_review import (
    EVIDENCE_RELPATH,
    REPORT_RELPATH,
    _write_review,
    run_security_review,
    format_report,
    _run_ruff_security,
    _run_semgrep_owasp,
    _security_rules_path,
    validate_canonical_evidence,
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
    findings, error = _run_ruff_security(str(tmp_path))
    assert error is None
    sql_findings = [f for f in findings if f["code"] == "S608"]
    assert len(sql_findings) >= 1
    assert sql_findings[0]["cwe"] == "CWE-89 (SQL Injection)"


def test_ruff_missing_returns_error(tmp_path):
    src = tmp_path / "app.py"
    src.write_text("x = 1\n")
    with patch("fettle.security_review.subprocess.run", side_effect=FileNotFoundError):
        findings, error = _run_ruff_security(str(tmp_path))
    assert findings == []
    assert error is not None and "ruff" in error


def test_semgrep_missing_returns_error(tmp_path):
    with patch("fettle.security_review.subprocess.run", side_effect=FileNotFoundError):
        findings, error = _run_semgrep_owasp(str(tmp_path))
    assert findings == []
    assert error is not None and "semgrep" in error


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
        findings, error = _run_semgrep_owasp(str(tmp_path))
    assert error is None
    assert len(findings) == 1
    assert findings[0]["cwe"] == "CWE-89"
    assert findings[0]["tool"] == "semgrep"


def test_bundled_semgrep_policy_fires_on_sql_fstring(tmp_path):
    keyword = "SEL" + "ECT"
    (tmp_path / "app.py").write_text(
        f'query = f"{keyword} * FROM users WHERE id = {{user_id}}"\n',
        encoding="utf-8",
    )

    findings, error = _run_semgrep_owasp(str(tmp_path))

    assert error is None
    assert any(item["code"] == "security-sql-fstring-python" for item in findings)


def test_scanner_process_failure_is_not_clean(tmp_path):
    failed = MagicMock(stdout="", stderr="scanner crashed", returncode=2)

    with patch("fettle.security_review.subprocess.run", return_value=failed):
        ruff_findings, ruff_error = _run_ruff_security(str(tmp_path))
        semgrep_findings, semgrep_error = _run_semgrep_owasp(str(tmp_path))

    assert ruff_findings == []
    assert semgrep_findings == []
    assert "exit 2" in ruff_error
    assert "exit 2" in semgrep_error


def test_security_rules_ignore_plugin_override(tmp_path, monkeypatch):
    attacker = tmp_path / "attacker" / "rules"
    attacker.mkdir(parents=True)
    (attacker / "security.yml").write_text("rules: []\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "attacker"))

    rules = _security_rules_path()

    assert rules.name == "security.yml"
    assert rules != attacker / "security.yml"


def test_tool_failure_marks_report_incomplete(tmp_path):
    """Stage-0: a security review with a dead tool must say so, loudly."""
    (tmp_path / "app.py").write_text("x = 1\n")
    with (
        patch("fettle.security_review._has_tool", return_value=True),
        patch("fettle.security_review.subprocess.run",
              side_effect=FileNotFoundError("gone")),
    ):
        report = run_security_review(str(tmp_path))
    assert len(report["tool_errors"]) == 2
    text = format_report(report)
    assert "INCOMPLETE REVIEW" in text


def test_clean_report_has_no_tool_errors(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    report = run_security_review(str(tmp_path))
    assert report["tool_errors"] == []
    assert "INCOMPLETE REVIEW" not in format_report(report)


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


def test_review_separates_policy_advisories_from_blocking_findings(tmp_path):
    (tmp_path / "app.py").write_text("assert True\n", encoding="utf-8")

    report = run_security_review(str(tmp_path), load_config(str(tmp_path)))

    assert any(item["code"] == "S101" for item in report["findings"])
    assert report["blocking_findings"] == []


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
    assert "No blocking security findings" in output


def _init_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@fettle.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "test"], check=True,
    )
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".fettle/\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "app.py", ".gitignore"], check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "seed"], check=True,
    )


def _report(*, findings=None, tool_errors=None):
    return {
        "findings": findings or [],
        "tools_used": ["ruff (S-rules, Python)", "semgrep (Fettle security rules)"],
        "tools_missing": [],
        "tool_errors": tool_errors or [],
        "target": ".",
        "scanned_paths": ["app.py"],
        "coverage_note": "Bounded security checks; not comprehensive OWASP coverage.",
    }


def test_clean_review_writes_valid_canonical_evidence(tmp_path):
    _init_repo(tmp_path)
    report = _report()

    assert _write_review(str(tmp_path), report, load_config(str(tmp_path))) is None
    retained = json.loads((tmp_path / REPORT_RELPATH).read_text(encoding="utf-8"))
    result = validate_canonical_evidence(str(tmp_path), load_config(str(tmp_path)), retained)

    assert result.validity == Validity.VALID
    assert result.result_state == ResultState.PASS
    assert (tmp_path / EVIDENCE_RELPATH).is_file()


def test_security_finding_is_valid_violation_evidence(tmp_path):
    _init_repo(tmp_path)
    report = _report(findings=[{
        "file": "app.py", "line": 1, "code": "S608", "message": "injection",
        "severity": "HIGH", "cwe": "CWE-89", "tool": "ruff",
    }])

    assert _write_review(str(tmp_path), report, load_config(str(tmp_path))) is None
    retained = json.loads((tmp_path / REPORT_RELPATH).read_text(encoding="utf-8"))
    result = validate_canonical_evidence(str(tmp_path), load_config(str(tmp_path)), retained)

    assert result.validity == Validity.VALID
    assert result.result_state == ResultState.VIOLATION


def test_tool_error_cannot_produce_authoritative_security_evidence(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / EVIDENCE_RELPATH).parent.mkdir()
    (tmp_path / EVIDENCE_RELPATH).write_text("old pass", encoding="utf-8")

    error = _write_review(
        str(tmp_path), _report(tool_errors=["semgrep: timeout"]),
        load_config(str(tmp_path)),
    )

    assert error is None
    assert not (tmp_path / EVIDENCE_RELPATH).exists()
    retained = json.loads((tmp_path / REPORT_RELPATH).read_text(encoding="utf-8"))
    assert "canonical_evidence" not in retained


def test_malformed_findings_cannot_produce_authoritative_security_evidence(tmp_path):
    _init_repo(tmp_path)
    report = _report()
    report["findings"] = {"unexpected": "shape"}

    assert _write_review(str(tmp_path), report, load_config(str(tmp_path))) is None
    retained = json.loads((tmp_path / REPORT_RELPATH).read_text(encoding="utf-8"))

    assert "canonical_evidence" not in retained
    assert not (tmp_path / EVIDENCE_RELPATH).exists()


def test_unignored_state_directory_cannot_produce_self_invalidating_evidence(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("", encoding="utf-8")

    error = _write_review(str(tmp_path), _report(), load_config(str(tmp_path)))

    assert ".fettle/ must be ignored" in error
    assert not (tmp_path / EVIDENCE_RELPATH).exists()


def test_target_outside_repository_cannot_produce_evidence(tmp_path):
    _init_repo(tmp_path)
    report = _report()
    report["target"] = "../outside"

    error = _write_review(str(tmp_path), report, load_config(str(tmp_path)))

    assert "inside the repository" in error
    assert not (tmp_path / EVIDENCE_RELPATH).exists()


def test_scan_that_does_not_cover_changed_scope_is_diagnostic_only(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("value = 2\n", encoding="utf-8")
    report = _report()
    report["scanned_paths"] = []

    error = _write_review(str(tmp_path), report, load_config(str(tmp_path)))

    assert error is None
    retained = json.loads((tmp_path / REPORT_RELPATH).read_text(encoding="utf-8"))
    assert "canonical_evidence" not in retained
    assert not (tmp_path / EVIDENCE_RELPATH).exists()


def test_advisory_ruff_finding_does_not_make_canonical_result_fail(tmp_path):
    _init_repo(tmp_path)
    report = _report(findings=[{
        "file": "app.py", "line": 1, "code": "S101", "message": "assert",
        "severity": "MEDIUM", "cwe": "", "tool": "ruff",
    }])

    assert _write_review(str(tmp_path), report, load_config(str(tmp_path))) is None
    retained = json.loads((tmp_path / REPORT_RELPATH).read_text(encoding="utf-8"))
    result = validate_canonical_evidence(str(tmp_path), load_config(str(tmp_path)), retained)

    assert len(retained["findings"]) == 1
    assert retained["blocking_findings"] == []
    assert result.result_state == ResultState.PASS


def test_absolute_target_and_finding_paths_are_retained_portably(tmp_path):
    _init_repo(tmp_path)
    report = _report(findings=[{
        "file": str(tmp_path / "app.py"), "line": 1, "code": "S105",
        "message": "credential", "severity": "MEDIUM", "cwe": "CWE-798",
        "tool": "ruff",
    }])
    report["target"] = str(tmp_path)

    assert _write_review(str(tmp_path), report, load_config(str(tmp_path))) is None
    retained = json.loads((tmp_path / REPORT_RELPATH).read_text(encoding="utf-8"))

    assert retained["target"] == "."
    assert retained["findings"][0]["file"] == "app.py"
    assert str(tmp_path) not in (tmp_path / EVIDENCE_RELPATH).read_text(encoding="utf-8")


def test_security_evidence_for_old_source_is_rejected(tmp_path):
    _init_repo(tmp_path)
    report = _report()
    assert _write_review(str(tmp_path), report, load_config(str(tmp_path))) is None
    retained = json.loads((tmp_path / REPORT_RELPATH).read_text(encoding="utf-8"))
    (tmp_path / "app.py").write_text("value = 2\n", encoding="utf-8")

    result = validate_canonical_evidence(str(tmp_path), load_config(str(tmp_path)), retained)

    assert result.validity == Validity.WRONG_SOURCE


def test_tampered_security_evidence_is_rejected(tmp_path):
    _init_repo(tmp_path)
    report = _report()
    assert _write_review(str(tmp_path), report, load_config(str(tmp_path))) is None
    retained = json.loads((tmp_path / REPORT_RELPATH).read_text(encoding="utf-8"))
    artifact_path = tmp_path / EVIDENCE_RELPATH
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["payload"]["findings_count"] = 99
    artifact_path.write_text(
        json.dumps(artifact, sort_keys=True, separators=(",", ":")), encoding="utf-8",
    )

    result = validate_canonical_evidence(str(tmp_path), load_config(str(tmp_path)), retained)

    assert result.validity == Validity.TAMPERED
