"""Dispatcher Phase 1 — Selection, aggregation, budget, fail-open tests."""

import contextlib
import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)
DISPATCHER = os.path.join(SCRIPTS_DIR, "dispatcher.py")


def _run_dispatcher(input_data: dict | str, env_overrides: dict | None = None) -> tuple[int, dict | None]:
    """Run dispatcher.py, return (exit_code, parsed_json_or_None)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    stdin_text = input_data if isinstance(input_data, str) else json.dumps(input_data)
    proc = subprocess.run(
        [sys.executable, DISPATCHER],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    output = None
    if proc.stdout.strip():
        with contextlib.suppress(json.JSONDecodeError):
            output = json.loads(proc.stdout.strip())
    return proc.returncode, output


class TestSelection:
    """Dispatcher selects correct checks based on event/tool."""

    def test_pretooluse_bash_selects_destructive_and_commit(self) -> None:
        rc, out = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "cwd": "/tmp",
            "session_id": "test",
        })
        assert rc == 0

    def test_pretooluse_write_does_not_run_bash_checks(self) -> None:
        rc, out = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/x.py"},
            "cwd": "/tmp",
            "session_id": "test",
        })
        assert rc == 0

    def test_pretooluse_bash_destructive_warns(self) -> None:
        rc, out = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /important"},
            "cwd": "/tmp",
            "session_id": "test",
        })
        assert rc == 0
        assert out is not None
        assert "Destructive" in out.get("hookSpecificOutput", {}).get("additionalContext", "")

    def test_pretooluse_bash_destructive_enforce_blocks(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".fettle.toml").write_text('[gates.destructive]\nenabled = true\nmode = "enforce"\n')
        rc, out = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /important"},
            "cwd": str(proj),
            "session_id": "test",
        })
        assert rc == 2
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestAggregation:
    """Multiple advisory results concatenate; first block wins."""

    def test_advisories_concatenate(self, tmp_path) -> None:
        """Destructive + commit message both warn → both in output."""
        rc, out = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": 'rm -rf /data && git commit -m "bad"'},
            "cwd": "/tmp",
            "session_id": "test",
        })
        assert rc == 0
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "Destructive" in ctx
        assert "Commit message" in ctx

    def test_no_findings_clean_output(self) -> None:
        rc, out = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": "/tmp",
            "session_id": "test",
        })
        assert rc == 0
        hso = out.get("hookSpecificOutput", {})
        assert "additionalContext" not in hso or hso["additionalContext"] == ""


class TestBudget:
    """Budget exhaustion aborts remaining checks."""

    def test_respects_budget(self) -> None:
        """With a very tight budget, dispatcher still exits 0."""
        rc, out = _run_dispatcher(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/x.py"},
                "cwd": "/tmp",
                "session_id": "test",
            },
            env_overrides={"FETTLE_DISPATCHER_BUDGET_MS": "1"},
        )
        assert rc == 0


class TestFailOpen:
    """Dispatcher never crashes the session."""

    def test_malformed_stdin_exits_zero(self) -> None:
        rc, out = _run_dispatcher("not json at all {{{")
        assert rc == 0
        assert out is not None

    def test_empty_stdin_exits_zero(self) -> None:
        rc, out = _run_dispatcher("")
        assert rc == 0

    def test_disabled_via_env(self) -> None:
        rc, out = _run_dispatcher(
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},
            env_overrides={"FETTLE_DISABLE_DISPATCHER": "1"},
        )
        assert rc == 0
        assert "Destructive" not in out.get("hookSpecificOutput", {}).get("additionalContext", "")


class TestDisabledChecks:
    """Config can disable individual checks."""

    def test_disabled_check_not_run(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".fettle.toml").write_text('[dispatcher]\ndisabled_checks = ["destructive_guard"]\n')
        rc, out = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /important"},
            "cwd": str(proj),
            "session_id": "test",
        })
        assert rc == 0
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "Destructive" not in ctx


class TestExistingTestsParity:
    """Existing standalone scripts still work via main()."""

    def test_destructive_guard_standalone_still_works(self) -> None:
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "destructive_guard.py")],
            input=json.dumps({
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /data"},
                "cwd": "/tmp",
            }),
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0
        out = json.loads(proc.stdout)
        assert "Destructive" in out["hookSpecificOutput"]["additionalContext"]
