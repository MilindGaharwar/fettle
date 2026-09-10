"""Tool output protection only claims interception on verified host surfaces."""

import json
from pathlib import Path

import pytest

from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.runtime_output_guard import run_check


TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"


def _ctx(tmp_path: Path, raw: dict) -> HookContext:
    return HookContext(
        input=HookInput(
            hook_event_name="PostToolUse",
            tool_name="Read",
            tool_input={"file_path": "config.json"},
            cwd=tmp_path,
            session_id="output-guard",
            raw=raw,
        ),
        config={},
        plugin_root=tmp_path,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )


def test_claude_output_is_replaced_with_redacted_content(tmp_path):
    result = run_check(_ctx(tmp_path, {
        "hook_event_name": "PostToolUse",
        "tool_response": f"token={TOKEN}",
    }))

    serialized = json.dumps(result.hook_specific_output)
    assert result.decision is Decision.ALLOW
    assert "updatedToolOutput" in result.hook_specific_output
    assert TOKEN not in serialized
    assert "***REDACTED***" in serialized


def test_gemini_output_is_withheld_with_value_free_replacement(tmp_path):
    result = run_check(_ctx(tmp_path, {
        "hook_event_name": "AfterTool",
        "tool_response": {"llmContent": f"failure: {TOKEN}"},
    }))

    assert result.decision is Decision.BLOCK
    assert "credential" in result.message.lower()
    assert TOKEN not in result.message


@pytest.mark.parametrize(
    "raw",
    [
        {"hook_event_name": "PostToolUse", "turn_id": "codex", "tool_response": TOKEN},
        {"hook_event_name": "PostToolUse", "fettle_host": "opencode", "tool_response": TOKEN},
    ],
)
def test_unsupported_hosts_do_not_claim_output_filtering(tmp_path, raw):
    result = run_check(_ctx(tmp_path, raw))

    assert result.decision is Decision.ALLOW
    assert not result.hook_specific_output


def test_clean_supported_output_is_unchanged(tmp_path):
    result = run_check(_ctx(tmp_path, {
        "hook_event_name": "PostToolUse",
        "tool_response": "public output",
    }))

    assert result.decision is Decision.ALLOW
    assert not result.hook_specific_output


def test_scanner_failure_withholds_supported_output(tmp_path, monkeypatch):
    def crash(_text):
        raise RuntimeError(f"failed on {TOKEN}")

    monkeypatch.setattr("fettle.runtime_output_guard.redact_secrets", crash)
    result = run_check(_ctx(tmp_path, {
        "hook_event_name": "AfterTool",
        "tool_response": TOKEN,
    }))

    assert result.decision is Decision.BLOCK
    assert "fettle doctor" in result.message
    assert TOKEN not in result.message
