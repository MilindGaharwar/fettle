"""WP-110 — Destructive Command Guard contract tests.

PreToolUse(Bash) hook that blocks or warns on dangerous commands like
rm -rf, git reset --hard, git push --force, DROP TABLE, etc.
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
    command: str,
    cwd: str | None = None,
    env_overrides: dict | None = None,
) -> tuple[int, dict | None, str]:
    """Run destructive_guard.py with a Bash tool_input, return (rc, json, stderr)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    input_data = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": cwd or "/tmp/test-project",
        "session_id": "test-session",
    }
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "destructive_guard.py")],
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


class TestBlocksRmRf:
    def test_blocks_rm_rf(self) -> None:
        rc, out, _ = _run_hook("rm -rf /some/path")
        assert rc == 0  # advisory = warn, not block
        assert out is not None
        assert "Destructive" in out["hookSpecificOutput"]["additionalContext"]

    def test_blocks_rm_Rf(self) -> None:
        rc, out, _ = _run_hook("rm -Rf ./build")
        assert rc == 0
        assert out is not None

    def test_blocks_rm_force_recursive(self) -> None:
        rc, out, _ = _run_hook("rm --recursive --force /tmp/data")
        assert rc == 0
        assert out is not None


class TestBlocksGitResetHard:
    def test_blocks_git_reset_hard(self) -> None:
        rc, out, _ = _run_hook("git reset --hard")
        assert rc == 0
        assert out is not None
        assert "Destructive" in out["hookSpecificOutput"]["additionalContext"]

    def test_blocks_git_reset_hard_with_ref(self) -> None:
        rc, out, _ = _run_hook("git reset --hard origin/main")
        assert rc == 0
        assert out is not None


class TestBlocksGitPushForce:
    def test_blocks_git_push_force(self) -> None:
        rc, out, _ = _run_hook("git push --force")
        assert rc == 0
        assert out is not None

    def test_blocks_git_push_f(self) -> None:
        rc, out, _ = _run_hook("git push -f origin main")
        assert rc == 0
        assert out is not None


class TestBlocksDropTable:
    def test_blocks_drop_table(self) -> None:
        rc, out, _ = _run_hook("psql -c 'DROP TABLE users'")
        assert rc == 0
        assert out is not None

    def test_blocks_drop_database(self) -> None:
        rc, out, _ = _run_hook("mysql -e 'DROP DATABASE prod'")
        assert rc == 0
        assert out is not None

    def test_blocks_truncate_table(self) -> None:
        rc, out, _ = _run_hook("psql -c 'TRUNCATE TABLE orders'")
        assert rc == 0
        assert out is not None


class TestAllowsSafeCommands:
    def test_allows_safe_rm(self) -> None:
        rc, out, _ = _run_hook("rm file.txt")
        assert rc == 0
        assert out is None

    def test_allows_rm_single_file_force(self) -> None:
        rc, out, _ = _run_hook("rm -f file.txt")
        assert rc == 0
        assert out is None

    def test_allows_git_push_no_force(self) -> None:
        rc, out, _ = _run_hook("git push origin main")
        assert rc == 0
        assert out is None

    def test_allows_git_status(self) -> None:
        rc, out, _ = _run_hook("git status")
        assert rc == 0
        assert out is None

    def test_allows_ls(self) -> None:
        rc, out, _ = _run_hook("ls -la")
        assert rc == 0
        assert out is None


class TestHandlesQuotedCommands:
    def test_handles_quoted_rm_rf(self) -> None:
        rc, out, _ = _run_hook('bash -c "rm -rf /tmp/data"')
        assert rc == 0
        assert out is not None

    def test_handles_single_quoted(self) -> None:
        rc, out, _ = _run_hook("bash -c 'git reset --hard'")
        assert rc == 0
        assert out is not None


class TestHandlesPipeChains:
    def test_handles_pipe_to_rm(self) -> None:
        rc, out, _ = _run_hook("find . -name '*.tmp' | xargs rm -rf")
        assert rc == 0
        assert out is not None

    def test_pipe_with_safe_commands(self) -> None:
        rc, out, _ = _run_hook("cat file.txt | grep pattern | wc -l")
        assert rc == 0
        assert out is None


