"""Fettle v0.5.0 — Language adapter registry.

WP-78: Defines the adapter protocol and provides discovery/registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Protocol

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fettle.finding import CheckFinding, EvidenceReference, ResultState
from fettle.paths import FileKind, classify_file
from fettle.trace import build_evidence
from fettle.workspace import Workspace


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
    """Invoke an adapter operation through the workspace-first contract."""
    files = files or []
    method = getattr(adapter, operation)
    if operation in ("build", "dependency_check"):
        return method(workspace)
    elif operation == "test":
        return method(workspace, files, scope)
    return method(workspace, files)


def migrate_adapter(cls):
    """Expose native workspace calls while retaining shipped legacy callers."""
    if not hasattr(cls, "supports"):
        cls.supports = lambda self, workspace: workspace.language in {
            self.language,
            "javascript" if self.language == "typescript" else self.language,
        }
    if not hasattr(cls, "classify"):
        cls.classify = lambda self, path, workspace: classify_file(path)
    for operation in ("lint", "format_check", "typecheck", "test", "build", "dependency_check"):
        legacy = getattr(cls, operation)

        @wraps(legacy)
        def migrated(self, *args, _operation=operation, _legacy=legacy):
            if not args or not isinstance(args[0], Workspace):
                return _legacy(self, *args)

            workspace = args[0]
            native = getattr(self, f"_native_{_operation}", None)
            if _operation == "build":
                scope = "full"
                findings = native(workspace) if native else _legacy(self, scope)
            elif _operation == "dependency_check":
                scope = "full"
                findings = native(workspace) if native else _legacy(self, [])
            elif _operation == "test":
                files = args[1] if len(args) > 1 else []
                scope = args[2] if len(args) > 2 else "full"
                findings = native(workspace, files, scope) if native else _legacy(self, scope, files)
            else:
                files = args[1] if len(args) > 1 else []
                scope = "changed" if files else "full"
                findings = native(workspace, files) if native else _legacy(self, scope, files)

            return _as_check_run(self, workspace, findings, scope)

        setattr(cls, operation, migrated)
    return cls


def _as_check_run(
    adapter: object,
    workspace: Workspace,
    findings: list[CheckFinding],
    scope: str,
) -> CheckRun:
    """Convert one completed legacy operation into the native result contract."""

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
