"""E2E dispatcher-contract tests for quality_gate.run_check (WP-1 + WP-2).

Regression class from the 2026-08 audits (H-01 + Opus 2.1): the subprocess
consumed the legacy `hook_event` field while real agent payloads carry
`hook_event_name`, so PreToolUse blocks silently downgraded to warnings; and
`run_check` read only `additionalContext`, destroying every block reason.

These tests drive run_check exactly the way the dispatcher does — with a
normalized HookInput whose `raw` payload uses each host's native vocabulary —
and assert blocks really block, with their real reasons.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fettle.dispatcher_types import Decision, HookContext, HookInput  # noqa: E402
from fettle.quality_gate import run_check  # noqa: E402


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """Tmp repo with the UX gate enabled and isolated fettle state."""
    (tmp_path / ".fettle.toml").write_text(
        "[gates.ux_spec]\nenabled = true\n\n[gates.tests]\nenabled = true\n"
    )
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path


def _ctx(repo, event, raw, tool_name="Write", tool_input=None, session_id="sess-e2e"):
    if tool_input is None:
        tool_input = {"file_path": "src/pages/Home.tsx", "content": "x"}
    hook_input = HookInput(
        hook_event_name=event,
        tool_name=tool_name,
        tool_input=tool_input,
        cwd=Path(repo),
        session_id=session_id,
        raw=raw,
    )
    return HookContext(
        input=hook_input,
        config={},
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


# ─── PreToolUse blocks through every host vocabulary ─────────────────────────


def test_pre_edit_ux_blocks_with_claude_shaped_raw(repo):
    """Claude payloads carry hook_event_name — must still block on Pre."""
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "src/pages/Home.tsx", "content": "x"},
        "cwd": str(repo),
        "session_id": "sess-e2e",
    }
    result = run_check(_ctx(repo, "PreToolUse", raw))
    assert result.decision is Decision.BLOCK


def test_pre_edit_ux_blocks_with_legacy_raw(repo):
    """Legacy payloads carrying hook_event keep working."""
    raw = {
        "hook_event": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "src/pages/Home.tsx", "content": "x"},
        "cwd": str(repo),
        "session_id": "sess-e2e",
    }
    result = run_check(_ctx(repo, "PreToolUse", raw))
    assert result.decision is Decision.BLOCK


def test_pre_edit_ux_blocks_with_foreign_raw_vocabulary(repo):
    """Normalization must dominate: a gemini-shaped raw payload with entirely
    different field names still blocks, because run_check canonicalizes from
    the normalized HookInput — never from the host's spelling."""
    raw = {
        "eventName": "BeforeTool",
        "tool": {"name": "write_file", "args": {"file_path": "src/pages/Home.tsx"}},
        "workingDirectory": str(repo),
    }
    result = run_check(_ctx(repo, "PreToolUse", raw))
    assert result.decision is Decision.BLOCK


def test_post_edit_ux_never_blocks(repo):
    """PostToolUse: the edit already happened — warn, don't block."""
    raw = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "src/pages/Home.tsx", "content": "x"},
        "cwd": str(repo),
        "session_id": "sess-e2e",
    }
    result = run_check(_ctx(repo, "PostToolUse", raw))
    assert result.decision is not Decision.BLOCK


# ─── Block reasons must survive the subprocess boundary (Opus 2.1) ───────────


def test_block_reason_carries_real_finding(repo):
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "src/pages/Home.tsx", "content": "x"},
        "cwd": str(repo),
        "session_id": "sess-e2e",
    }
    result = run_check(_ctx(repo, "PreToolUse", raw))
    assert result.decision is Decision.BLOCK
    assert result.message  # never an empty reason
    assert "UX" in result.message  # the actual finding, not a generic banner
    assert "docs" in result.message


# ─── Stop-event test enforcement reaches the gate ────────────────────────────


def test_stop_blocks_untested_edits_with_normalized_payload(repo):
    """A Stop event whose payload has only hook_event_name must still trigger
    test enforcement (previously missed: hook_event was empty → no Stop path
    unless the host happened to send stop_hook_active)."""
    from fettle.config import state_dir

    sdir = state_dir("sess-e2e")
    sdir.mkdir(parents=True, exist_ok=True)
    impl = repo / "core" / "logic.py"
    impl.parent.mkdir()
    impl.write_text("x = 1\n")
    (sdir / "edits.jsonl").write_text(
        json.dumps({"file": str(impl), "tested": False}) + "\n"
    )

    raw = {
        "hook_event_name": "Stop",
        "cwd": str(repo),
        "session_id": "sess-e2e",
    }
    result = run_check(_ctx(repo, "Stop", raw, tool_name=None, tool_input={}))
    assert result.decision is Decision.BLOCK
    assert "TESTS" in result.message
