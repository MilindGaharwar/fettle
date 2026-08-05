"""Fettle v0.5.0 — WP-94: TypeScript/JavaScript language adapter.

Wraps eslint/biome (lint), prettier/biome (format), tsc (typecheck),
vitest/jest (test), knip (deps), npm/pnpm ci (build).
"""

from __future__ import annotations

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fettle.finding import CheckFinding, FindingSeverity, Confidence
from fettle.profile import Profile
from fettle.tool_runner import ToolRunner
from fettle.adapters import migrate_adapter
from fettle.workspace import Workspace


@migrate_adapter
class TypeScriptAdapter:
    """TypeScript/JavaScript language adapter."""

    language = "typescript"

    def __init__(self, cwd: str | None = None):
        self._cwd = cwd or os.getcwd()
        self._runner = ToolRunner(timeout_s=60, cwd=self._cwd)

    def detect(self, profile: Profile) -> bool:
        return "typescript" in profile.languages or "javascript" in profile.languages

    def lint(self, tier: str, files: list[str]) -> list[CheckFinding]:
        # Try biome first, fall back to eslint
        result = self._runner.run(["biome", "check", "--reporter=json", *files])
        if not result.tool_missing:
            return self._parse_biome(result.stdout) if result.returncode != 0 else []

        args = ["eslint", "--format=json", *files] if files else ["eslint", "--format=json", "."]
        result = self._runner.run(args)
        if result.tool_missing:
            return [self._advisory("Neither biome nor eslint found")]
        if result.returncode == 0:
            return []
        return self._parse_eslint_json(result.stdout)

    def format_check(self, tier: str, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run(["biome", "format", "--check", *files])
        if not result.tool_missing:
            if result.returncode == 0:
                return []
            return [CheckFinding(
                checker="biome-format", severity=FindingSeverity.WARNING,
                file=files[0] if files else ".", line=0,
                message="Format violations found",
                suggested_fix="Run: biome format --write",
            )]

        result = self._runner.run(["prettier", "--check", *(files or ["."])])
        if result.tool_missing:
            return [self._advisory("Neither biome nor prettier found")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="prettier", severity=FindingSeverity.WARNING,
            file=files[0] if files else ".", line=0,
            message="Format violations found",
            suggested_fix="Run: prettier --write .",
        )]

    def typecheck(self, tier: str, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run(["tsc", "--noEmit"])
        if result.tool_missing:
            return [self._advisory("tsc not found")]
        if result.returncode == 0:
            return []
        return self._parse_tsc(result.stdout)

    def test(self, tier: str, files: list[str]) -> list[CheckFinding]:
        # Try vitest first, then jest
        result = self._runner.run(["vitest", "run", "--reporter=json", *files])
        if result.tool_missing:
            result = self._runner.run(["jest", "--json", *files])
        if result.tool_missing:
            return [self._advisory("Neither vitest nor jest found")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="test-js", severity=FindingSeverity.ERROR,
            file=files[0] if files else ".", line=0,
            message="Test failures detected",
            raw_tool_output=result.stdout[-2048:],
            blocking=True,
        )]

    def build(self, tier: str) -> list[CheckFinding]:
        # Detect package manager
        for cmd in ("pnpm", "npm", "yarn"):
            result = self._runner.run([cmd, "ci"])
            if not result.tool_missing:
                if result.returncode == 0:
                    return []
                return [CheckFinding(
                    checker=f"{cmd}-ci", severity=FindingSeverity.ERROR,
                    file="package.json", line=0,
                    message=f"{cmd} ci failed",
                    raw_tool_output=result.stderr[-2048:],
                    blocking=True,
                )]
        return [self._advisory("No package manager found")]

    def dependency_check(self, files: list[str]) -> list[CheckFinding]:
        result = self._runner.run(["knip", "--reporter=json"])
        if result.tool_missing:
            return [self._advisory("knip not found — install with: npm install -D knip")]
        if result.returncode == 0:
            return []
        return [CheckFinding(
            checker="knip", severity=FindingSeverity.WARNING,
            file="package.json", line=0,
            message="Unused dependencies or exports detected",
            raw_tool_output=result.stdout[-2048:],
        )]

    def _native_lint(self, workspace: Workspace, files: list[str]) -> list[CheckFinding]:
        if self._has_script("lint"):
            result = self._runner.run([workspace.manager or "npm", "run", "lint", *(["--", *files] if files else [])])
            if result.returncode == 0:
                return []
            parsed = self._parse_eslint_json(result.stdout + result.stderr)
            return parsed or [self._command_failure("lint", files, result)]

        result = self._runner.run([*self._exec_prefix(workspace), "biome", "check", "--reporter=json", *files])
        if not result.tool_missing:
            if result.returncode == 0:
                return []
            parsed = self._parse_biome(result.stdout + result.stderr)
            return parsed or [self._command_failure("biome", files, result)]
        result = self._runner.run([*self._exec_prefix(workspace), "eslint", "--format=json", *(files or ["."])])
        if result.tool_missing:
            return [self._advisory("Neither biome nor eslint found in the workspace")]
        if result.returncode == 0:
            return []
        parsed = self._parse_eslint_json(result.stdout + result.stderr)
        return parsed or [self._command_failure("eslint", files, result)]

    def _native_format_check(self, workspace: Workspace, files: list[str]) -> list[CheckFinding]:
        if self._has_script("format"):
            result = self._runner.run([workspace.manager or "npm", "run", "format", "--", "--check", *files])
            return [] if result.returncode == 0 else [self._command_failure("format", files, result)]
        result = self._runner.run([*self._exec_prefix(workspace), "biome", "format", "--check", *files])
        if result.tool_missing:
            result = self._runner.run([*self._exec_prefix(workspace), "prettier", "--check", *(files or ["."])])
        if result.tool_missing:
            return [self._advisory("Neither biome nor prettier found in the workspace")]
        return [] if result.returncode == 0 else [self._command_failure("format", files, result)]

    def _native_typecheck(self, workspace: Workspace, files: list[str]) -> list[CheckFinding]:
        if self._has_script("typecheck"):
            result = self._runner.run([workspace.manager or "npm", "run", "typecheck"])
        else:
            result = self._runner.run([*self._exec_prefix(workspace), "tsc", "--noEmit"])
        if result.tool_missing:
            return [self._advisory("tsc not found in the workspace")]
        if result.returncode == 0:
            return []
        parsed = self._parse_tsc(result.stdout + result.stderr)
        return parsed or [self._command_failure("tsc", files, result, blocking=True)]

    def _native_test(self, workspace: Workspace, files: list[str], scope: str) -> list[CheckFinding]:
        if self._has_script("test"):
            args = [workspace.manager or "npm", "test", *(["--", *files] if files else [])]
            result = self._runner.run(args)
        else:
            result = self._runner.run([*self._exec_prefix(workspace), "vitest", "run", "--reporter=json", *files])
            if result.tool_missing:
                result = self._runner.run([*self._exec_prefix(workspace), "jest", "--json", *files])
        if result.tool_missing:
            return [self._advisory("Neither a test script, vitest, nor jest was found")]
        return [] if result.returncode == 0 else [self._command_failure("test", files, result, blocking=True)]

    def _native_build(self, workspace: Workspace) -> list[CheckFinding]:
        manager = workspace.manager or "npm"
        if self._has_script("build"):
            result = self._runner.run([manager, "run", "build"])
        else:
            return [self._advisory("No repository build script found")]
        if result.tool_missing:
            return [self._advisory(f"Package manager not found: {manager}")]
        return [] if result.returncode == 0 else [self._command_failure("build", ["package.json"], result, blocking=True)]

    def _native_dependency_check(self, workspace: Workspace) -> list[CheckFinding]:
        result = self._runner.run([*self._exec_prefix(workspace), "knip", "--reporter=json"])
        if result.tool_missing:
            return [self._advisory("knip not found in the workspace")]
        return [] if result.returncode == 0 else [self._command_failure("knip", ["package.json"], result)]

    def _package_data(self) -> dict:
        try:
            from pathlib import Path

            data = json.loads((Path(self._cwd) / "package.json").read_text())
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _has_script(self, name: str) -> bool:
        scripts = self._package_data().get("scripts", {})
        return isinstance(scripts, dict) and isinstance(scripts.get(name), str)

    @staticmethod
    def _exec_prefix(workspace: Workspace) -> list[str]:
        manager = workspace.manager or "npm"
        return {
            "npm": ["npm", "exec", "--"],
            "pnpm": ["pnpm", "exec"],
            "yarn": ["yarn", "exec"],
            "bun": ["bunx"],
        }.get(manager, [manager, "exec"])

    @staticmethod
    def _command_failure(
        checker: str,
        files: list[str],
        result,
        *,
        blocking: bool = False,
    ) -> CheckFinding:
        output = (result.stdout + result.stderr).strip()
        return CheckFinding(
            checker=checker,
            severity=FindingSeverity.ERROR if blocking else FindingSeverity.WARNING,
            file=files[0] if files else ".",
            line=0,
            message=f"{checker} failed",
            raw_tool_output=output[-2048:],
            blocking=blocking,
        )

    def _advisory(self, message: str) -> CheckFinding:
        return CheckFinding(
            checker="typescript-adapter", severity=FindingSeverity.INFO,
            file="", line=0, message=message,
            confidence=Confidence.HIGH, blocking=False,
        )

    def _parse_eslint_json(self, output: str) -> list[CheckFinding]:
        import json
        findings = []
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return []
        for file_result in data:
            for msg in file_result.get("messages", []):
                findings.append(CheckFinding(
                    checker="eslint",
                    severity=FindingSeverity.ERROR if msg.get("severity", 0) >= 2 else FindingSeverity.WARNING,
                    file=file_result.get("filePath", ""),
                    line=msg.get("line", 0),
                    column=msg.get("column"),
                    code=msg.get("ruleId", ""),
                    message=msg.get("message", ""),
                ))
        return findings

    def _parse_biome(self, output: str) -> list[CheckFinding]:
        import json
        findings = []
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return []
        for diag in data.get("diagnostics", []):
            findings.append(CheckFinding(
                checker="biome",
                severity=FindingSeverity.ERROR,
                file=diag.get("file", ""),
                line=diag.get("line", 0),
                message=diag.get("message", ""),
                code=diag.get("rule", ""),
            ))
        return findings

    def _parse_tsc(self, output: str) -> list[CheckFinding]:
        import re
        findings = []
        for line in output.splitlines():
            m = re.match(r"(.+?)\((\d+),(\d+)\): error (TS\d+): (.+)", line)
            if m:
                findings.append(CheckFinding(
                    checker="tsc",
                    severity=FindingSeverity.ERROR,
                    file=m.group(1),
                    line=int(m.group(2)),
                    column=int(m.group(3)),
                    code=m.group(4),
                    message=m.group(5),
                ))
        return findings
