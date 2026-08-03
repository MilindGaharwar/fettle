"""Tests for fettle.cross_review — LLM-backed code review utility."""

import json
from unittest.mock import patch

from fettle.cross_review import _call_llm, _endpoint_allowed, _read_files


class TestReadFiles:
    def test_reads_existing_files(self, tmp_path):
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("def hello(): pass")
        b.write_text("x = 1")
        result = _read_files([str(a), str(b)])
        assert "def hello()" in result
        assert "x = 1" in result
        assert "--- " in result

    def test_missing_file_skipped(self, tmp_path, capsys):
        result = _read_files([str(tmp_path / "gone.py")])
        assert result == ""
        captured = capsys.readouterr()
        assert "WARNING" in captured.err


class TestCallLlm:
    def test_no_endpoint_raises_or_returns_none(self, monkeypatch):
        monkeypatch.setattr("fettle.cross_review.REVIEW_ENDPOINT", "")
        try:
            result = _call_llm("model", "prompt", "code")
            assert result is None
        except ValueError:
            pass  # urllib rejects empty URL — acceptable failure mode

    def test_successful_call(self, monkeypatch):
        monkeypatch.setattr("fettle.cross_review.REVIEW_ENDPOINT", "https://api.example.com/v1/chat/completions")
        response_body = json.dumps({
            "choices": [{"message": {"content": "looks good"}}]
        }).encode()

        class FakeResp:
            def read(self):
                return response_body
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        with patch("urllib.request.urlopen", return_value=FakeResp()):
            result = _call_llm("gpt-4", "review this", "def f(): pass")
        assert result == "looks good"

    def test_network_error_returns_none(self, monkeypatch, capsys):
        import urllib.error
        monkeypatch.setattr("fettle.cross_review.REVIEW_ENDPOINT", "https://api.example.com/v1/chat/completions")

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            result = _call_llm("model", "prompt", "code")
        assert result is None
        assert "ERROR" in capsys.readouterr().err


class TestEndpointValidation:
    # WP-12 (audit M-05): code must never travel cleartext to a remote host.
    def test_https_allowed(self):
        assert _endpoint_allowed("https://api.example.com/v1")

    def test_loopback_http_allowed(self):
        assert _endpoint_allowed("http://127.0.0.1:8080/v1")
        assert _endpoint_allowed("http://localhost:11434/v1")

    def test_remote_http_rejected(self):
        assert not _endpoint_allowed("http://api.example.com/v1")

    def test_loopback_prefix_spoof_rejected(self):
        assert not _endpoint_allowed("http://127.0.0.1.evil.example/v1")
        assert not _endpoint_allowed("http://localhost.evil.example/v1")

    def test_garbage_rejected(self):
        assert not _endpoint_allowed("ftp://example.com")
        assert not _endpoint_allowed("not a url")

    def test_main_exits_2_on_bad_endpoint(self, monkeypatch, capsys):
        from fettle import cross_review
        monkeypatch.setattr(cross_review, "REVIEW_ENDPOINT", "http://api.example.com/v1")
        assert cross_review.main() == 2
        assert "https" in capsys.readouterr().err
