"""WP-E — Bash Structured Audit tests."""

import json
from pathlib import Path
from unittest.mock import patch

from fettle.dispatcher_types import Decision, HookContext, HookInput


def _make_ctx(command: str = "ls -la", config_overrides: dict | None = None,
              session_id: str = "test-audit"):
    config = {
        "gates": {
            "bash_audit": {
                "enabled": True,
                "capture_command": False,
                "capture_exit_code": True,
                "capture_duration": True,
                "redaction": {
                    "patterns": [
                        r"(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*\S+",
                        r"(?i)bearer\s+\S+",
                    ],
                    "replacement": "[REDACTED]",
                    "fail_closed": True,
                },
            },
        },
    }
    if config_overrides:
        config["gates"]["bash_audit"].update(config_overrides)

    hook_input = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Bash",
        tool_input={"command": command},
        cwd=Path("/tmp"),
        session_id=session_id,
        raw={"tool_response": {"exit_code": 0, "duration_ms": 150}},
    )
    return HookContext(
        input=hook_input,
        config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


def test_disabled_no_file(tmp_path):
    """When disabled, no audit file is created."""
    from fettle.bash_audit import run_check

    ctx = _make_ctx(config_overrides={"enabled": False})
    with patch("fettle.config.state_dir", return_value=tmp_path / "sess"):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW
    assert not (tmp_path / "sess" / "bash_events.jsonl").exists()


def test_enabled_no_capture_hash_only(tmp_path):
    """Enabled without capture_command: logs hash, no command text."""
    from fettle.bash_audit import run_check

    session_dir = tmp_path / "test-audit"
    session_dir.mkdir(parents=True)

    ctx = _make_ctx(command="echo secret_password=abc123")
    with patch("fettle.config.state_dir", return_value=session_dir):
        result = run_check(ctx)

    assert result.decision == Decision.ALLOW
    events_file = session_dir / "bash_events.jsonl"
    assert events_file.exists()
    record = json.loads(events_file.read_text().strip())
    assert "command_hash" in record
    assert "command" not in record
    assert record["exit_code"] == 0
    assert record["duration_ms"] == 150


def test_capture_with_redaction(tmp_path):
    """With capture_command=true, secrets are redacted."""
    from fettle.bash_audit import run_check

    session_dir = tmp_path / "test-audit-redact"
    session_dir.mkdir(parents=True)

    ctx = _make_ctx(
        command="curl -H 'Authorization: Bearer sk-abc123' https://api.example.com",
        config_overrides={"capture_command": True},
    )
    with patch("fettle.config.state_dir", return_value=session_dir):
        result = run_check(ctx)

    assert result.decision == Decision.ALLOW
    events_file = session_dir / "bash_events.jsonl"
    record = json.loads(events_file.read_text().strip())
    assert "command" in record
    assert "sk-abc123" not in record["command"]
    assert "[REDACTED]" in record["command"]


def test_invalid_regex_fail_closed(tmp_path):
    """Invalid redaction regex: command not written (fail_closed)."""
    from fettle.bash_audit import run_check

    session_dir = tmp_path / "test-audit-failclose"
    session_dir.mkdir(parents=True)

    ctx = _make_ctx(
        command="echo hello",
        config_overrides={
            "capture_command": True,
            "redaction": {
                "patterns": ["[invalid(regex"],
                "replacement": "[REDACTED]",
                "fail_closed": True,
            },
        },
    )
    with patch("fettle.config.state_dir", return_value=session_dir):
        result = run_check(ctx)

    assert result.decision == Decision.ALLOW
    events_file = session_dir / "bash_events.jsonl"
    record = json.loads(events_file.read_text().strip())
    assert "command" not in record
