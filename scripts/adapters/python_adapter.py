"""Fettle v0.5.0 — WP-78: Python language adapter.

Wraps ruff (lint+format), pyright/mypy (typecheck), pytest (test),
deptry (dependency check), pip install -e . (build).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finding import CheckFinding, FindingSeverity, Confidence
from profile import Profile
from tool_runner import ToolRunner


class PythonAdapter:
    """Python language adapter using ruff, pyright, pytest, deptry."""

    language = "python"

    def __init__(self, cwd: str | None = None):
        self._cwd = cwd or os.getcwd()
        self._runner = ToolRunner(timeout_s=60, cwd=self._cwd)
        self._ruff_cmd = "ruff"
        self._pyright_cmd = "pyright"
        self._pytest_cmd = "python3"
        self._deptry_cmd = "deptry"

    def detect(self, profile: Profile) -> bool:
        return "python" in profile.languages

    def lint(self, tier: str, files: list[str]) -> list[CheckFinding]:
        args = [self._ruff_cmd, "check", "--output-format=json"]
        if files:
            args.extend(files)
        else:
            args.append(".")
        result = self._runner.run(args)
        if result.tool_missing:
            return [self._advisory(f"{self._ruff_cmd} not found — install with: pip install ruff")]
        if result.returncode == 0:
            return []
        return self._parse_ruff_json(result.stdout)

    def format_check(self, tier: str, files: list[str]) -> list[CheckFinding]:
        args = [self._ruff_cmd, "format", "--check", "--diff"]
        if files:
            args.extend(files)
        else:
            args.append(".")
        result = self._runner.run(args)
        if result.tool_missing:
            return [self._advisory(f"{self._ruff_cmd} not found — install with: pip install ruff")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="ruff-format",
            severity=FindingSeverity.WARNING,
            file=files[0] if files else ".",
            line=0,
            message="Format violations found",
            suggested_fix=f"Run: ruff format {' '.join(files) if files else '.'}",
            rerun_command=f"ruff format --check {' '.join(files) if files else '.'}",
        )]

    def typecheck(self, tier: str, files: list[str]) -> list[CheckFinding]:
        args = [self._pyright_cmd, "--outputjson"]
        if files:
            args.extend(files)
        result = self._runner.run(args)
        if result.tool_missing:
            return [self._advisory(f"{self._pyright_cmd} not available — install with: pip install pyright")]
        if result.returncode == 0:
            return []
        return self._parse_pyright_json(result.stdout)

    def test(self, tier: str, files: list[str]) -> list[CheckFinding]:
        args = [self._pytest_cmd, "-m", "pytest", "-q", "--tb=short"]
        if files:
            args.extend(files)
        result = self._runner.run(args)
        if result.tool_missing:
            return [self._advisory("pytest not available")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="pytest",
            severity=FindingSeverity.ERROR,
            file=files[0] if files else ".",
            line=0,
            message="Test failures detected",
            raw_tool_output=result.stdout[-2048:] if result.stdout else "",
            rerun_command=f"python3 -m pytest {' '.join(files) if files else ''}",
            blocking=True,
        )]

    def build(self, tier: str) -> list[CheckFinding]:
        result = self._runner.run(["pip", "install", "-e", ".", "--dry-run"])
        if result.tool_missing:
            return [self._advisory("pip not available")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="pip-install",
            severity=FindingSeverity.ERROR,
            file="pyproject.toml",
            line=0,
            message="Package install failed",
            raw_tool_output=result.stderr[-2048:] if result.stderr else "",
            blocking=True,
        )]

    def dependency_check(self, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run([self._deptry_cmd, "."])
        if result.tool_missing:
            return [self._advisory(f"{self._deptry_cmd} not available — install with: pip install deptry")]
        if result.returncode == 0:
            return []
        return self._parse_deptry_output(result.stdout)

    def _advisory(self, message: str) -> CheckFinding:
        return CheckFinding(
            checker="python-adapter",
            severity=FindingSeverity.INFO,
            file="",
            line=0,
            message=message,
            confidence=Confidence.HIGH,
            blocking=False,
        )

    def _parse_ruff_json(self, output: str) -> list[CheckFinding]:
        import json
        findings = []
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return self._parse_ruff_text(output)
        for item in data:
            findings.append(CheckFinding(
                checker="ruff",
                severity=FindingSeverity.ERROR,
                file=item.get("filename", ""),
                line=item.get("location", {}).get("row", 0),
                column=item.get("location", {}).get("column"),
                code=item.get("code", ""),
                message=item.get("message", ""),
                suggested_fix=item.get("fix", {}).get("message") if item.get("fix") else None,
                rerun_command=f"ruff check {item.get('filename', '')}",
            ))
        return findings

    def _parse_ruff_text(self, output: str) -> list[CheckFinding]:
        import re
        findings = []
        for line in output.strip().splitlines():
            m = re.match(r"(.+?):(\d+):(\d+): (\w+) (.+)", line)
            if m:
                findings.append(CheckFinding(
                    checker="ruff",
                    severity=FindingSeverity.ERROR,
                    file=m.group(1),
                    line=int(m.group(2)),
                    column=int(m.group(3)),
                    code=m.group(4),
                    message=m.group(5),
                ))
        return findings

    def _parse_pyright_json(self, output: str) -> list[CheckFinding]:
        import json
        findings = []
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return []
        for diag in data.get("generalDiagnostics", []):
            sev = FindingSeverity.ERROR if diag.get("severity") == "error" else FindingSeverity.WARNING
            rng = diag.get("range", {}).get("start", {})
            findings.append(CheckFinding(
                checker="pyright",
                severity=sev,
                file=diag.get("file", ""),
                line=rng.get("line", 0) + 1,
                column=rng.get("character"),
                message=diag.get("message", ""),
                code=diag.get("rule"),
            ))
        return findings

    def _parse_deptry_output(self, output: str) -> list[CheckFinding]:
        findings = []
        for line in output.strip().splitlines():
            if line.strip():
                findings.append(CheckFinding(
                    checker="deptry",
                    severity=FindingSeverity.WARNING,
                    file="pyproject.toml",
                    line=0,
                    message=line.strip(),
                ))
        return findings
