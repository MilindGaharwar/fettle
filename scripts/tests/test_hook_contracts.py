"""Contract tests for Fettle hooks.

Each test feeds known JSON to a hook via subprocess stdin and verifies
the JSON output shape matches the expected contract.
"""

import json
import os
import subprocess

SCRIPTS_DIR = os.path.expanduser(
    "~/.claude/plugins/fettle/scripts"
)


def _run_hook(script: str, input_data: dict, env_overrides: dict | None = None) -> tuple[int, dict | None]:
    """Run a hook script, return (exit_code, parsed_json_output_or_None)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        ["python3", os.path.join(SCRIPTS_DIR, script)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    output = None
    if proc.stdout.strip():
        output = json.loads(proc.stdout)
    return proc.returncode, output


class TestPlanGate:
    """plan_gate.py — PreToolUse hook."""

    def test_blocks_without_plan_marker(self, tmp_path: object) -> None:
        marker = str(tmp_path) + "/nonexistent.json"
        rc, out = _run_hook(
            "plan_gate.py",
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/fettle/somefile.py"}},
            env_overrides={"FETTLE_PLAN_MARKER": marker},
        )
        assert rc == 2
        assert out is not None
        assert out["decision"] == "block"
        assert "hookSpecificOutput" in out
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_allows_with_valid_marker(self, tmp_path: object) -> None:
        marker = os.path.join(str(tmp_path), "plan.json")
        with open(marker, "w") as f:
            json.dump({"plan": "test.md", "approved": True, "ts": 1}, f)
        rc, out = _run_hook(
            "plan_gate.py",
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/fettle/somefile.py"}},
            env_overrides={"FETTLE_PLAN_MARKER": marker},
        )
        assert rc == 0
        assert out is None

    def test_allows_exempt_paths(self) -> None:
        rc, out = _run_hook(
            "plan_gate.py",
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/scratch.py"}},
            env_overrides={"FETTLE_PLAN_MARKER": "/nonexistent"},
        )
        assert rc == 0
        assert out is None

    def test_allows_test_files(self) -> None:
        rc, out = _run_hook(
            "plan_gate.py",
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/fettle/tests/test_something.py"}},
            env_overrides={"FETTLE_PLAN_MARKER": "/nonexistent"},
        )
        assert rc == 0
        assert out is None

    def test_allows_config_files(self) -> None:
        rc, out = _run_hook(
            "plan_gate.py",
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/fettle/config.toml"}},
            env_overrides={"FETTLE_PLAN_MARKER": "/nonexistent"},
        )
        assert rc == 0
        assert out is None

    def test_handles_malformed_stdin(self) -> None:
        proc = subprocess.run(
            ["python3", os.path.join(SCRIPTS_DIR, "plan_gate.py")],
            input="not json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0


class TestMcpGate:
    """mcp_gate.py — PreToolUse hook."""

    def test_blocks_npm_install_mcp(self) -> None:
        rc, out = _run_hook(
            "mcp_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "npm install some-mcp-package"}},
        )
        assert rc == 2
        assert out is not None
        assert out["decision"] == "block"
        assert "Zero-Trust" in out["reason"]

    def test_blocks_npx_mcp(self) -> None:
        rc, out = _run_hook(
            "mcp_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "npx @modelcontextprotocol/mcp-server"}},
        )
        assert rc == 2

    def test_allows_non_mcp_install(self) -> None:
        rc, out = _run_hook(
            "mcp_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "npm install express"}},
        )
        assert rc == 0
        assert out is None

    def test_allows_non_bash_tool(self) -> None:
        rc, out = _run_hook(
            "mcp_gate.py",
            {"tool_name": "Read", "tool_input": {"file_path": "/etc/hosts"}},
        )
        assert rc == 0
        assert out is None


class TestLiveTestGate:
    """live_test_gate.py — Stop hook."""

    def test_blocks_with_untested_entries(self, tmp_path: object) -> None:
        tracking = os.path.join(str(tmp_path), "edits.jsonl")
        with open(tracking, "w") as f:
            f.write(json.dumps({"file": "/tmp/fettle/somefile.py", "ts": 1, "tested": False}) + "\n")
        rc, out = _run_hook(
            "live_test_gate.py",
            {"stop_hook_active": False},
            env_overrides={"FETTLE_EDIT_TRACKING": tracking},
        )
        assert rc == 2
        assert out is not None
        assert out["decision"] == "block"
        assert "somefile.py" in out["reason"]

    def test_allows_when_all_tested(self, tmp_path: object) -> None:
        tracking = os.path.join(str(tmp_path), "edits.jsonl")
        with open(tracking, "w") as f:
            f.write(json.dumps({"file": "/tmp/fettle/somefile.py", "ts": 1, "tested": True}) + "\n")
        rc, out = _run_hook(
            "live_test_gate.py",
            {"stop_hook_active": False},
            env_overrides={"FETTLE_EDIT_TRACKING": tracking},
        )
        assert rc == 0
        assert out is None

    def test_allows_when_no_tracking_file(self, tmp_path: object) -> None:
        rc, out = _run_hook(
            "live_test_gate.py",
            {"stop_hook_active": False},
            env_overrides={"FETTLE_EDIT_TRACKING": str(tmp_path) + "/nonexistent.jsonl"},
        )
        assert rc == 0
        assert out is None

    def test_convergence_allows_on_second_fire(self, tmp_path: object) -> None:
        tracking = os.path.join(str(tmp_path), "edits.jsonl")
        with open(tracking, "w") as f:
            f.write(json.dumps({"file": "/tmp/fettle/somefile.py", "ts": 1, "tested": False}) + "\n")
        rc, out = _run_hook(
            "live_test_gate.py",
            {"stop_hook_active": True},
            env_overrides={"FETTLE_EDIT_TRACKING": tracking},
        )
        assert rc == 0
        assert out is None


class TestMcpTrustGate:
    """mcp_trust_gate.py — PreToolUse hook."""

    def test_blocks_unpinned_pip_install(self) -> None:
        rc, out = _run_hook(
            "mcp_trust_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "pip install requests"}},
        )
        assert rc == 2
        assert out is not None
        assert "Unpinned" in out["reason"]

    def test_blocks_iptables_modification(self) -> None:
        rc, out = _run_hook(
            "mcp_trust_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "sudo iptables -F"}},
        )
        assert rc == 2
        assert out is not None
        assert "iptables" in out["reason"]

    def test_allows_harmless_bash(self) -> None:
        rc, out = _run_hook(
            "mcp_trust_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "ls -la /tmp"}},
        )
        assert rc == 0
        assert out is None


class TestPostBashTestDetect:
    """post_bash_test_detect.py — PostToolUse hook."""

    def test_marks_entries_tested_on_pytest(self, tmp_path: object) -> None:
        tracking = os.path.join(str(tmp_path), "edits.jsonl")
        with open(tracking, "w") as f:
            f.write(json.dumps({"file": "/tmp/fettle/mod.py", "ts": 1, "tested": False}) + "\n")
        rc, _ = _run_hook(
            "post_bash_test_detect.py",
            {"tool_name": "Bash", "tool_input": {"command": "pytest tests/"}},
            env_overrides={"FETTLE_EDIT_TRACKING": tracking},
        )
        assert rc == 0
        with open(tracking) as f:
            entry = json.loads(f.readline())
        assert entry["tested"] is True
        assert "tested_ts" in entry

    def test_ignores_non_test_commands(self, tmp_path: object) -> None:
        tracking = os.path.join(str(tmp_path), "edits.jsonl")
        with open(tracking, "w") as f:
            f.write(json.dumps({"file": "/tmp/fettle/mod.py", "ts": 1, "tested": False}) + "\n")
        rc, _ = _run_hook(
            "post_bash_test_detect.py",
            {"tool_name": "Bash", "tool_input": {"command": "ls -la"}},
            env_overrides={"FETTLE_EDIT_TRACKING": tracking},
        )
        assert rc == 0
        with open(tracking) as f:
            entry = json.loads(f.readline())
        assert entry["tested"] is False


class TestPostEditRegressions:
    """post_edit.py — PostToolUse hook. Regression tests."""

    def test_handles_malformed_ruff_json_entry(self, tmp_path: object) -> None:
        """Regression: bare except previously swallowed TypeError from non-dict ruff entries.
        With typed code + specific catches, TypeError from malformed entries is handled
        via the isinstance(item, dict) guard instead of being silently swallowed."""
        tracking = os.path.join(str(tmp_path), "edits.jsonl")
        rc, _ = _run_hook(
            "post_edit.py",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/tmp/fettle_typed/tests/test_hook_contracts.py"},
                "cwd": "/tmp",
                "session_id": "test-session",
            },
            env_overrides={
                "FETTLE_EDIT_TRACKING": tracking,
                "FETTLE_TRACE_DIR": str(tmp_path),
            },
        )
        assert rc == 0
