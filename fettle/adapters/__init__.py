"""Fettle v0.5.0 — Language adapter registry.

WP-78: Defines the adapter protocol and provides discovery/registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import subprocess
from typing import Protocol

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fettle._resources import rules_dir
from fettle.finding import (
    CheckFinding,
    Confidence,
    EvidenceReference,
    FindingSeverity,
    ResultState,
)
from fettle.paths import FileKind
from fettle.project_rules import extra_rule_configs
from fettle.semgrep_util import anchored_semgrep_args
from fettle.tool_paths import resolve_tool
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


def semgrep_findings(
    files: list[str],
    *,
    cwd: str,
    config: dict,
    rule_pack: str,
) -> list[CheckFinding]:
    """Run one bundled rule pack and project rules for changed files."""
    if not files:
        return []
    semgrep = _resolve_tool("semgrep")
    rules_file = rules_dir() / rule_pack
    if semgrep is None:
        return [_adapter_error("semgrep not found")]
    if not rules_file.is_file():
        return [_adapter_error(f"semgrep rules not available: {rule_pack}")]

    findings: list[CheckFinding] = []
    for file_path in files:
        anchor_args, anchor_cwd = anchored_semgrep_args(file_path, cwd=cwd)
        config_args = ["--config", str(rules_file)]
        for extra in extra_rule_configs(config, anchor_cwd):
            config_args.extend(["--config", extra])
        try:
            proc = subprocess.run(
                [semgrep, *config_args, "--json", *anchor_args],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=anchor_cwd,
            )
            if not proc.stdout.strip():
                findings.append(_adapter_error("semgrep not available: empty output"))
                continue
            raw = json.loads(proc.stdout)
        except subprocess.TimeoutExpired:
            findings.append(_adapter_error("semgrep not available: timed out"))
            continue
        except (json.JSONDecodeError, OSError) as error:
            findings.append(_adapter_error(f"semgrep not available: {error}"))
            continue
        if not isinstance(raw, dict):
            findings.append(_adapter_error("semgrep not available: malformed output"))
            continue
        errors = raw.get("errors", [])
        if errors:
            first = errors[0] if isinstance(errors, list) else errors
            message = first.get("message", first) if isinstance(first, dict) else first
            findings.append(_adapter_error(f"semgrep not available: {message}"))
            continue
        for item in raw.get("results", []):
            if not isinstance(item, dict):
                continue
            start = item.get("start", {})
            extra = item.get("extra", {})
            severity = str(extra.get("severity", "")) if isinstance(extra, dict) else ""
            findings.append(CheckFinding(
                checker="semgrep",
                severity=(
                    FindingSeverity.ERROR
                    if "error" in severity.lower()
                    else FindingSeverity.WARNING
                ),
                file=str(item.get("path") or file_path),
                line=int(start.get("line", 0)) if isinstance(start, dict) else 0,
                code=str(item.get("check_id", "")),
                message=str(extra.get("message", "")) if isinstance(extra, dict) else "",
                rerun_command=f"semgrep --config {rules_file} {file_path}",
            ))
    return findings


def _resolve_tool(name: str) -> str | None:
    return resolve_tool(name)


def _adapter_error(message: str) -> CheckFinding:
    return CheckFinding(
        checker="semgrep-adapter",
        severity=FindingSeverity.INFO,
        file="",
        line=0,
        message=message,
        confidence=Confidence.HIGH,
        blocking=False,
    )


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


def as_check_run(
    adapter: object,
    workspace: Workspace,
    findings: list[CheckFinding],
    scope: str,
) -> CheckRun:
    """Convert one completed adapter operation into the canonical result contract."""

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
    errors = [
        finding for finding in findings
        if finding.checker.endswith("-adapter")
        and any(
            phrase in finding.message.lower()
            for phrase in ("not found", "not available", "timed out", "malformed", "empty output")
        )
    ]
    if errors:
        return CheckRun(ResultState.TOOL_ERROR, findings, evidence, scope, errors[0].message)
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
