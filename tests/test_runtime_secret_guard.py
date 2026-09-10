"""Runtime secret boundary: deny disclosure without echoing credential values."""

from pathlib import Path

import pytest

from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.runtime_secret_guard import find_secret_locations, redact_secrets, run_check


SYNTHETIC_GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"


def _ctx(tmp_path: Path, tool: str, tool_input: dict) -> HookContext:
    return HookContext(
        input=HookInput(
            hook_event_name="PreToolUse",
            tool_name=tool,
            tool_input=tool_input,
            cwd=tmp_path,
            session_id="runtime-secret-test",
            raw={},
        ),
        config={},
        plugin_root=tmp_path,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )


@pytest.mark.parametrize(
    "content",
    [
        f'let config = ["token": "{SYNTHETIC_GITHUB_TOKEN}"]\n',
        f'{{"token": "{SYNTHETIC_GITHUB_TOKEN}"}}\n',
        f'token: "{SYNTHETIC_GITHUB_TOKEN}"\n',
        f"TOKEN={SYNTHETIC_GITHUB_TOKEN}\n",
        f"RuntimeError: request failed with token={SYNTHETIC_GITHUB_TOKEN}\n",
        "token: Z2hwXzEyMzQ1Njc4OTBhYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5eg==\n",
    ],
)
def test_detects_adversarial_formats_without_returning_values(content):
    findings = find_secret_locations(content, "fixture.txt")

    assert findings
    assert findings[0].source == "fixture.txt"
    assert findings[0].line == 1
    assert SYNTHETIC_GITHUB_TOKEN not in repr(findings)


def test_redacts_every_detected_value():
    text = f"before {SYNTHETIC_GITHUB_TOKEN} after"

    redacted = redact_secrets(text)

    assert SYNTHETIC_GITHUB_TOKEN not in redacted
    assert "***REDACTED***" in redacted


def test_read_with_secret_is_blocked_before_execution(tmp_path):
    target = tmp_path / "config.json"
    target.write_text(f'{{"token": "{SYNTHETIC_GITHUB_TOKEN}"}}\n')

    result = run_check(_ctx(tmp_path, "Read", {"file_path": str(target)}))

    assert result.decision is Decision.BLOCK
    assert str(target) in result.message
    assert "GitHub PAT" in result.message
    assert SYNTHETIC_GITHUB_TOKEN not in result.message


def test_clean_read_is_allowed(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("public documentation\n")

    assert run_check(_ctx(tmp_path, "Read", {"file_path": str(target)})).decision is Decision.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "env",
        "printenv",
        "sudo env",
        "/usr/bin/env",
        "bash -c 'printenv'",
        "sh -c \"env | sort\"",
    ],
)
def test_environment_dumps_are_blocked(command, tmp_path):
    result = run_check(_ctx(tmp_path, "Bash", {"command": command}))

    assert result.decision is Decision.BLOCK
    assert "Environment credential dump" in result.message


def test_shell_read_of_secret_file_is_blocked(tmp_path):
    target = tmp_path / "credentials.yaml"
    target.write_text(f'token: "{SYNTHETIC_GITHUB_TOKEN}"\n')

    result = run_check(_ctx(tmp_path, "Bash", {"command": f"cat {target}"}))

    assert result.decision is Decision.BLOCK
    assert SYNTHETIC_GITHUB_TOKEN not in result.message


def test_nested_shell_read_of_secret_file_is_blocked(tmp_path):
    target = tmp_path / "credentials.yaml"
    target.write_text(f'token: "{SYNTHETIC_GITHUB_TOKEN}"\n')

    result = run_check(
        _ctx(tmp_path, "Bash", {"command": f"bash -c 'cat {target}'"})
    )

    assert result.decision is Decision.BLOCK


def test_mcp_file_read_with_secret_is_blocked(tmp_path):
    target = tmp_path / "credentials.json"
    target.write_text(f'{{"token": "{SYNTHETIC_GITHUB_TOKEN}"}}\n')

    result = run_check(
        _ctx(tmp_path, "mcp__filesystem__read_file", {"path": str(target)})
    )

    assert result.decision is Decision.BLOCK


def test_unrelated_tool_without_read_arguments_is_allowed(tmp_path):
    result = run_check(_ctx(tmp_path, "mcp__memory__search", {"query": "public docs"}))

    assert result.decision is Decision.ALLOW


def test_scanner_error_blocks_without_exposing_exception(tmp_path, monkeypatch):
    target = tmp_path / "config.json"
    target.write_text("clean\n")

    def fail_closed(*_args, **_kwargs):
        raise RuntimeError(f"scanner saw {SYNTHETIC_GITHUB_TOKEN}")

    monkeypatch.setattr("fettle.runtime_secret_guard.find_secret_locations", fail_closed)
    result = run_check(_ctx(tmp_path, "Read", {"file_path": str(target)}))

    assert result.decision is Decision.BLOCK
    assert "fettle doctor" in result.message
    assert SYNTHETIC_GITHUB_TOKEN not in result.message
