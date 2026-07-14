"""WP-111 — Tool Loop Detection contract tests.

PostToolUse hook that detects repeated identical tool calls and warns.
"""

import contextlib
import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)


def _run_hook(
    tool_name: str,
    tool_input: dict,
    session_id: str = "test-session",
    cwd: str = "/tmp/test-project",
    env_overrides: dict | None = None,
) -> tuple[int, dict | None, str]:
    """Run loop_detect.py, return (rc, parsed_json, stderr)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    input_data = {
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": cwd,
        "session_id": session_id,
    }
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "loop_detect.py")],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    output = None
    if proc.stdout.strip():
        with contextlib.suppress(json.JSONDecodeError):
            output = json.loads(proc.stdout.strip())
    return proc.returncode, output, proc.stderr


def _run_sequence(
    calls: list[tuple[str, dict]],
    state_dir: str,
    session_id: str = "test-session",
) -> list[tuple[int, dict | None]]:
    """Run a sequence of hook calls, return list of (rc, output)."""
    results = []
    for tool_name, tool_input in calls:
        rc, out, _ = _run_hook(
            tool_name, tool_input,
            session_id=session_id,
            env_overrides={"FETTLE_LOOP_STATE_DIR": state_dir},
        )
        results.append((rc, out))
    return results


class TestNoWarningOnUniqueCalls:
    def test_no_warning_on_unique_calls(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _run_sequence([
            ("Bash", {"command": "ls"}),
            ("Bash", {"command": "pwd"}),
            ("Read", {"file_path": "/tmp/a.py"}),
        ], state_dir)
        assert all(out is None for _, out in results)


class TestWarnsAfterIdenticalCalls:
    def test_warns_after_3_identical_calls(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _run_sequence([
            ("Bash", {"command": "cat /tmp/x.py"}),
            ("Bash", {"command": "cat /tmp/x.py"}),
            ("Bash", {"command": "cat /tmp/x.py"}),
        ], state_dir)
        # First two: no warning. Third: warning.
        assert results[0][1] is None
        assert results[1][1] is None
        assert results[2][1] is not None
        assert "Loop detected" in results[2][1]["hookSpecificOutput"]["additionalContext"]

    def test_warns_on_edit_loop(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _run_sequence([
            ("Edit", {"file_path": "/tmp/x.py", "old_string": "a", "new_string": "b"}),
            ("Edit", {"file_path": "/tmp/x.py", "old_string": "a", "new_string": "b"}),
            ("Edit", {"file_path": "/tmp/x.py", "old_string": "a", "new_string": "b"}),
        ], state_dir)
        assert results[2][1] is not None


class TestDifferentParamsResetsCount:
    def test_different_params_resets_count(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _run_sequence([
            ("Bash", {"command": "cat /tmp/x.py"}),
            ("Bash", {"command": "cat /tmp/x.py"}),
            ("Bash", {"command": "cat /tmp/y.py"}),  # different
            ("Bash", {"command": "cat /tmp/x.py"}),
            ("Bash", {"command": "cat /tmp/x.py"}),
        ], state_dir)
        # Never reaches 3 consecutive identical
        assert all(out is None for _, out in results)


class TestDifferentToolResetsCount:
    def test_different_tool_resets_count(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _run_sequence([
            ("Bash", {"command": "cat /tmp/x.py"}),
            ("Bash", {"command": "cat /tmp/x.py"}),
            ("Read", {"file_path": "/tmp/x.py"}),  # different tool
            ("Bash", {"command": "cat /tmp/x.py"}),
            ("Bash", {"command": "cat /tmp/x.py"}),
        ], state_dir)
        assert all(out is None for _, out in results)


class TestWindowSizeRespected:
    def test_window_size_respected(self, tmp_path) -> None:
        """Old identical calls outside window don't count."""
        state_dir = str(tmp_path)
        calls = [
            ("Bash", {"command": "cat /tmp/x.py"}),
            ("Bash", {"command": "cat /tmp/x.py"}),
            # 5 different calls to push old ones out of window (default 7)
            ("Bash", {"command": "ls 1"}),
            ("Bash", {"command": "ls 2"}),
            ("Bash", {"command": "ls 3"}),
            ("Bash", {"command": "ls 4"}),
            ("Bash", {"command": "ls 5"}),
            # Now the original 2 are outside the window
            ("Bash", {"command": "cat /tmp/x.py"}),
        ]
        results = _run_sequence(calls, state_dir)
        # Should NOT warn — only 1 in the current window
        assert results[-1][1] is None


class TestCustomThreshold:
    def test_custom_threshold_works(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text("[gates.loop_detect]\nenabled = true\nthreshold = 2\n")
        state_dir = str(tmp_path / "state")
        os.makedirs(state_dir, exist_ok=True)
        results2 = []
        for tool_name, tool_input in [
            ("Bash", {"command": "echo hi"}),
            ("Bash", {"command": "echo hi"}),
        ]:
            env = os.environ.copy()
            env["FETTLE_LOOP_STATE_DIR"] = state_dir
            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": tool_name,
                "tool_input": tool_input,
                "cwd": str(proj),
                "session_id": "custom-thresh-2",
            }
            proc = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS_DIR, "loop_detect.py")],
                input=json.dumps(input_data),
                capture_output=True, text=True, timeout=10, env=env,
            )
            output = None
            if proc.stdout.strip():
                with contextlib.suppress(json.JSONDecodeError):
                    output = json.loads(proc.stdout.strip())
            results2.append((proc.returncode, output))
        assert results2[1][1] is not None


class TestAlwaysExitsZero:
    def test_never_blocks(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _run_sequence([
            ("Bash", {"command": "rm -rf /"}),
            ("Bash", {"command": "rm -rf /"}),
            ("Bash", {"command": "rm -rf /"}),
            ("Bash", {"command": "rm -rf /"}),
        ], state_dir)
        assert all(rc == 0 for rc, _ in results)


class TestMalformedInput:
    def test_malformed_stdin_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "loop_detect.py")],
            input="not json",
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0

    def test_missing_tool_input_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "loop_detect.py")],
            input=json.dumps({"tool_name": "Bash"}),
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0
