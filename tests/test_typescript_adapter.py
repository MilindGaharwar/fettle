"""Integration tests for TypeScript/JavaScript language adapter.

Tests adapter methods with mocked tool outputs — no actual eslint/biome/tsc
installation required. Verifies parsing, graceful absence, and finding structure.
"""

import json
import os
import sys
from dataclasses import dataclass
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from adapters.typescript_adapter import TypeScriptAdapter
from finding import FindingSeverity
from profile import Profile


@dataclass
class MockResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    tool_missing: bool = False


class TestDetection:
    def test_detects_typescript(self):
        adapter = TypeScriptAdapter()
        assert adapter.detect(Profile(languages=["typescript"]))

    def test_detects_javascript(self):
        adapter = TypeScriptAdapter()
        assert adapter.detect(Profile(languages=["javascript"]))

    def test_rejects_python(self):
        adapter = TypeScriptAdapter()
        assert not adapter.detect(Profile(languages=["python"]))

    def test_rejects_empty(self):
        adapter = TypeScriptAdapter()
        assert not adapter.detect(Profile(languages=[]))


class TestLint:
    def test_eslint_clean_returns_empty(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        biome_miss = MockResult(tool_missing=True)
        eslint_clean = MockResult(returncode=0, stdout="[]")

        with patch.object(adapter._runner, "run", side_effect=[biome_miss, eslint_clean]):
            findings = adapter.lint("fast", [str(tmp_path / "app.ts")])
        assert findings == []

    def test_eslint_findings_parsed(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        eslint_output = json.dumps([{
            "filePath": "/tmp/app.ts",
            "messages": [
                {"line": 5, "column": 3, "severity": 2, "ruleId": "no-unused-vars", "message": "'x' is defined but never used"},
                {"line": 10, "column": 1, "severity": 1, "ruleId": "semi", "message": "Missing semicolon"},
            ]
        }])
        biome_miss = MockResult(tool_missing=True)
        eslint_result = MockResult(returncode=1, stdout=eslint_output)

        with patch.object(adapter._runner, "run", side_effect=[biome_miss, eslint_result]):
            findings = adapter.lint("fast", ["/tmp/app.ts"])

        assert len(findings) == 2
        assert findings[0].file == "/tmp/app.ts"
        assert findings[0].line == 5
        assert findings[0].code == "no-unused-vars"
        assert findings[0].severity == FindingSeverity.ERROR
        assert findings[1].severity == FindingSeverity.WARNING

    def test_biome_findings_parsed(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        biome_output = json.dumps({
            "diagnostics": [
                {"file": "src/app.ts", "line": 3, "message": "Unsafe any", "rule": "noExplicitAny"}
            ]
        })
        biome_result = MockResult(returncode=1, stdout=biome_output)

        with patch.object(adapter._runner, "run", return_value=biome_result):
            findings = adapter.lint("fast", ["src/app.ts"])

        assert len(findings) == 1
        assert findings[0].checker == "biome"
        assert findings[0].code == "noExplicitAny"

    def test_no_lint_tools_returns_advisory(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        miss = MockResult(tool_missing=True)

        with patch.object(adapter._runner, "run", return_value=miss):
            findings = adapter.lint("fast", ["app.ts"])

        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.INFO
        assert "biome" in findings[0].message.lower() or "eslint" in findings[0].message.lower()

    def test_malformed_eslint_json_no_crash(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        biome_miss = MockResult(tool_missing=True)
        bad_json = MockResult(returncode=1, stdout="NOT JSON{{{")

        with patch.object(adapter._runner, "run", side_effect=[biome_miss, bad_json]):
            findings = adapter.lint("fast", ["app.ts"])
        assert findings == []


class TestTypecheck:
    def test_tsc_clean(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        with patch.object(adapter._runner, "run", return_value=MockResult(returncode=0)):
            findings = adapter.typecheck("fast", [])
        assert findings == []

    def test_tsc_errors_parsed(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        tsc_out = "src/api.ts(12,5): error TS2322: Type 'string' is not assignable to type 'number'.\nsrc/api.ts(20,1): error TS2304: Cannot find name 'foo'.\n"
        with patch.object(adapter._runner, "run", return_value=MockResult(returncode=1, stdout=tsc_out)):
            findings = adapter.typecheck("fast", [])

        assert len(findings) == 2
        assert findings[0].file == "src/api.ts"
        assert findings[0].line == 12
        assert findings[0].code == "TS2322"
        assert "not assignable" in findings[0].message
        assert findings[1].line == 20
        assert findings[1].code == "TS2304"

    def test_tsc_missing(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        with patch.object(adapter._runner, "run", return_value=MockResult(tool_missing=True)):
            findings = adapter.typecheck("fast", [])
        assert len(findings) == 1
        assert "tsc" in findings[0].message


class TestFormatCheck:
    def test_biome_format_clean(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        with patch.object(adapter._runner, "run", return_value=MockResult(returncode=0)):
            findings = adapter.format_check("fast", ["app.ts"])
        assert findings == []

    def test_biome_format_violations(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        with patch.object(adapter._runner, "run", return_value=MockResult(returncode=1)):
            findings = adapter.format_check("fast", ["app.ts"])
        assert len(findings) == 1
        assert findings[0].checker == "biome-format"
        assert "biome format --write" in findings[0].suggested_fix

    def test_prettier_fallback(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        biome_miss = MockResult(tool_missing=True)
        prettier_fail = MockResult(returncode=1)

        with patch.object(adapter._runner, "run", side_effect=[biome_miss, prettier_fail]):
            findings = adapter.format_check("fast", ["app.ts"])
        assert len(findings) == 1
        assert "prettier" in findings[0].suggested_fix


class TestBuild:
    def test_pnpm_ci_success(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        with patch.object(adapter._runner, "run", return_value=MockResult(returncode=0)):
            findings = adapter.build("fast")
        assert findings == []

    def test_npm_ci_failure(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        pnpm_miss = MockResult(tool_missing=True)
        npm_fail = MockResult(returncode=1, stderr="ERR! peer dep missing")

        with patch.object(adapter._runner, "run", side_effect=[pnpm_miss, npm_fail]):
            findings = adapter.build("fast")
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.ERROR
        assert findings[0].blocking is True

    def test_no_package_manager(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        miss = MockResult(tool_missing=True)

        with patch.object(adapter._runner, "run", return_value=miss):
            findings = adapter.build("fast")
        assert len(findings) == 1
        assert "package manager" in findings[0].message.lower()


class TestDependencyCheck:
    def test_knip_clean(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        with patch.object(adapter._runner, "run", return_value=MockResult(returncode=0)):
            findings = adapter.dependency_check(["app.ts"])
        assert findings == []

    def test_knip_finds_unused(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        with patch.object(adapter._runner, "run", return_value=MockResult(returncode=1, stdout='{"unused":["lodash"]}')):
            findings = adapter.dependency_check(["app.ts"])
        assert len(findings) == 1
        assert "unused" in findings[0].message.lower()

    def test_knip_missing(self, tmp_path):
        adapter = TypeScriptAdapter(cwd=str(tmp_path))
        with patch.object(adapter._runner, "run", return_value=MockResult(tool_missing=True)):
            findings = adapter.dependency_check(["app.ts"])
        assert len(findings) == 1
        assert "knip" in findings[0].message
