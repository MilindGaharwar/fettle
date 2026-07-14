"""WP-112 — Commit Message Validation contract tests.

PreToolUse(Bash) hook that validates git commit messages for conventional format.
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
    """Run commit_message.py with a Bash command, return (rc, json, stderr)."""
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
        [sys.executable, os.path.join(SCRIPTS_DIR, "commit_message.py")],
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


class TestValidConventionalCommit:
    def test_valid_conventional_commit_passes(self) -> None:
        rc, out, _ = _run_hook('git commit -m "feat: add user login flow"')
        assert rc == 0
        assert out is None

    def test_valid_with_scope(self) -> None:
        rc, out, _ = _run_hook('git commit -m "fix(auth): resolve token expiry issue"')
        assert rc == 0
        assert out is None

    def test_valid_with_body(self) -> None:
        msg = "feat: add search\\n\\nImplements full-text search using pg_trgm."
        rc, out, _ = _run_hook(f'git commit -m "{msg}"')
        assert rc == 0
        assert out is None

    def test_co_authored_by_preserved(self) -> None:
        rc, out, _ = _run_hook(
            'git commit -m "fix: resolve null pointer\\n\\nCo-Authored-By: Claude <noreply@anthropic.com>"'
        )
        assert rc == 0
        assert out is None


class TestInvalidMessages:
    def test_missing_type_fails(self) -> None:
        rc, out, _ = _run_hook('git commit -m "add new feature"')
        assert rc == 0  # advisory default
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "conventional" in ctx.lower() or "type" in ctx.lower()

    def test_invalid_type_fails(self) -> None:
        rc, out, _ = _run_hook('git commit -m "yolo: break everything"')
        assert rc == 0
        assert out is not None

    def test_subject_too_long_fails(self) -> None:
        long_msg = "feat: " + "x" * 70  # > 72 chars
        rc, out, _ = _run_hook(f'git commit -m "{long_msg}"')
        assert rc == 0
        assert out is not None
        assert "72" in out["hookSpecificOutput"]["additionalContext"]

    def test_missing_colon_space_fails(self) -> None:
        rc, out, _ = _run_hook('git commit -m "feat add something"')
        assert rc == 0
        assert out is not None

    def test_period_at_end_fails(self) -> None:
        rc, out, _ = _run_hook('git commit -m "fix: resolve the bug."')
        assert rc == 0
        assert out is not None


class TestAllowsScope:
    def test_allows_scope_in_parens(self) -> None:
        rc, out, _ = _run_hook('git commit -m "refactor(db): simplify query builder"')
        assert rc == 0
        assert out is None

    def test_allows_breaking_change_marker(self) -> None:
        rc, out, _ = _run_hook('git commit -m "feat!: remove deprecated API"')
        assert rc == 0
        assert out is None


class TestAdvisoryMode:
    def test_advisory_warns_not_blocks(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text('[gates.commit_message]\nenabled = true\nmode = "advisory"\n')
        rc, out, _ = _run_hook('git commit -m "bad message"', cwd=str(proj))
        assert rc == 0
        assert out is not None


class TestEnforceMode:
    def test_enforce_blocks_bad_commit(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text('[gates.commit_message]\nenabled = true\nmode = "enforce"\n')
        rc, out, _ = _run_hook('git commit -m "bad message"', cwd=str(proj))
        assert rc == 2
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestHeredocMessage:
    def test_handles_heredoc_message(self) -> None:
        cmd = """git commit -m "$(cat <<'EOF'
feat: add user authentication

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
"""
        rc, out, _ = _run_hook(cmd)
        assert rc == 0
        assert out is None

    def test_handles_heredoc_bad_message(self) -> None:
        cmd = """git commit -m "$(cat <<'EOF'
just some changes

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
"""
        rc, out, _ = _run_hook(cmd)
        assert rc == 0
        assert out is not None


class TestIgnoresNonCommit:
    def test_ignores_non_commit_bash_commands(self) -> None:
        rc, out, _ = _run_hook("git status")
        assert rc == 0
        assert out is None

    def test_ignores_git_push(self) -> None:
        rc, out, _ = _run_hook("git push origin main")
        assert rc == 0
        assert out is None

    def test_ignores_non_git_commands(self) -> None:
        rc, out, _ = _run_hook("ls -la")
        assert rc == 0
        assert out is None

    def test_ignores_commit_amend(self) -> None:
        rc, out, _ = _run_hook("git commit --amend --no-edit")
        assert rc == 0
        assert out is None


class TestDisabled:
    def test_disabled_allows_all(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text("[gates.commit_message]\nenabled = false\n")
        rc, out, _ = _run_hook('git commit -m "terrible message"', cwd=str(proj))
        assert rc == 0
        assert out is None


class TestMalformedInput:
    def test_malformed_stdin_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "commit_message.py")],
            input="not json",
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0
