"""WP-113 — Debug Statement Detection contract tests.

Verifies that semgrep rules in llm-antipatterns.yml and ts-antipatterns.yml
detect leftover debug statements.
"""

import os
import subprocess

import pytest

RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules"
)


def _has_semgrep() -> bool:
    """Check if semgrep is available."""
    try:
        r = subprocess.run(["semgrep", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _has_semgrep(), reason="semgrep not available")


def _run_semgrep(rule_file: str, target_file: str) -> list[dict]:
    """Run semgrep with a rule file against a target, return findings."""
    import json
    result = subprocess.run(
        ["semgrep", "--config", rule_file, "--json", "--quiet", target_file],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode not in (0, 1):  # 1 = findings found
        return []
    try:
        data = json.loads(result.stdout)
        return data.get("results", [])
    except (json.JSONDecodeError, KeyError):
        return []


class TestPythonDebugDetection:
    def test_detects_breakpoint(self, tmp_path) -> None:
        f = tmp_path / "code.py"
        f.write_text("x = 1\nbreakpoint()\ny = 2\n")
        findings = _run_semgrep(
            os.path.join(RULES_DIR, "llm-antipatterns.yml"), str(f)
        )
        assert any("debug-breakpoint" in r.get("check_id", "") for r in findings)

    def test_detects_pdb_import(self, tmp_path) -> None:
        f = tmp_path / "code.py"
        f.write_text("import pdb\nx = 1\n")
        findings = _run_semgrep(
            os.path.join(RULES_DIR, "llm-antipatterns.yml"), str(f)
        )
        assert any("debug-pdb" in r.get("check_id", "") for r in findings)

    def test_detects_pdb_set_trace(self, tmp_path) -> None:
        f = tmp_path / "code.py"
        f.write_text("import pdb\npdb.set_trace()\n")
        findings = _run_semgrep(
            os.path.join(RULES_DIR, "llm-antipatterns.yml"), str(f)
        )
        assert any("debug-pdb" in r.get("check_id", "") for r in findings)

    def test_detects_print_in_non_cli(self, tmp_path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        f = src / "service.py"
        f.write_text("def process():\n    print('debug value')\n")
        findings = _run_semgrep(
            os.path.join(RULES_DIR, "llm-antipatterns.yml"), str(f)
        )
        assert any("debug-print" in r.get("check_id", "") for r in findings)

    def test_excludes_cli_paths_for_print(self, tmp_path) -> None:
        cli_dir = tmp_path / "cli"
        cli_dir.mkdir()
        f = cli_dir / "main.py"
        f.write_text("print('Hello user')\n")
        findings = _run_semgrep(
            os.path.join(RULES_DIR, "llm-antipatterns.yml"), str(f)
        )
        debug_prints = [r for r in findings if "debug-print" in r.get("check_id", "")]
        assert debug_prints == []


class TestTypeScriptDebugDetection:
    def test_detects_console_log(self, tmp_path) -> None:
        f = tmp_path / "app.ts"
        f.write_text("const x = 1;\nconsole.log('debug', x);\n")
        findings = _run_semgrep(
            os.path.join(RULES_DIR, "ts-antipatterns.yml"), str(f)
        )
        assert any("debug-console-log" in r.get("check_id", "") for r in findings)

    def test_detects_debugger_statement(self, tmp_path) -> None:
        f = tmp_path / "app.ts"
        f.write_text("function foo() {\n  debugger;\n  return 1;\n}\n")
        findings = _run_semgrep(
            os.path.join(RULES_DIR, "ts-antipatterns.yml"), str(f)
        )
        assert any("debug-debugger" in r.get("check_id", "") for r in findings)

    def test_excludes_scripts_for_console_log(self, tmp_path) -> None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        f = scripts_dir / "build.js"
        f.write_text("console.log('Building...');\n")
        findings = _run_semgrep(
            os.path.join(RULES_DIR, "ts-antipatterns.yml"), str(f)
        )
        console_logs = [r for r in findings if "debug-console-log" in r.get("check_id", "")]
        assert console_logs == []

    def test_debugger_is_error_severity(self, tmp_path) -> None:
        f = tmp_path / "app.ts"
        f.write_text("debugger;\n")
        findings = _run_semgrep(
            os.path.join(RULES_DIR, "ts-antipatterns.yml"), str(f)
        )
        debugger_findings = [r for r in findings if "debug-debugger" in r.get("check_id", "")]
        assert debugger_findings
        assert debugger_findings[0].get("extra", {}).get("severity") == "ERROR"
