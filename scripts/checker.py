"""Fettle checker protocol — formal interface for tool plugins.

Any checker implements this protocol. Fettle dispatches to registered
checkers based on file type and gate configuration.

Built-in checkers: ruff, semgrep, shellcheck.
Future: mypy, pyright, eslint, bandit, gitleaks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from result import Finding, Severity


@dataclass
class CheckContext:
    """Context passed to every checker."""
    file_path: Path
    repo_root: Path
    config: dict[str, Any]
    session_id: str = ""


@dataclass
class AvailabilityResult:
    available: bool
    version: str = ""
    message: str = ""


class Checker(ABC):
    """Base class for all Fettle checkers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Checker identifier (e.g., 'ruff', 'semgrep', 'eslint')."""
        ...

    @property
    @abstractmethod
    def file_extensions(self) -> set[str]:
        """File extensions this checker handles (e.g., {'.py', '.pyi'})."""
        ...

    @abstractmethod
    def is_available(self) -> AvailabilityResult:
        """Check if the tool is installed and usable."""
        ...

    @abstractmethod
    def check(self, context: CheckContext) -> list[Finding]:
        """Run the checker on a file. Returns findings."""
        ...

    def can_fix(self) -> bool:
        """Whether this checker supports autofix."""
        return False

    def fix(self, context: CheckContext) -> list[Finding]:
        """Apply fixes. Returns remaining unfixed findings."""
        return self.check(context)


class RuffChecker(Checker):
    """Built-in ruff checker."""

    @property
    def name(self) -> str:
        return "ruff"

    @property
    def file_extensions(self) -> set[str]:
        return {".py", ".pyi"}

    def is_available(self) -> AvailabilityResult:
        bin_path = shutil.which("ruff") or os.path.expanduser("~/.local/bin/ruff")
        if os.path.isfile(bin_path) and os.access(bin_path, os.X_OK):
            try:
                result = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=5)
                return AvailabilityResult(True, version=result.stdout.strip())
            except (subprocess.TimeoutExpired, OSError):
                pass
        return AvailabilityResult(False, message="ruff not found on PATH")

    def check(self, context: CheckContext) -> list[Finding]:
        import json as _json
        bin_path = shutil.which("ruff") or os.path.expanduser("~/.local/bin/ruff")
        if not os.path.isfile(bin_path):
            return []

        plugin_root = os.environ.get(
            "CLAUDE_PLUGIN_ROOT",
            str(Path(__file__).parent.parent),
        )
        ruff_config = str(context.config.get("paths", {}).get("ruff_config", "")) or os.path.join(plugin_root, "rules", ".ruff.toml")

        try:
            result = subprocess.run(
                [bin_path, "check", "--config", ruff_config, "--output-format=json", str(context.file_path)],
                capture_output=True, text=True, timeout=10,
            )
            if not result.stdout.strip():
                return []

            findings = []
            for item in _json.loads(result.stdout):
                if not isinstance(item, dict):
                    continue
                location = item.get("location", {})
                row = location.get("row", 0) if isinstance(location, dict) else 0
                code = item.get("code", "")
                error_rules = set(context.config.get("severity", {}).get("error_rules", []))
                warning_prefixes = tuple(context.config.get("severity", {}).get("warning_prefixes", []))

                if code in error_rules:
                    sev = Severity.ERROR
                elif any(code.startswith(p) for p in warning_prefixes):
                    sev = Severity.WARNING
                else:
                    sev = Severity.INFO

                findings.append(Finding(
                    tool="ruff", severity=sev,
                    path=str(context.file_path), line=row,
                    code=code, message=item.get("message", ""),
                    fixable=item.get("fix", {}).get("applicability", "") == "safe",
                ))
            return findings
        except (subprocess.TimeoutExpired, OSError, _json.JSONDecodeError):
            return []

    def can_fix(self) -> bool:
        return True


class SemgrepChecker(Checker):
    """Built-in semgrep checker."""

    @property
    def name(self) -> str:
        return "semgrep"

    @property
    def file_extensions(self) -> set[str]:
        return {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs"}

    def is_available(self) -> AvailabilityResult:
        bin_path = shutil.which("semgrep") or os.path.expanduser("~/.local/bin/semgrep")
        if os.path.isfile(bin_path) and os.access(bin_path, os.X_OK):
            return AvailabilityResult(True)
        return AvailabilityResult(False, message="semgrep not found on PATH")

    def check(self, context: CheckContext) -> list[Finding]:
        import json as _json
        bin_path = shutil.which("semgrep") or os.path.expanduser("~/.local/bin/semgrep")
        if not os.path.isfile(bin_path):
            return []

        plugin_root = os.environ.get(
            "CLAUDE_PLUGIN_ROOT",
            str(Path(__file__).parent.parent),
        )
        rules_file = os.path.join(plugin_root, "rules", "llm-antipatterns.yml")
        if not os.path.isfile(rules_file):
            return []

        try:
            result = subprocess.run(
                [bin_path, "--config", rules_file, "--json", str(context.file_path)],
                capture_output=True, text=True, timeout=15,
            )
            if not result.stdout.strip():
                return []

            findings = []
            raw = _json.loads(result.stdout)
            for item in raw.get("results", []):
                if not isinstance(item, dict):
                    continue
                start_loc = item.get("start", {})
                line_no = start_loc.get("line", 0) if isinstance(start_loc, dict) else 0
                extra = item.get("extra", {})
                msg = extra.get("message", "") if isinstance(extra, dict) else ""
                findings.append(Finding(
                    tool="semgrep", severity=Severity.ERROR,
                    path=str(context.file_path), line=line_no,
                    code=item.get("check_id", ""), message=msg,
                ))
            return findings
        except (subprocess.TimeoutExpired, OSError, _json.JSONDecodeError):
            return []


# Registry of built-in checkers
CHECKERS: dict[str, Checker] = {
    "ruff": RuffChecker(),
    "semgrep": SemgrepChecker(),
}


def get_checkers_for_file(file_path: str) -> list[Checker]:
    """Return checkers applicable to a given file extension."""
    ext = Path(file_path).suffix
    return [c for c in CHECKERS.values() if ext in c.file_extensions]


def register_checker(checker: Checker) -> None:
    """Register a custom checker."""
    CHECKERS[checker.name] = checker
