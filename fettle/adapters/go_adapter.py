"""Fettle v0.5.0 — WP-96: Go language adapter.

Wraps golangci-lint (lint), gofmt (format), go vet (typecheck),
go test ./... (test), govulncheck (deps), go build ./... (build).
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fettle.finding import CheckFinding, FindingSeverity, Confidence
from fettle.paths import FileKind, classify_file
from fettle.profile import Profile
from fettle.tool_runner import ToolRunner
from fettle.adapters import CheckRun, as_check_run, semgrep_findings
from fettle.workspace import Workspace


class GoAdapter:
    """Go language adapter."""

    language = "go"
    extensions = frozenset({".go"})

    def __init__(self, cwd: str | None = None):
        self._cwd = cwd or os.getcwd()
        self._runner = ToolRunner(timeout_s=90, cwd=self._cwd)
        self._config: dict = {}

    def detect(self, profile: Profile) -> bool:
        return "go" in profile.languages

    def supports(self, workspace: Workspace) -> bool:
        return workspace.language == self.language

    def classify(self, path: str, workspace: Workspace) -> FileKind:
        return classify_file(path)

    def lint(self, workspace: Workspace, files: list[str]) -> CheckRun:
        return as_check_run(
            self, workspace, self._native_lint(workspace, files),
            "changed" if files else "full",
        )

    def _native_lint(self, workspace: Workspace, files: list[str]) -> list[CheckFinding]:
        findings = semgrep_findings(
            files, cwd=self._cwd, config=self._config, rule_pack="go-antipatterns.yml",
        )
        result = self._runner.run(["golangci-lint", "run", "--out-format=line-number"])
        if result.tool_missing:
            result = self._runner.run(["go", "vet", "./..."])
            if result.tool_missing:
                return findings + [self._advisory("Neither golangci-lint nor go found")]
            if result.returncode == 0:
                return findings
            return findings + self._parse_go_output(result.stderr, "go-vet")
        if result.returncode == 0:
            return findings
        return findings + self._parse_golangci(result.stdout)

    def format_check(self, workspace: Workspace, files: list[str]) -> CheckRun:
        return as_check_run(
            self, workspace, self._format_check(files), "changed" if files else "full",
        )

    def _format_check(self, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run(["gofmt", "-l", "."])
        if result.tool_missing:
            return [self._advisory("gofmt not found")]
        if not result.stdout.strip():
            return []
        unformatted = result.stdout.strip().splitlines()
        return [CheckFinding(
            checker="gofmt", severity=FindingSeverity.WARNING,
            file=f.strip(), line=0,
            message="File not formatted",
            suggested_fix="Run: gofmt -w .",
        ) for f in unformatted[:10]]

    def typecheck(self, workspace: Workspace, files: list[str]) -> CheckRun:
        return as_check_run(
            self, workspace, self._typecheck(), "changed" if files else "full",
        )

    def _typecheck(self) -> list[CheckFinding]:
        result = self._runner.run(["go", "vet", "./..."])
        if result.tool_missing:
            return [self._advisory("go not found")]
        if result.returncode == 0:
            return []
        return self._parse_go_output(result.stderr, "go-vet")

    def test(self, workspace: Workspace, files: list[str], scope: str) -> CheckRun:
        return as_check_run(self, workspace, self._test(), scope)

    def _test(self) -> list[CheckFinding]:
        result = self._runner.run(["go", "test", "./..."])
        if result.tool_missing:
            return [self._advisory("go not found")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="go-test", severity=FindingSeverity.ERROR,
            file=".", line=0, message="Test failures detected",
            raw_tool_output=result.stdout[-2048:],
            blocking=True,
        )]

    def build(self, workspace: Workspace) -> CheckRun:
        return as_check_run(self, workspace, self._build(), "full")

    def _build(self) -> list[CheckFinding]:
        result = self._runner.run(["go", "build", "./..."])
        if result.tool_missing:
            return [self._advisory("go not found")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="go-build", severity=FindingSeverity.ERROR,
            file=".", line=0, message="Build failed",
            raw_tool_output=result.stderr[-2048:],
            blocking=True,
        )]

    def dependency_check(self, workspace: Workspace) -> CheckRun:
        return as_check_run(self, workspace, self._dependency_check(), "full")

    def _dependency_check(self) -> list[CheckFinding]:
        result = self._runner.run(["govulncheck", "./..."])
        if result.tool_missing:
            return [self._advisory("govulncheck not installed — run: go install golang.org/x/vuln/cmd/govulncheck@latest")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="govulncheck", severity=FindingSeverity.WARNING,
            file="go.mod", line=0,
            message="Vulnerabilities found in dependencies",
            raw_tool_output=result.stdout[-2048:],
        )]

    def _advisory(self, message: str) -> CheckFinding:
        return CheckFinding(
            checker="go-adapter", severity=FindingSeverity.INFO,
            file="", line=0, message=message,
            confidence=Confidence.HIGH, blocking=False,
        )

    def _parse_golangci(self, output: str) -> list[CheckFinding]:
        findings = []
        for line in output.splitlines():
            m = re.match(r"(.+?):(\d+)(?::(\d+))?: (.+)", line)
            if m:
                findings.append(CheckFinding(
                    checker="golangci-lint", severity=FindingSeverity.WARNING,
                    file=m.group(1), line=int(m.group(2)),
                    column=int(m.group(3)) if m.group(3) else None,
                    message=m.group(4),
                ))
        return findings

    def _parse_go_output(self, output: str, checker: str) -> list[CheckFinding]:
        findings = []
        for line in output.splitlines():
            m = re.match(r"(.+?):(\d+)(?::(\d+))?: (.+)", line)
            if m:
                findings.append(CheckFinding(
                    checker=checker, severity=FindingSeverity.WARNING,
                    file=m.group(1), line=int(m.group(2)),
                    column=int(m.group(3)) if m.group(3) else None,
                    message=m.group(4),
                ))
        return findings
