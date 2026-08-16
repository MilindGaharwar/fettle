"""WP-140 / Stage 13 — Agent abstraction layer tests.

Conformance contract: for every fixture case, every agent's native payload
(Claude Code, Codex, Gemini, OpenCode) MUST normalize to the same HookInput
fields. Payload drift in any agent breaks these tests, not users.
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

AGENT_KEYS = ("claude_code", "codex", "gemini", "opencode")


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

    @pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
    def test_detects_codex(self, case) -> None:
        assert detect_agent(case["codex"]) is AgentKind.CODEX

    @pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
    def test_detects_gemini(self, case) -> None:
        assert detect_agent(case["gemini"]) is AgentKind.GEMINI

    def test_unknown_shape(self) -> None:
        assert detect_agent({"foo": "bar"}) is AgentKind.UNKNOWN
        assert detect_agent({}) is AgentKind.UNKNOWN


class TestConformance:
    """All agents' payloads must normalize to identical events."""

    @pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
    def test_agents_agree(self, case) -> None:
        essences = {
            key: _essence(normalize(case[key], fallback_cwd="/fallback"))
            for key in AGENT_KEYS
        }
        baseline = essences["claude_code"]
        for key, essence in essences.items():
            assert essence == baseline, f"{key} disagrees on {case['name']}"

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
        {"hook_event_name": "BeforeTool"},
        {"hook_event_name": "BeforeTool", "tool_name": 9, "tool_input": "nope"},
        {"hook_event_name": "AfterAgent", "cwd": [], "session_id": {}},
        {"hook_event_name": "PreToolUse", "turn_id": "t-x", "tool_input": None},
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

    def test_gemini_unmapped_tool_passes_through(self) -> None:
        payload = {"hook_event_name": "BeforeTool", "tool_name": "web_fetch", "tool_input": {}}
        assert normalize(payload, fallback_cwd="/fb").tool_name == "web_fetch"

    def test_codex_native_tool_names_mapped(self) -> None:
        payload = {"hook_event_name": "PreToolUse", "turn_id": "t", "tool_name": "shell",
                   "tool_input": {"command": "ls"}, "cwd": "/r"}
        assert normalize(payload, fallback_cwd="/fb").tool_name == "Bash"

    def test_codex_single_file_patch_exposes_target_path(self) -> None:
        payload = {
            "hook_event_name": "PostToolUse",
            "turn_id": "t",
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Begin Patch\n*** Add File: app/new.py\n+x = 1\n*** End Patch"},
            "cwd": "/r",
        }

        hook_input = normalize(payload, fallback_cwd="/fb")

        assert hook_input.tool_name == "Edit"
        assert hook_input.tool_input["file_path"] == "app/new.py"

    def test_codex_multi_file_patch_does_not_guess_target_path(self) -> None:
        payload = {
            "hook_event_name": "PostToolUse",
            "turn_id": "t",
            "tool_name": "apply_patch",
            "tool_input": {"command": (
                "*** Begin Patch\n*** Update File: app/a.py\n@@\n-a = 1\n+a = 2\n"
                "*** Update File: app/b.py\n@@\n-b = 1\n+b = 2\n*** End Patch"
            )},
            "cwd": "/r",
        }

        hook_input = normalize(payload, fallback_cwd="/fb")

        assert "file_path" not in hook_input.tool_input

    def test_codex_malformed_patch_does_not_guess_target_path(self) -> None:
        payload = {
            "hook_event_name": "PostToolUse",
            "turn_id": "t",
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Begin Patch\n*** End Patch"},
            "cwd": "/r",
        }

        hook_input = normalize(payload, fallback_cwd="/fb")

        assert hook_input.tool_name == "Edit"
        assert "file_path" not in hook_input.tool_input


class TestDispatcherEndToEnd:
    """The dispatcher accepts NATIVE payloads from every agent.

    Stage 13: Stop output is an empty object (or systemMessage) — Codex's
    strict Stop parser rejects hookSpecificOutput on that event.
    """

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
        assert "hookSpecificOutput" not in out

    def test_claude_stop_still_works(self, tmp_path) -> None:
        rc, out = self._run({
            "hook_event_name": "Stop",
            "cwd": str(tmp_path),
            "session_id": "e2e-cc",
        })
        assert rc == 0
        assert "hookSpecificOutput" not in out

    def test_native_gemini_after_agent(self, tmp_path) -> None:
        rc, out = self._run({
            "hook_event_name": "AfterAgent",
            "cwd": str(tmp_path),
            "session_id": "e2e-gm",
            "timestamp": "2026-02-14T00:00:00Z",
        })
        assert rc == 0
        assert "hookSpecificOutput" not in out

    def test_native_codex_stop(self, tmp_path) -> None:
        rc, out = self._run({
            "hook_event_name": "Stop",
            "cwd": str(tmp_path),
            "session_id": "e2e-cx",
            "turn_id": "t-e2e",
        })
        assert rc == 0
        assert "hookSpecificOutput" not in out
