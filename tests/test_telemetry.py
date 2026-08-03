"""Tests for WP-148: opt-in, privacy-first telemetry."""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import threading
import time

import pytest

from fettle.telemetry import (
    PAYLOAD_SCHEMA,
    compute_payload,
    send_payload,
    telemetry_settings,
)

ORG_POLICY = b"""\
[telemetry]
enabled = true
endpoint = "https://telemetry.example.com/ingest"
"""


def _org_enabled_repo(tmp_path, monkeypatch, policy: bytes = ORG_POLICY):
    """Repo whose digest-pinned cached org policy enables telemetry."""
    sha = hashlib.sha256(policy).hexdigest()
    cache = tmp_path / "policy-cache"
    cache.mkdir()
    (cache / f"{sha}.toml").write_bytes(policy)
    monkeypatch.setenv("FETTLE_POLICY_CACHE_DIR", str(cache))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".fettle.toml").write_text(
        f'[extends]\nurl = "https://example.com/org.toml"\nsha256 = "{sha}"\n'
    )
    return repo


class TestOptIn:
    def test_default_off_no_config(self, tmp_path):
        settings = telemetry_settings(str(tmp_path))
        assert settings["enabled"] is False
        assert settings["source"] == "default"

    def test_repo_enable_is_ignored_and_surfaced(self, tmp_path):
        (tmp_path / ".fettle.toml").write_text(
            '[telemetry]\nenabled = true\nendpoint = "https://evil.example.com"\n'
        )
        settings = telemetry_settings(str(tmp_path))
        assert settings["enabled"] is False
        assert "org" in settings["note"]  # loud, not silent

    def test_org_policy_enables(self, tmp_path, monkeypatch):
        repo = _org_enabled_repo(tmp_path, monkeypatch)
        settings = telemetry_settings(str(repo))
        assert settings["enabled"] is True
        assert settings["source"] == "org-policy"
        assert settings["endpoint"] == "https://telemetry.example.com/ingest"

    def test_org_policy_with_non_https_endpoint_stays_off(self, tmp_path, monkeypatch):
        policy = b'[telemetry]\nenabled = true\nendpoint = "http://plain.example.com"\n'
        repo = _org_enabled_repo(tmp_path, monkeypatch, policy)
        settings = telemetry_settings(str(repo))
        assert settings["enabled"] is False
        assert "https" in settings["note"]

    def test_loopback_prefix_spoof_stays_off(self, tmp_path, monkeypatch):
        # WP-12 (audit M-05): startswith("http://127.0.0.1") passed this host.
        policy = b'[telemetry]\nenabled = true\nendpoint = "http://127.0.0.1.evil.example/i"\n'
        repo = _org_enabled_repo(tmp_path, monkeypatch, policy)
        assert telemetry_settings(str(repo))["enabled"] is False

    def test_real_loopback_http_allowed(self, tmp_path, monkeypatch):
        policy = b'[telemetry]\nenabled = true\nendpoint = "http://127.0.0.1:9999/ingest"\n'
        repo = _org_enabled_repo(tmp_path, monkeypatch, policy)
        assert telemetry_settings(str(repo))["enabled"] is True

    def test_org_policy_without_telemetry_stays_off(self, tmp_path, monkeypatch):
        repo = _org_enabled_repo(tmp_path, monkeypatch, b'[gates.lint]\nmode = "enforce"\n')
        assert telemetry_settings(str(repo))["enabled"] is False


def _fake_entries():
    now = time.time()
    return [
        {"ts": now - 10, "status": "pass", "findings": []},
        {"ts": now - 20, "status": "violation", "findings": [{"code": "sql-fstring"}]},
        {"ts": now - 30, "status": "blocked", "findings": [{"code": "sql-fstring"}]},
        {"ts": now - 40, "status": "tool_error", "findings": []},
        {"ts": now - 50 * 86400, "status": "violation", "findings": [{"code": "old"}]},
    ]


class TestPayload:
    @pytest.fixture(autouse=True)
    def _trace(self, monkeypatch):
        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: _fake_entries()
        )

    def test_counters(self):
        payload = compute_payload(days=30)
        assert payload["counters"] == {
            "decisions": 4,   # old entry filtered out
            "fired": 2,       # entries with findings
            "blocked": 1,
            "overridden": 0,
            "tool_errors": 1,
        }
        assert payload["schema"] == PAYLOAD_SCHEMA
        assert payload["period_days"] == 30

    def test_payload_is_anonymous(self):
        """Pin the full key set: counters + version, nothing identifying."""
        payload = compute_payload(days=30)
        assert set(payload) == {"schema", "period_days", "counters", "fettle_version"}
        assert all(isinstance(v, int) for v in payload["counters"].values())
        serialized = json.dumps(payload)
        assert "sql-fstring" not in serialized  # no rule ids
        assert "/" not in serialized.replace("fettle-telemetry/1", "")  # no paths


class _Ingest(http.server.BaseHTTPRequestHandler):
    received: list[bytes] = []

    def do_POST(self):
        self.received.append(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


class TestSend:
    def test_send_posts_json(self):
        _Ingest.received = []
        server = http.server.HTTPServer(("127.0.0.1", 0), _Ingest)
        threading.Thread(target=server.handle_request, daemon=True).start()
        endpoint = f"http://127.0.0.1:{server.server_port}/ingest"
        payload = {"schema": PAYLOAD_SCHEMA, "counters": {"decisions": 3}}
        assert send_payload(payload, endpoint) is True
        server.server_close()
        assert json.loads(_Ingest.received[0])["counters"]["decisions"] == 3

    def test_send_failure_returns_false_never_raises(self):
        assert send_payload({}, "http://127.0.0.1:1/ingest", timeout=0.5) is False


class TestCLI:
    def test_status_default_off(self, tmp_path, monkeypatch, capsys):
        from fettle.cli import cmd_telemetry

        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_telemetry(argparse.Namespace(telemetry_action="status"))
        assert exc.value.code == 0
        assert "off (default)" in capsys.readouterr().out

    def test_show_prints_payload(self, tmp_path, monkeypatch, capsys):
        from fettle.cli import cmd_telemetry

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: _fake_entries()
        )
        with pytest.raises(SystemExit) as exc:
            cmd_telemetry(argparse.Namespace(telemetry_action="show", days=30))
        assert exc.value.code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["schema"] == PAYLOAD_SCHEMA

    def test_send_refused_when_disabled(self, tmp_path, monkeypatch, capsys):
        from fettle.cli import cmd_telemetry

        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_telemetry(argparse.Namespace(telemetry_action="send", days=30))
        assert exc.value.code == 1
        assert "nothing was sent" in capsys.readouterr().err

    def test_send_when_org_enabled(self, tmp_path, monkeypatch, capsys):
        from fettle.cli import cmd_telemetry

        _Ingest.received = []
        server = http.server.HTTPServer(("127.0.0.1", 0), _Ingest)
        threading.Thread(target=server.handle_request, daemon=True).start()
        endpoint = f"http://127.0.0.1:{server.server_port}/ingest".encode()
        policy = b'[telemetry]\nenabled = true\nendpoint = "' + endpoint + b'"\n'
        repo = _org_enabled_repo(tmp_path, monkeypatch, policy)
        monkeypatch.chdir(repo)
        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: _fake_entries()
        )
        with pytest.raises(SystemExit) as exc:
            cmd_telemetry(argparse.Namespace(telemetry_action="send", days=30))
        assert exc.value.code == 0
        server.server_close()
        assert json.loads(_Ingest.received[0])["counters"]["decisions"] == 4
