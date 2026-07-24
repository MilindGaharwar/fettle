#!/usr/bin/env python3
"""Fettle LSP server — WP-125: Publish ruff + semgrep diagnostics over LSP.

A minimal Language Server Protocol implementation over stdin/stdout using only
stdlib. Reuses the existing fettle check infrastructure (ruff + semgrep) and
converts CheckFinding objects to LSP Diagnostic notifications.

Usage:
    python scripts/lsp_server.py
    fettle lsp  (via CLI entry point)

Transport: JSON-RPC 2.0 over Content-Length framed stdio.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from typing import Any

# Allow imports from scripts/ when run standalone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config  # noqa: E402
from _resources import rules_dir  # noqa: E402
from finding import CheckFinding, FindingSeverity  # noqa: E402
from semgrep_util import anchored_semgrep_args  # noqa: E402


# ── LSP constants ────────────────────────────────────────────────────────────

DIAGNOSTIC_SEVERITY_ERROR = 1
DIAGNOSTIC_SEVERITY_WARNING = 2
DIAGNOSTIC_SEVERITY_INFORMATION = 3

SEVERITY_MAP = {
    FindingSeverity.ERROR: DIAGNOSTIC_SEVERITY_ERROR,
    FindingSeverity.WARNING: DIAGNOSTIC_SEVERITY_WARNING,
    FindingSeverity.INFO: DIAGNOSTIC_SEVERITY_INFORMATION,
}


# ── JSON-RPC transport ───────────────────────────────────────────────────────


def encode_message(obj: dict[str, Any]) -> bytes:
    """Encode a JSON-RPC message with Content-Length header."""
    body = json.dumps(obj).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def decode_header(stream) -> int | None:
    """Read Content-Length from headers. Returns body length or None on EOF."""
    content_length = -1
    while True:
        line = stream.readline()
        if not line:
            return None
        line_str = line.decode("ascii").strip()
        if not line_str:
            # Empty line signals end of headers
            break
        if line_str.lower().startswith("content-length:"):
            content_length = int(line_str.split(":", 1)[1].strip())
    if content_length < 0:
        return None
    return content_length


def read_message(stream) -> dict[str, Any] | None:
    """Read one JSON-RPC message from the stream. Returns None on EOF."""
    length = decode_header(stream)
    if length is None:
        return None
    body = stream.read(length)
    if not body or len(body) < length:
        return None
    return json.loads(body.decode("utf-8"))


# ── Check runner (reuses fettle infrastructure) ──────────────────────────────


def _resolve_tool(name: str) -> str | None:
    """Find a tool binary."""
    local = os.path.expanduser(f"~/.local/bin/{name}")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return shutil.which(name)


def run_checks(file_path: str, workspace_root: str) -> list[CheckFinding]:
    """Run ruff + semgrep on a single file. Returns findings list.

    Timeout: 10s per tool. Non-Python files are skipped.
    """
    if not file_path.endswith(".py"):
        return []
    if not os.path.isfile(file_path):
        return []

    cfg = load_config(workspace_root)
    if not cfg["gates"]["lint"]["enabled"]:
        return []

    findings: list[CheckFinding] = []

    # Severity classification from config
    error_rules = set(cfg["severity"]["error_rules"])
    warning_prefixes = tuple(cfg["severity"]["warning_prefixes"])

    def classify_severity(rule: str, source: str, declared: str = "") -> FindingSeverity:
        if rule in error_rules:
            return FindingSeverity.ERROR
        if source == "semgrep" and declared.lower() == "error":
            return FindingSeverity.ERROR
        if any(rule.startswith(p) for p in warning_prefixes):
            return FindingSeverity.WARNING
        return FindingSeverity.INFO

    # ── Ruff ─────────────────────────────────────────────────────────────
    ruff_bin = _resolve_tool("ruff")
    ruff_config = str(cfg["paths"]["ruff_config"]) or str(rules_dir() / ".ruff.toml")
    if ruff_bin:
        try:
            result = subprocess.run(
                [ruff_bin, "check", "--config", ruff_config, "--output-format=json", file_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.stdout.strip():
                raw: list[dict[str, Any]] = json.loads(result.stdout)
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    location = item.get("location", {})
                    row = location.get("row", 0) if isinstance(location, dict) else 0
                    col = location.get("column", 0) if isinstance(location, dict) else 0
                    code = str(item.get("code", ""))
                    findings.append(CheckFinding(
                        checker="ruff",
                        severity=classify_severity(code, "ruff"),
                        file=str(item.get("filename", file_path)),
                        line=row,
                        column=col if col else None,
                        code=code,
                        message=str(item.get("message", "")),
                    ))
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass

    # ── Semgrep ──────────────────────────────────────────────────────────
    semgrep_exclude_dirs = ("/tests/", "/test/", "/__pycache__/")
    if not any(d in file_path for d in semgrep_exclude_dirs):
        semgrep_bin = _resolve_tool("semgrep")
        semgrep_rules = str(rules_dir() / "llm-antipatterns.yml")
        if semgrep_bin and os.path.isfile(semgrep_rules):
            try:
                anchor_args, anchor_cwd = anchored_semgrep_args(file_path, cwd=workspace_root)
                result = subprocess.run(
                    [semgrep_bin, "--config", semgrep_rules, "--json", *anchor_args],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=anchor_cwd,
                )
                if result.stdout.strip():
                    raw_semgrep: dict[str, Any] = json.loads(result.stdout)
                    results_list = raw_semgrep.get("results", [])
                    if isinstance(results_list, list):
                        for item in results_list:
                            if not isinstance(item, dict):
                                continue
                            start_loc = item.get("start", {})
                            line_no = start_loc.get("line", 0) if isinstance(start_loc, dict) else 0
                            col_no = start_loc.get("col", 0) if isinstance(start_loc, dict) else 0
                            extra = item.get("extra", {})
                            msg = extra.get("message", "") if isinstance(extra, dict) else ""
                            declared_severity = extra.get("severity", "") if isinstance(extra, dict) else ""
                            check_id = str(item.get("check_id", ""))
                            findings.append(CheckFinding(
                                checker="semgrep",
                                severity=classify_severity(check_id, "semgrep", str(declared_severity)),
                                file=str(item.get("path", file_path)),
                                line=line_no,
                                column=col_no if col_no else None,
                                code=check_id,
                                message=str(msg),
                            ))
            except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
                pass

    return findings


# ── Diagnostic conversion ────────────────────────────────────────────────────


def finding_to_diagnostic(f: CheckFinding) -> dict[str, Any]:
    """Convert a CheckFinding to an LSP Diagnostic object."""
    line = max(0, f.line - 1)  # LSP lines are 0-based
    col = max(0, (f.column or 1) - 1)  # LSP columns are 0-based
    return {
        "range": {
            "start": {"line": line, "character": col},
            "end": {"line": line, "character": 999},
        },
        "severity": SEVERITY_MAP.get(f.severity, DIAGNOSTIC_SEVERITY_INFORMATION),
        "code": f.code or f.checker,
        "source": "fettle",
        "message": f.message,
    }


def findings_to_diagnostics(findings: list[CheckFinding]) -> list[dict[str, Any]]:
    """Convert a list of findings to LSP Diagnostic objects."""
    return [finding_to_diagnostic(f) for f in findings]


# ── LSP Server ───────────────────────────────────────────────────────────────


class FettleLSPServer:
    """Minimal LSP server for fettle quality diagnostics."""

    def __init__(self, reader=None, writer=None):
        self._reader = reader or sys.stdin.buffer
        self._writer = writer or sys.stdout.buffer
        self._running = True
        self._workspace_root: str = os.getcwd()
        self._lock = threading.Lock()

    def _send(self, msg: dict[str, Any]) -> None:
        """Send a JSON-RPC message."""
        data = encode_message(msg)
        with self._lock:
            self._writer.write(data)
            self._writer.flush()

    def _respond(self, req_id: int | str, result: Any) -> None:
        """Send a JSON-RPC response."""
        self._send({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _respond_error(self, req_id: int | str | None, code: int, message: str) -> None:
        """Send a JSON-RPC error response."""
        self._send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        })

    def _notify(self, method: str, params: Any) -> None:
        """Send a JSON-RPC notification (no id)."""
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _publish_diagnostics(self, uri: str, diagnostics: list[dict[str, Any]]) -> None:
        """Publish diagnostics for a document."""
        self._notify("textDocument/publishDiagnostics", {
            "uri": uri,
            "diagnostics": diagnostics,
        })

    def _uri_to_path(self, uri: str) -> str:
        """Convert a file:// URI to a filesystem path."""
        if uri.startswith("file://"):
            # Handle file:///path/to/file
            path = uri[7:]
            # On Windows, file:///C:/path -> C:/path
            if len(path) > 2 and path[0] == "/" and path[2] == ":":
                path = path[1:]
        else:
            path = uri
        # Decode percent-encoded characters
        import urllib.parse
        return urllib.parse.unquote(path)

    def _path_to_uri(self, path: str) -> str:
        """Convert a filesystem path to a file:// URI."""
        import urllib.parse
        abs_path = os.path.abspath(path)
        return "file://" + urllib.parse.quote(abs_path, safe="/:")

    def _run_checks_for_uri(self, uri: str) -> None:
        """Run checks on a file and publish diagnostics."""
        path = self._uri_to_path(uri)
        if not path.endswith(".py"):
            return
        if not os.path.isfile(path):
            return

        findings = run_checks(path, self._workspace_root)
        diagnostics = findings_to_diagnostics(findings)
        self._publish_diagnostics(uri, diagnostics)

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request."""
        # Extract workspace root from rootUri or rootPath
        root_uri = params.get("rootUri", "")
        if root_uri:
            self._workspace_root = self._uri_to_path(root_uri)
        elif params.get("rootPath"):
            self._workspace_root = params["rootPath"]

        return {
            "capabilities": {
                "textDocumentSync": {
                    "openClose": True,
                    "save": {"includeText": False},
                    "change": 0,  # None — we don't need incremental changes
                },
            },
            "serverInfo": {
                "name": "fettle",
                "version": "1.0.1",
            },
        }

    def _handle_shutdown(self) -> None:
        """Handle shutdown request."""
        self._running = False

    def _dispatch(self, msg: dict[str, Any]) -> None:
        """Dispatch a JSON-RPC message."""
        method = msg.get("method", "")
        params = msg.get("params", {})
        req_id = msg.get("id")  # None for notifications

        if method == "initialize":
            result = self._handle_initialize(params)
            self._respond(req_id, result)

        elif method == "initialized":
            # Notification — no response needed
            pass

        elif method == "shutdown":
            self._handle_shutdown()
            self._respond(req_id, None)

        elif method == "exit":
            self._running = False

        elif method in ("textDocument/didOpen", "textDocument/didSave"):
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            if uri:
                self._run_checks_for_uri(uri)

        elif method == "textDocument/didClose":
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            if uri:
                # Clear diagnostics for closed file
                self._publish_diagnostics(uri, [])

        elif req_id is not None:
            # Unknown request — respond with MethodNotFound
            self._respond_error(req_id, -32601, f"Method not found: {method}")

    def serve(self) -> None:
        """Main server loop — read messages and dispatch."""
        while self._running:
            msg = read_message(self._reader)
            if msg is None:
                break
            self._dispatch(msg)


def main() -> None:
    """Entry point for the LSP server."""
    server = FettleLSPServer()
    server.serve()


if __name__ == "__main__":
    main()
