"""WP-140 — Agent abstraction layer tests.

Conformance contract: for every fixture case, the Claude Code payload and
the native OpenCode payload MUST normalize to the same HookInput fields.
Payload drift in either agent breaks these tests, not users.
"""

import json
import os
import subprocess
import sys

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PLUGIN_DIR)

from fettle.agents import AgentKind, detect_agent, normalize  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "agent_payloads", "conformance.json")

with open(FIXTURES) as _fh:
    CASES = json.load(_fh)["cases"]


def _essence(hook_input) -> dict:
    """The normalized fields that must agree across agents."""
    return {
        "hook_event_name": hook_input.hook_event_name,
        "tool_name": hook_input.tool_name,
        "file_path": hook_input.tool_input.get("file_path"),
        "command": hook_input.tool_input.get("command"),
        "cwd": str(hook_input.cwd),
        "session_id": hook_input.session_id,
    }


class TestDetection:
    @pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
    def test_detects_claude_code(self, case) -> None:
        assert detect_agent(case["claude_code"]) is AgentKind.CLAUDE_CODE

    @pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
    def test_detects_opencode(self, case) -> None:
        assert detect_agent(case["opencode"]) is AgentKind.OPENCODE

    def test_unknown_shape(self) -> None:
        assert detect_agent({"foo": "bar"}) is AgentKind.UNKNOWN
        assert detect_agent({}) is AgentKind.UNKNOWN


class TestConformance:
    """Both agents' payloads must normalize to identical events."""

    @pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
    def test_agents_agree(self, case) -> None:
        cc = normalize(case["claude_code"], fallback_cwd="/fallback")
        oc = normalize(case["opencode"], fallback_cwd="/fallback")
        assert _essence(cc) == _essence(oc), f"agents disagree on {case['name']}"

    @pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
    def test_matches_expected(self, case) -> None:
        got = _essence(normalize(case["claude_code"], fallback_cwd="/fallback"))
        for key, want in case["expect"].items():
            assert got[key] == want, f"{case['name']}.{key}: {got[key]!r} != {want!r}"


class TestRobustness:
    """Translators never raise on malformed input (fail-open contract)."""

    @pytest.mark.parametrize("payload", [
        {},
        {"hook_event_name": None},
        {"hook_event_name": "PreToolUse", "tool_input": "not-a-dict"},
        {"hook_event_name": "PreToolUse", "cwd": 42, "session_id": 7},
        {"type": "tool.execute.before"},
        {"type": "tool.execute.before", "tool": 3, "args": None},
        {"type": "session.idle", "properties": "nope"},
    ])
    def test_never_raises(self, payload) -> None:
        hook_input = normalize(payload, fallback_cwd="/fb")
        assert hook_input.raw == payload
        assert isinstance(hook_input.tool_input, dict)

    def test_fallback_cwd_used(self) -> None:
        hook_input = normalize({"hook_event_name": "Stop"}, fallback_cwd="/fb")
        assert str(hook_input.cwd) == "/fb"

    def test_opencode_unmapped_tool_is_none(self) -> None:
        payload = {"type": "tool.execute.before", "tool": "webfetch", "args": {}, "directory": "/r"}
        assert normalize(payload, fallback_cwd="/fb").tool_name is None


class TestDispatcherEndToEnd:
    """The dispatcher accepts NATIVE payloads from both agents."""

    def _run(self, payload: dict) -> tuple[int, dict]:
        proc = subprocess.run(
            [sys.executable, os.path.join(PLUGIN_DIR, "fettle", "dispatcher.py")],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=30,
        )
        return proc.returncode, json.loads(proc.stdout or "{}")

    def test_native_opencode_stop(self, tmp_path) -> None:
        rc, out = self._run({
            "type": "session.idle",
            "properties": {"sessionID": "e2e-oc"},
            "directory": str(tmp_path),
        })
        assert rc == 0
        assert out["hookSpecificOutput"]["hookEventName"] == "Stop"

    def test_claude_stop_still_works(self, tmp_path) -> None:
        rc, out = self._run({
            "hook_event_name": "Stop",
            "cwd": str(tmp_path),
            "session_id": "e2e-cc",
        })
        assert rc == 0
        assert out["hookSpecificOutput"]["hookEventName"] == "Stop"
