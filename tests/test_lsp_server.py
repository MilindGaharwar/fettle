"""Tests for scripts/lsp_server.py — WP-125: LSP server for editor diagnostics."""

import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from fettle import lsp_server
from fettle.finding import CheckFinding, FindingSeverity
from fettle.lsp_server import (
    FettleLSPServer,
    decode_header,
    encode_message,
    finding_to_diagnostic,
    findings_to_diagnostics,
    read_message,
    run_checks,
)


# ── JSON-RPC message framing tests ──────────────────────────────────────────


class TestMessageFraming:
    """Test JSON-RPC encode/decode over Content-Length transport."""

    def test_encode_message_produces_valid_frame(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        encoded = encode_message(msg)
        # Should start with Content-Length header
        assert encoded.startswith(b"Content-Length: ")
        # Should have \r\n\r\n separator
        assert b"\r\n\r\n" in encoded
        # Body should be valid JSON
        header, body = encoded.split(b"\r\n\r\n", 1)
        parsed = json.loads(body)
        assert parsed == msg

    def test_encode_message_length_matches_body(self):
        msg = {"jsonrpc": "2.0", "method": "test", "params": {"key": "value"}}
        encoded = encode_message(msg)
        header, body = encoded.split(b"\r\n\r\n", 1)
        declared_length = int(header.decode("ascii").split(":")[1].strip())
        assert declared_length == len(body)

    def test_decode_header_reads_content_length(self):
        stream = io.BytesIO(b"Content-Length: 42\r\n\r\n")
        length = decode_header(stream)
        assert length == 42

    def test_decode_header_returns_none_on_eof(self):
        stream = io.BytesIO(b"")
        length = decode_header(stream)
        assert length is None

    def test_decode_header_case_insensitive(self):
        stream = io.BytesIO(b"content-length: 100\r\n\r\n")
        length = decode_header(stream)
        assert length == 100

    def test_read_message_roundtrip(self):
        original = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        encoded = encode_message(original)
        stream = io.BytesIO(encoded)
        decoded = read_message(stream)
        assert decoded == original

    def test_read_message_returns_none_on_empty_stream(self):
        stream = io.BytesIO(b"")
        result = read_message(stream)
        assert result is None

    def test_multiple_messages_in_sequence(self):
        msg1 = {"jsonrpc": "2.0", "id": 1, "method": "foo"}
        msg2 = {"jsonrpc": "2.0", "id": 2, "method": "bar"}
        data = encode_message(msg1) + encode_message(msg2)
        stream = io.BytesIO(data)
        assert read_message(stream) == msg1
        assert read_message(stream) == msg2

    def test_unicode_content(self):
        msg = {"jsonrpc": "2.0", "method": "test", "params": {"text": "hello ☃"}}
        encoded = encode_message(msg)
        stream = io.BytesIO(encoded)
        decoded = read_message(stream)
        assert decoded["params"]["text"] == "hello ☃"


# ── Diagnostic generation tests ──────────────────────────────────────────────


class TestDiagnosticConversion:
    """Test converting CheckFinding objects to LSP Diagnostics."""

    def test_error_severity_maps_to_1(self):
        f = CheckFinding(
            checker="ruff", severity=FindingSeverity.ERROR,
            file="x.py", line=10, message="bad code", code="BLE001",
        )
        diag = finding_to_diagnostic(f)
        assert diag["severity"] == 1

    def test_warning_severity_maps_to_2(self):
        f = CheckFinding(
            checker="ruff", severity=FindingSeverity.WARNING,
            file="x.py", line=5, message="could be better", code="SIM101",
        )
        diag = finding_to_diagnostic(f)
        assert diag["severity"] == 2

    def test_info_severity_maps_to_3(self):
        f = CheckFinding(
            checker="ruff", severity=FindingSeverity.INFO,
            file="x.py", line=1, message="style note", code="E501",
        )
        diag = finding_to_diagnostic(f)
        assert diag["severity"] == 3

    def test_line_is_zero_based(self):
        f = CheckFinding(
            checker="ruff", severity=FindingSeverity.ERROR,
            file="x.py", line=10, message="msg", code="X001",
        )
        diag = finding_to_diagnostic(f)
        assert diag["range"]["start"]["line"] == 9  # 0-based

    def test_line_zero_stays_zero(self):
        f = CheckFinding(
            checker="ruff", severity=FindingSeverity.ERROR,
            file="x.py", line=0, message="msg", code="X001",
        )
        diag = finding_to_diagnostic(f)
        assert diag["range"]["start"]["line"] == 0

    def test_column_is_zero_based(self):
        f = CheckFinding(
            checker="ruff", severity=FindingSeverity.ERROR,
            file="x.py", line=1, column=5, message="msg", code="X001",
        )
        diag = finding_to_diagnostic(f)
        assert diag["range"]["start"]["character"] == 4  # 0-based

    def test_diagnostic_has_source_fettle(self):
        f = CheckFinding(
            checker="semgrep", severity=FindingSeverity.WARNING,
            file="x.py", line=1, message="msg", code="rule-id",
        )
        diag = finding_to_diagnostic(f)
        assert diag["source"] == "fettle"

    def test_diagnostic_code_from_finding(self):
        f = CheckFinding(
            checker="ruff", severity=FindingSeverity.ERROR,
            file="x.py", line=1, message="msg", code="BLE001",
        )
        diag = finding_to_diagnostic(f)
        assert diag["code"] == "BLE001"

    def test_diagnostic_code_falls_back_to_checker(self):
        f = CheckFinding(
            checker="ruff", severity=FindingSeverity.ERROR,
            file="x.py", line=1, message="msg",
        )
        diag = finding_to_diagnostic(f)
        assert diag["code"] == "ruff"

    def test_diagnostic_range_end_line_equals_start(self):
        f = CheckFinding(
            checker="ruff", severity=FindingSeverity.ERROR,
            file="x.py", line=7, message="msg", code="X",
        )
        diag = finding_to_diagnostic(f)
        assert diag["range"]["end"]["line"] == diag["range"]["start"]["line"]

    def test_findings_to_diagnostics_batch(self):
        findings = [
            CheckFinding(checker="ruff", severity=FindingSeverity.ERROR,
                         file="x.py", line=1, message="a", code="A"),
            CheckFinding(checker="semgrep", severity=FindingSeverity.WARNING,
                         file="x.py", line=2, message="b", code="B"),
        ]
        diags = findings_to_diagnostics(findings)
        assert len(diags) == 2
        assert diags[0]["code"] == "A"
        assert diags[1]["code"] == "B"

    def test_empty_findings_produces_empty_diagnostics(self):
        assert findings_to_diagnostics([]) == []

    def test_semgrep_declared_error_is_editor_error(self, tmp_path, monkeypatch):
        target = tmp_path / "app.py"
        target.write_text("pass\n")
        monkeypatch.setattr(lsp_server, "_resolve_tool", lambda name: "semgrep" if name == "semgrep" else None)
        monkeypatch.setattr(
            lsp_server.subprocess,
            "run",
            lambda *args, **kwargs: type("Result", (), {
                "stdout": json.dumps({"results": [{
                    "check_id": "sql-fstring",
                    "path": str(target),
                    "start": {"line": 1, "col": 1},
                    "extra": {"message": "unsafe SQL", "severity": "ERROR"},
                }]}),
            })(),
        )

        findings = run_checks(str(target), str(tmp_path))

        assert findings[0].severity == FindingSeverity.ERROR


# ── Initialize/shutdown lifecycle tests ──────────────────────────────────────


class TestServerLifecycle:
    """Test the LSP server initialize/shutdown/exit lifecycle."""

    def _make_server(self, messages: list[dict]) -> tuple[FettleLSPServer, io.BytesIO]:
        """Create a server with pre-loaded input messages and capture output."""
        input_data = b""
        for msg in messages:
            input_data += encode_message(msg)
        reader = io.BytesIO(input_data)
        writer = io.BytesIO()
        server = FettleLSPServer(reader=reader, writer=writer)
        return server, writer

    def _read_responses(self, writer: io.BytesIO) -> list[dict]:
        """Read all responses from the output buffer."""
        writer.seek(0)
        responses = []
        while True:
            msg = read_message(writer)
            if msg is None:
                break
            responses.append(msg)
        return responses

    def test_initialize_returns_capabilities(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "rootUri": "file:///tmp/project",
                "capabilities": {},
            }},
            {"jsonrpc": "2.0", "method": "initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
            {"jsonrpc": "2.0", "method": "exit", "params": {}},
        ]
        server, writer = self._make_server(messages)
        server.serve()

        responses = self._read_responses(writer)
        # First response is to initialize
        init_resp = responses[0]
        assert init_resp["id"] == 1
        assert "capabilities" in init_resp["result"]
        caps = init_resp["result"]["capabilities"]
        assert "textDocumentSync" in caps

    def test_initialize_extracts_workspace_root(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "rootUri": "file:///home/user/project",
                "capabilities": {},
            }},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
            {"jsonrpc": "2.0", "method": "exit", "params": {}},
        ]
        server, writer = self._make_server(messages)
        server.serve()
        assert server._workspace_root == "/home/user/project"

    def test_shutdown_responds_with_null(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
            {"jsonrpc": "2.0", "method": "exit", "params": {}},
        ]
        server, writer = self._make_server(messages)
        server.serve()

        responses = self._read_responses(writer)
        shutdown_resp = responses[1]
        assert shutdown_resp["id"] == 2
        assert shutdown_resp["result"] is None

    def test_exit_terminates_loop(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "exit", "params": {}},
        ]
        server, writer = self._make_server(messages)
        server.serve()  # Should not hang
        assert not server._running

    def test_unknown_method_returns_error(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 99, "method": "unknown/method", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
            {"jsonrpc": "2.0", "method": "exit", "params": {}},
        ]
        server, writer = self._make_server(messages)
        server.serve()

        responses = self._read_responses(writer)
        error_resp = next(r for r in responses if r.get("id") == 99)
        assert "error" in error_resp
        assert error_resp["error"]["code"] == -32601

    def test_did_close_publishes_empty_diagnostics(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "textDocument/didClose", "params": {
                "textDocument": {"uri": "file:///tmp/foo.py"},
            }},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
            {"jsonrpc": "2.0", "method": "exit", "params": {}},
        ]
        server, writer = self._make_server(messages)
        server.serve()

        responses = self._read_responses(writer)
        # Find the publishDiagnostics notification
        diag_notif = next(
            (r for r in responses if r.get("method") == "textDocument/publishDiagnostics"),
            None,
        )
        assert diag_notif is not None
        assert diag_notif["params"]["uri"] == "file:///tmp/foo.py"
        assert diag_notif["params"]["diagnostics"] == []

    def test_server_info_in_initialize_response(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
            {"jsonrpc": "2.0", "method": "exit", "params": {}},
        ]
        server, writer = self._make_server(messages)
        server.serve()

        responses = self._read_responses(writer)
        init_resp = responses[0]
        assert init_resp["result"]["serverInfo"]["name"] == "fettle"
