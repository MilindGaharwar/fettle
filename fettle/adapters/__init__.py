"""Fettle v0.5.0 — Language adapter registry.

WP-78: Defines the adapter protocol and provides discovery/registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fettle.finding import CheckFinding, EvidenceReference, ResultState
from fettle.trace import build_evidence
from fettle.workspace import Workspace


FileKind = Literal["implementation", "test", "generated", "config", "dependency", "unknown"]


@dataclass
class CheckRun:
    """Explicit outcome from one adapter operation."""

    result_state: ResultState
    findings: list[CheckFinding] = field(default_factory=list)
    evidence: list[EvidenceReference] = field(default_factory=list)
    scope: str = ""
    tool_error: str = ""


class LanguageAdapter(Protocol):
    """Protocol that all language adapters must implement."""

    language: str
    extensions: frozenset[str]

    def supports(self, workspace: Workspace) -> bool: ...
    def classify(self, path: str, workspace: Workspace) -> FileKind: ...
    def lint(self, workspace: Workspace, files: list[str]) -> CheckRun: ...
    def format_check(self, workspace: Workspace, files: list[str]) -> CheckRun: ...
    def typecheck(self, workspace: Workspace, files: list[str]) -> CheckRun: ...
    def test(self, workspace: Workspace, files: list[str], scope: str) -> CheckRun: ...
    def build(self, workspace: Workspace) -> CheckRun: ...
    def dependency_check(self, workspace: Workspace) -> CheckRun: ...


def run_adapter_check(
    adapter: object,
    operation: str,
    workspace: Workspace,
    files: list[str] | None = None,
    *,
    scope: str = "full",
) -> CheckRun:
    """Bridge legacy adapters to the explicit CheckRun contract during migration."""
    files = files or []
    method = getattr(adapter, operation)
    if operation == "build":
        findings = method(scope)
    elif operation == "dependency_check":
        findings = method(files)
    else:
        findings = method(scope, files)

    runner = getattr(adapter, "_runner", None)
    last_result = getattr(runner, "last_result", None)
    command = getattr(runner, "last_command", [])
    evidence_data = build_evidence(
        "command", command=command, exit_code=getattr(last_result, "returncode", None),
        scope=scope, workspace=workspace.path,
    )
    evidence = [EvidenceReference(evidence_data["evidence_id"], "command")]
    if last_result is not None and (last_result.tool_missing or last_result.timed_out):
        error = "tool not found" if last_result.tool_missing else "tool timed out"
        return CheckRun(ResultState.TOOL_ERROR, findings, evidence, scope, error)
    if findings and all(
        finding.checker.endswith("-adapter")
        and ("not found" in finding.message.lower() or "not available" in finding.message.lower())
        for finding in findings
    ):
        return CheckRun(ResultState.TOOL_ERROR, findings, evidence, scope, findings[0].message)
    state = ResultState.VIOLATION if findings else ResultState.PASS
    return CheckRun(state, findings, evidence, scope)


_REGISTRY: list[LanguageAdapter] = []


def register_adapter(adapter: LanguageAdapter) -> None:
    """Register a language adapter."""
    _REGISTRY.append(adapter)


def list_adapters() -> list[LanguageAdapter]:
    """Return all registered adapters."""
    _ensure_loaded()
    return list(_REGISTRY)


def get_adapter(language: str) -> LanguageAdapter | None:
    """Get adapter by language name."""
    _ensure_loaded()
    for a in _REGISTRY:
        if a.language == language:
            return a
    return None


_loaded = False


def _ensure_loaded():
    global _loaded
    if _loaded:
        return
    _loaded = True
    from fettle.adapters.python_adapter import PythonAdapter
    from fettle.adapters.typescript_adapter import TypeScriptAdapter
    from fettle.adapters.rust_adapter import RustAdapter
    from fettle.adapters.go_adapter import GoAdapter
    if not any(a.language == "python" for a in _REGISTRY):
        register_adapter(PythonAdapter())
    if not any(a.language == "typescript" for a in _REGISTRY):
        register_adapter(TypeScriptAdapter())
    if not any(a.language == "rust" for a in _REGISTRY):
        register_adapter(RustAdapter())
    if not any(a.language == "go" for a in _REGISTRY):
        register_adapter(GoAdapter())
