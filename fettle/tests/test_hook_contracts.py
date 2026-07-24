"""Hook stdin/stdout contract tests for the standalone gate scripts.

Plan / live-test / test-stamping behavior is consolidated inside
quality_gate.py and specced in tests/test_quality_gate.py — this file covers
the scripts that remain standalone: mcp_gate, mcp_trust_gate, post_edit.
"""

import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_hook(script: str, input_data: dict, env_overrides: dict | None = None) -> tuple[int, dict | None]:
    """Run a hook script, return (exit_code, parsed_json_output_or_None)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, script)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    output = None
    if proc.stdout.strip():
        try:
            output = json.loads(proc.stdout)
        except json.JSONDecodeError:
            output = None
    return proc.returncode, output




class TestMcpTrustGate:
    """mcp_trust_gate.py — allowlist-based package trust gate (opt-in)."""

    def _setup(self, tmp_path) -> tuple[str, dict]:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".fettle.toml").write_text("[gates.mcp_trust]\nenabled = true\n")
        allowlist = tmp_path / "allowlist.json"
        allowlist.write_text(json.dumps({"packages": {}, "registries_blocked": [], "protected_paths": []}))
        return str(proj), {"MCP_ALLOWLIST_PATH": str(allowlist)}

    def test_blocks_unpinned_pip_install(self, tmp_path) -> None:
        cwd, env = self._setup(tmp_path)
        rc, out = _run_hook(
            "mcp_trust_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "pip install requests"}, "cwd": cwd},
            env_overrides=env,
        )
        assert rc == 2
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_allows_harmless_bash(self, tmp_path) -> None:
        cwd, env = self._setup(tmp_path)
        rc, _ = _run_hook(
            "mcp_trust_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "ls -la"}, "cwd": cwd},
            env_overrides=env,
        )
        assert rc == 0

    def test_disabled_by_default(self, tmp_path) -> None:
        proj = tmp_path / "bare"
        proj.mkdir()
        rc, _ = _run_hook(
            "mcp_trust_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "pip install anything"}, "cwd": str(proj)},
        )
        assert rc == 0


class TestPostEditRegressions:
    """post_edit.py — PostToolUse hook. Regression + contract tests."""

    def test_handles_malformed_ruff_json_entry(self, tmp_path) -> None:
        """Regression: non-dict ruff entries must be skipped, not crash or block."""
        tracking = os.path.join(str(tmp_path), "edits.jsonl")
        rc, _ = _run_hook(
            "post_edit.py",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/tmp/fettle_typed/tests/test_hook_contracts.py"},
                "cwd": str(tmp_path),
                "session_id": "test-session",
            },
            env_overrides={
                "FETTLE_EDIT_TRACKING": tracking,
                "FETTLE_TRACE_DIR": str(tmp_path),
            },
        )
        assert rc == 0

    def test_non_python_file_ignored(self, tmp_path) -> None:
        rc, out = _run_hook(
            "post_edit.py",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(tmp_path / "notes.md")},
                "cwd": str(tmp_path),
                "session_id": "t",
            },
            env_overrides={"FETTLE_TRACE_DIR": str(tmp_path)},
        )
        assert rc == 0
        assert out is None

    def test_malformed_stdin_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "post_edit.py")],
            input="not json at all",
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 0

    def test_lint_gate_disabled_via_config(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".fettle.toml").write_text("[gates.lint]\nenabled = false\n")
        bad = proj / "bad.py"
        bad.write_text("try:\n    x = 1\nexcept:\n    pass\n")
        rc, out = _run_hook(
            "post_edit.py",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(bad)},
                "cwd": str(proj),
                "session_id": "t",
            },
        )
        assert rc == 0
        assert out is None
