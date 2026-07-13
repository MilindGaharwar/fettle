"""Tests for scripts/tool_runner.py — WP-70: Tool execution abstraction."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from tool_runner import (
    ToolRunner,
    FakeRunner,
    RunResult,
)


def test_runs_command_and_captures_output():
    runner = ToolRunner()
    result = runner.run(["echo", "hello world"])
    assert result.returncode == 0
    assert "hello world" in result.stdout


def test_timeout_kills_process_cleanly():
    runner = ToolRunner(timeout_s=1)
    result = runner.run(["sleep", "10"])
    assert result.timed_out
    assert result.returncode != 0


def test_timeout_produces_structured_finding():
    runner = ToolRunner(timeout_s=1)
    result = runner.run(["sleep", "10"])
    assert result.timed_out
    assert "timeout" in result.error_message.lower() or "timed out" in result.error_message.lower()


def test_missing_tool_produces_advisory():
    runner = ToolRunner()
    result = runner.run(["nonexistent_tool_xyz_12345"])
    assert result.tool_missing
    assert result.returncode != 0


def test_working_directory_set_correctly(tmp_path):
    marker = tmp_path / "marker.txt"
    marker.write_text("found")
    runner = ToolRunner(cwd=str(tmp_path))
    result = runner.run(["cat", "marker.txt"])
    assert result.returncode == 0
    assert "found" in result.stdout


def test_env_vars_passed_through():
    runner = ToolRunner(env={"FETTLE_TEST_VAR": "test_value_42"})
    result = runner.run(["bash", "-c", "echo $FETTLE_TEST_VAR"])
    assert "test_value_42" in result.stdout


def test_secret_env_vars_redacted_in_logs():
    runner = ToolRunner(
        env={"SECRET_KEY": "super_secret_123"},
        redact_env_keys=["SECRET_KEY"],
    )
    assert "super_secret_123" not in runner.describe_env()


def test_fake_executor_for_testing():
    fake = FakeRunner(
        responses={
            ("ruff", "check", "test.py"): RunResult(
                returncode=1,
                stdout="test.py:1:1 F401 unused import",
                stderr="",
            ),
        }
    )
    result = fake.run(["ruff", "check", "test.py"])
    assert result.returncode == 1
    assert "F401" in result.stdout


def test_fake_executor_unknown_command():
    fake = FakeRunner(responses={})
    result = fake.run(["unknown", "cmd"])
    assert result.tool_missing


def test_nonzero_exit_handled():
    runner = ToolRunner()
    result = runner.run(["bash", "-c", "exit 42"])
    assert result.returncode == 42
    assert not result.timed_out
    assert not result.tool_missing


def test_binary_output_handled():
    runner = ToolRunner()
    result = runner.run(["bash", "-c", "printf '\\x00\\x01\\x02'"])
    assert result.returncode == 0
    assert result.stdout is not None
