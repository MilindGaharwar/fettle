"""WP-104 — SubagentStart hook (subagent_inject.js) contract tests.

Tests the JavaScript hook that injects The Ladder into subagents before they
generate code. Runs via `node` subprocess, matching the pattern in
test_hook_contracts.py but targeting JS instead of Python.
"""

import contextlib
import json
import os
import subprocess
import tempfile

HOOKS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"
)
HOOK_SCRIPT = os.path.join(HOOKS_DIR, "subagent_inject.js")


def _run_hook(
    input_data: dict | str,
    env_overrides: dict | None = None,
    timeout: int = 5,
) -> tuple[int, dict | None, str]:
    """Run subagent_inject.js, return (exit_code, parsed_json_or_None, stderr)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    stdin_text = input_data if isinstance(input_data, str) else json.dumps(input_data)
    proc = subprocess.run(
        ["node", HOOK_SCRIPT],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    output = None
    if proc.stdout.strip():
        with contextlib.suppress(json.JSONDecodeError):
            output = json.loads(proc.stdout.strip())
    return proc.returncode, output, proc.stderr


def _base_input(agent_type: str = "general-purpose") -> dict:
    return {
        "hook_event_name": "SubagentStart",
        "session_id": "test-session-123",
        "cwd": "/tmp/test-project",
        "agent_id": "agent-abc",
        "agent_type": agent_type,
    }


class TestInjectsLadderIntoSubagent:
    """Core injection behavior — The Ladder content appears in output."""

    def test_injects_ladder_into_subagent(self) -> None:
        rc, out, _ = _run_hook(_base_input())
        assert rc == 0
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "Does this need to exist" in ctx
        assert "YAGNI" in ctx

    def test_output_contains_all_ladder_rungs(self) -> None:
        rc, out, _ = _run_hook(_base_input())
        assert rc == 0
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "Already in this codebase" in ctx
        assert "Stdlib" in ctx or "stdlib" in ctx
        assert "Already-installed dep" in ctx
        assert "One-liner" in ctx
        assert "minimum code" in ctx


class TestRespectsDisabledConfig:
    """Gate disabled → no injection, clean exit."""

    def test_respects_disabled_config(self, tmp_path) -> None:
        cfg = tmp_path / ".fettle.toml"
        cfg.write_text("[gates.subagent]\nenabled = false\n")
        rc, out, _ = _run_hook(
            _base_input(),
            env_overrides={"FETTLE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0
        assert out is None


class TestMatcherFiltersByAgentType:
    """FETTLE_SUBAGENT_MATCHER env var filters by agent_type regex."""

    def test_matcher_filters_by_agent_type(self) -> None:
        rc, out, _ = _run_hook(
            _base_input("code-reviewer"),
            env_overrides={"FETTLE_SUBAGENT_MATCHER": "^general|^claude$"},
        )
        assert rc == 0
        assert out is None

    def test_matcher_allows_matching_agent_type(self) -> None:
        rc, out, _ = _run_hook(
            _base_input("general-purpose"),
            env_overrides={"FETTLE_SUBAGENT_MATCHER": "^general"},
        )
        assert rc == 0
        assert out is not None
        assert "hookSpecificOutput" in out


class TestNoMatcherInjectsIntoAll:
    """No FETTLE_SUBAGENT_MATCHER → inject into every subagent."""

    def test_no_matcher_injects_into_all(self) -> None:
        rc, out, _ = _run_hook(_base_input("whatever-agent"))
        assert rc == 0
        assert out is not None
        assert "additionalContext" in out.get("hookSpecificOutput", {})


class TestFailsOpenOnStdinError:
    """Malformed/empty stdin → exit 0, no output (fail-open)."""

    def test_fails_open_on_malformed_stdin(self) -> None:
        rc, out, _ = _run_hook("not valid json {{{")
        assert rc == 0
        assert out is None

    def test_fails_open_on_empty_stdin(self) -> None:
        rc, out, _ = _run_hook("")
        assert rc == 0
        assert out is None


class TestFailsOpenOnMissingConfig:
    """Missing .fettle.toml → still injects (defaults to enabled)."""

    def test_fails_open_on_missing_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rc, out, _ = _run_hook(
                _base_input(),
                env_overrides={"FETTLE_PROJECT_DIR": td},
            )
            assert rc == 0
            assert out is not None
            assert "additionalContext" in out.get("hookSpecificOutput", {})


class TestInjectionUnder500Tokens:
    """Injected content must be under 500 tokens (~2000 chars conservative)."""

    def test_injection_under_500_tokens(self) -> None:
        rc, out, _ = _run_hook(_base_input())
        assert rc == 0
        ctx = out["hookSpecificOutput"]["additionalContext"]
        # Conservative: 500 tokens ≈ ~2000 chars for English text
        assert len(ctx) < 2000


class TestCustomInjectionFileLoaded:
    """[gates.subagent] injection_file = path → loads that content instead."""

    def test_custom_injection_file_loaded(self, tmp_path) -> None:
        custom = tmp_path / "my_rules.txt"
        custom.write_text("Custom rule: always use semicolons.")
        cfg = tmp_path / ".fettle.toml"
        cfg.write_text(
            f'[gates.subagent]\nenabled = true\ninjection_file = "{custom}"\n'
        )
        rc, out, _ = _run_hook(
            _base_input(),
            env_overrides={"FETTLE_PROJECT_DIR": str(tmp_path)},
        )
        assert rc == 0
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "Custom rule: always use semicolons" in ctx


class TestTimeoutDoesNotHangSession:
    """Hook must complete in <50ms for typical case (we allow 1s in test)."""

    def test_timeout_does_not_hang_session(self) -> None:
        import time

        start = time.monotonic()
        rc, _, _ = _run_hook(_base_input(), timeout=5)
        elapsed = time.monotonic() - start
        assert rc == 0
        # Node cold-start + script should still be well under 1s
        assert elapsed < 1.0


class TestJsonOutputFormatCorrect:
    """Output matches Claude Code SubagentStart hook protocol."""

    def test_json_output_format_correct(self) -> None:
        rc, out, _ = _run_hook(_base_input())
        assert rc == 0
        assert "hookSpecificOutput" in out
        hso = out["hookSpecificOutput"]
        assert hso["hookEventName"] == "SubagentStart"
        assert isinstance(hso["additionalContext"], str)
        assert len(hso["additionalContext"]) > 0