class TestHandlesSemicolonChaining:
    def test_semicolon_with_destructive(self) -> None:
        rc, out, _ = _run_hook("cd /tmp; rm -rf data")
        assert rc == 0
        assert out is not None

    def test_and_chaining(self) -> None:
        rc, out, _ = _run_hook("cd /tmp && git push --force")
        assert rc == 0
        assert out is not None


class TestAdvisoryWarnsNotBlocks:
    def test_advisory_warns_not_blocks(self, tmp_path) -> None:
        cfg = tmp_path / ".fettle.toml"
        cfg.write_text('[gates.destructive]\nenabled = true\nmode = "advisory"\n')
        rc, out, _ = _run_hook(
            "rm -rf /data",
            cwd=str(tmp_path),
        )
        assert rc == 0  # advisory = exit 0
        assert out is not None
        assert "additionalContext" in out.get("hookSpecificOutput", {})


class TestEnforceBlocks:
    def test_enforce_blocks(self, tmp_path) -> None:
        cfg = tmp_path / ".fettle.toml"
        cfg.write_text('[gates.destructive]\nenabled = true\nmode = "enforce"\n')
        rc, out, _ = _run_hook(
            "rm -rf /data",
            cwd=str(tmp_path),
        )
        assert rc == 2
        assert out is not None
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestAllowCommandsOverride:
    def test_allow_commands_override(self, tmp_path) -> None:
        cfg = tmp_path / ".fettle.toml"
        cfg.write_text(
            '[gates.destructive]\nenabled = true\n'
            'allow_commands = ["rm -rf node_modules"]\n'
        )
        rc, out, _ = _run_hook("rm -rf node_modules", cwd=str(tmp_path))
        assert rc == 0
        assert out is None

    def test_allow_commands_partial_no_match(self, tmp_path) -> None:
        cfg = tmp_path / ".fettle.toml"
        cfg.write_text(
            '[gates.destructive]\nenabled = true\n'
            'allow_commands = ["rm -rf node_modules"]\n'
        )
        rc, out, _ = _run_hook("rm -rf /important", cwd=str(tmp_path))
        assert rc == 0
        assert out is not None

    def test_allow_entry_does_not_forgive_chained_command(self, tmp_path) -> None:
        """An allow entry must not whitelist a chained command containing it (audit D7)."""
        cfg = tmp_path / ".fettle.toml"
        cfg.write_text(
            '[gates.destructive]\nenabled = true\n'
            'allow_commands = ["rm -rf node_modules"]\n'
        )
        rc, out, _ = _run_hook(
            "rm -rf node_modules && rm -rf /important", cwd=str(tmp_path)
        )
        assert rc == 0
        assert out is not None  # second segment still flagged

    def test_allow_entry_does_not_match_as_prefix(self, tmp_path) -> None:
        """An allow entry must not forgive a segment with extra arguments (audit D7)."""
        cfg = tmp_path / ".fettle.toml"
        cfg.write_text(
            '[gates.destructive]\nenabled = true\n'
            'allow_commands = ["rm -rf node_modules"]\n'
        )
        rc, out, _ = _run_hook("rm -rf node_modules /important", cwd=str(tmp_path))
        assert rc == 0
        assert out is not None


class TestNoFalsePositives:
    def test_does_not_false_positive_on_grep_containing_rm(self) -> None:
        rc, out, _ = _run_hook("grep -r 'rm -rf' docs/")
        assert rc == 0
        assert out is None

    def test_does_not_false_positive_on_echo(self) -> None:
        rc, out, _ = _run_hook("echo 'git reset --hard is dangerous'")
        assert rc == 0
        assert out is None

    def test_does_not_false_positive_on_comment(self) -> None:
        rc, out, _ = _run_hook("# rm -rf /everything")
        assert rc == 0
        assert out is None


class TestDisabled:
    def test_disabled_allows_all(self, tmp_path) -> None:
        cfg = tmp_path / ".fettle.toml"
        cfg.write_text("[gates.destructive]\nenabled = false\n")
        rc, out, _ = _run_hook("rm -rf /", cwd=str(tmp_path))
        assert rc == 0
        assert out is None


class TestMalformedInput:
    def test_malformed_stdin_exits_zero(self) -> None:
        env = os.environ.copy()
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "destructive_guard.py")],
            input="not json",
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert proc.returncode == 0

    def test_missing_command_exits_zero(self) -> None:
        env = os.environ.copy()
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "destructive_guard.py")],
            input=json.dumps({"tool_name": "Bash", "tool_input": {}}),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert proc.returncode == 0
