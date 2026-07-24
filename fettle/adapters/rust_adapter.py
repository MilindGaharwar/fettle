"""Fettle v0.5.0 — WP-95: Rust language adapter.

Wraps cargo clippy (lint), cargo fmt (format), cargo check (typecheck),
cargo test (test), cargo audit (deps), cargo build (build).
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fettle.finding import CheckFinding, FindingSeverity, Confidence
from fettle.profile import Profile
from fettle.tool_runner import ToolRunner


class RustAdapter:
    """Rust language adapter using cargo toolchain."""

    language = "rust"

    def __init__(self, cwd: str | None = None):
        self._cwd = cwd or os.getcwd()
        self._runner = ToolRunner(timeout_s=120, cwd=self._cwd)

    def detect(self, profile: Profile) -> bool:
        return "rust" in profile.languages

    def lint(self, tier: str, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run(["cargo", "clippy", "--message-format=short", "--", "-D", "warnings"])
        if result.tool_missing:
            return [self._advisory("cargo not found")]
        if result.returncode == 0:
            return []
        return self._parse_cargo_output(result.stderr, "clippy")

    def format_check(self, tier: str, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run(["cargo", "fmt", "--check"])
        if result.tool_missing:
            return [self._advisory("cargo fmt not found")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="cargo-fmt", severity=FindingSeverity.WARNING,
            file=".", line=0, message="Format violations found",
            suggested_fix="Run: cargo fmt",
        )]

    def typecheck(self, tier: str, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run(["cargo", "check", "--message-format=short"])
        if result.tool_missing:
            return [self._advisory("cargo not found")]
        if result.returncode == 0:
            return []
        return self._parse_cargo_output(result.stderr, "cargo-check")

    def test(self, tier: str, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run(["cargo", "test"])
        if result.tool_missing:
            return [self._advisory("cargo not found")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="cargo-test", severity=FindingSeverity.ERROR,
            file=".", line=0, message="Test failures detected",
            raw_tool_output=result.stdout[-2048:],
            blocking=True,
        )]

    def build(self, tier: str) -> list[CheckFinding]:
        result = self._runner.run(["cargo", "build"])
        if result.tool_missing:
            return [self._advisory("cargo not found")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="cargo-build", severity=FindingSeverity.ERROR,
            file=".", line=0, message="Build failed",
            raw_tool_output=result.stderr[-2048:],
            blocking=True,
        )]

    def dependency_check(self, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run(["cargo", "audit"])
        if result.tool_missing:
            return [self._advisory("cargo-audit not installed")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="cargo-audit", severity=FindingSeverity.WARNING,
            file="Cargo.toml", line=0,
            message="Security vulnerabilities found in dependencies",
            raw_tool_output=result.stdout[-2048:],
        )]

    def _advisory(self, message: str) -> CheckFinding:
        return CheckFinding(
            checker="rust-adapter", severity=FindingSeverity.INFO,
            file="", line=0, message=message,
            confidence=Confidence.HIGH, blocking=False,
        )

    def _parse_cargo_output(self, output: str, checker: str) -> list[CheckFinding]:
        findings = []
        for line in output.splitlines():
            m = re.match(r"(?:error|warning)(?:\[(\w+)\])?: (.+)", line)
            if m:
                code = m.group(1) or ""
                msg = m.group(2)
                sev = FindingSeverity.ERROR if line.startswith("error") else FindingSeverity.WARNING
                # Try to extract file:line
                loc_match = re.search(r"--> (.+?):(\d+):(\d+)", output[output.index(line):])
                findings.append(CheckFinding(
                    checker=checker, severity=sev,
                    file=loc_match.group(1) if loc_match else "",
                    line=int(loc_match.group(2)) if loc_match else 0,
                    column=int(loc_match.group(3)) if loc_match else None,
                    code=code, message=msg,
                ))
        return findings
