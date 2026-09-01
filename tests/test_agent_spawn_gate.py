"""Tests for [gates.agent_spawn] — nested-agent-launch gate (WP-157, A5)."""

from pathlib import Path

import pytest

from fettle.agent_spawn_gate import run_check
from fettle.dispatcher_types import Decision, HookContext, HookInput


def _ctx(command: str, mode: str = "advisory", enabled: bool = True) -> HookContext:
    hook_input = HookInput(
        hook_event_name="PreToolUse",
        tool_name="Bash",
        tool_input={"command": command},
        cwd=Path("/tmp"),
        session_id="s1",
        raw={},
    )
    return HookContext(
        input=hook_input,
        config={"gates": {"agent_spawn": {"enabled": enabled, "mode": mode}}},
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=1e12,
    )


@pytest.fixture(autouse=True)
def _no_capsule(monkeypatch):
    monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)


VIOLATING = [
    'claude -p "fix the bug"',
    'claude --print "task"',
    "codex exec 'do the thing'",
    'gemini -p "task"',
    'gemini --prompt "task"',
    "gemini --yolo",
    'opencode run "task"',
    'cd /tmp && claude -p "task"',
    'env FOO=bar claude -p "task"',
    '/usr/local/bin/claude -p "task"',
]

CLEAN = [
    "claude --version",
    "claude",                      # interactive, not headless
    "codex --help",
    "git commit -m 'codex exec docs'",
    'echo "claude -p is how you launch it"',
    "grep -r 'opencode run' docs/",
    "fettle spawn claude --task 'fix it'",
    "opencode --version",
    "gemini --help",
    "my-claude -p x",              # not the binary
]


class TestDetection:
    @pytest.mark.parametrize("cmd", VIOLATING)
    def test_ungoverned_launch_advises(self, cmd) -> None:
        result = run_check(_ctx(cmd))
        assert result.decision == Decision.ADVISORY, cmd
        assert "fettle spawn" in result.message

    @pytest.mark.parametrize("cmd", CLEAN)
    def test_clean_commands_allowed(self, cmd) -> None:
        assert run_check(_ctx(cmd)).decision == "allow", cmd


class TestBypassLadder:
    BYPASS = [
        'claude -p --dangerously-skip-permissions "task"',
        "gemini --yolo",
        "codex exec --full-auto 'task'",
        'env FETTLE_GATE_MODE=off claude -p "task"',
    ]

    @pytest.mark.parametrize("cmd", BYPASS)
    def test_bypass_blocks_in_enforce(self, cmd) -> None:
        result = run_check(_ctx(cmd, mode="enforce"))
        assert result.decision == "block", cmd
        hso = result.hook_specific_output
        assert hso["permissionDecision"] == "deny"

    @pytest.mark.parametrize("cmd", BYPASS)
    def test_bypass_advises_in_advisory(self, cmd) -> None:
        assert run_check(_ctx(cmd)).decision == "advisory", cmd

    def test_bypass_blocks_even_with_capsule(self, monkeypatch) -> None:
        # A bypass flag disables the child's hooks — the capsule cannot follow.
        monkeypatch.setenv("FETTLE_POLICY_CAPSULE", "/tmp/c.json")
        result = run_check(_ctx('claude -p --yolo "t"', mode="enforce"))
        assert result.decision == "block"


class TestGoverned:
    def test_capsule_in_env_allows_plain_launch(self, monkeypatch) -> None:
        monkeypatch.setenv("FETTLE_POLICY_CAPSULE", "/tmp/c.json")
        assert run_check(_ctx('claude -p "t"')).decision == "allow"

    def test_inline_capsule_allows(self) -> None:
        cmd = 'env FETTLE_POLICY_CAPSULE=/tmp/c.json claude -p "t"'
        assert run_check(_ctx(cmd)).decision == "allow"


class TestConfig:
    def test_disabled_gate_allows(self) -> None:
        assert run_check(_ctx('claude -p "t"', enabled=False)).decision == "allow"

    def test_no_command_allows(self) -> None:
        assert run_check(_ctx("")).decision == "allow"

    def test_enforce_plain_launch_still_advisory(self) -> None:
        # Only the bypass ladder escalates to block (design §3.2).
        assert run_check(_ctx('claude -p "t"', mode="enforce")).decision == "advisory"


class TestRegistry:
    def test_registered_for_pretooluse_bash(self) -> None:
        from fettle.dispatcher_registry import CHECKS
        spec = next(c for c in CHECKS if c.name == "agent_spawn_gate")
        assert spec.events == frozenset({"PreToolUse"})
        assert spec.tools == frozenset({"Bash"})


class TestGateModeKillSwitch:
    """2026-08 audit: FETTLE_GATE_MODE=off screened on ANY segment, not
    only agent launches — it disables every gate for the process tree."""

    def test_non_launch_command_with_gate_off_advises(self) -> None:
        result = run_check(_ctx("FETTLE_GATE_MODE=off git commit -m x"))
        assert result.decision == Decision.ADVISORY
        assert "FETTLE_GATE_MODE=off" in result.message

    def test_non_launch_command_with_gate_off_blocks_in_enforce(self) -> None:
        result = run_check(_ctx("FETTLE_GATE_MODE=off make test", mode="enforce"))
        assert result.decision == "block"
        assert result.hook_specific_output["permissionDecision"] == "deny"

    def test_quoted_mention_is_not_flagged(self) -> None:
        result = run_check(_ctx("grep -r 'FETTLE_GATE_MODE=off' docs/"))
        assert result.decision == "allow"
