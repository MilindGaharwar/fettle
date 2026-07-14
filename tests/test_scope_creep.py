"""WP-114 — Scope Creep Warning contract tests.

PostToolUse(Write|Edit) hook that warns when too many files are modified in a session.
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
    file_path: str,
    session_id: str = "test-session",
    cwd: str | None = None,
    env_overrides: dict | None = None,
) -> tuple[int, dict | None, str]:
    """Run scope_creep.py, return (rc, json, stderr)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    input_data = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
        "cwd": cwd or "/tmp/test-project",
        "session_id": session_id,
    }
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "scope_creep.py")],
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


def _edit_n_files(n: int, state_dir: str, session_id: str = "test-session", cwd: str = "/tmp/proj") -> list[tuple[int, dict | None]]:
    """Simulate editing N distinct files."""
    results = []
    for i in range(n):
        rc, out, _ = _run_hook(
            f"/tmp/proj/file_{i}.py",
            session_id=session_id,
            cwd=cwd,
            env_overrides={"FETTLE_SCOPE_STATE_DIR": state_dir},
        )
        results.append((rc, out))
    return results


class TestNoWarningBelowThreshold:
    def test_no_warning_below_threshold(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _edit_n_files(10, state_dir)
        assert all(out is None for _, out in results)


class TestWarnsAtWarningThreshold:
    def test_warns_at_warning_threshold(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _edit_n_files(16, state_dir)
        # Should warn at file 15 (0-indexed: result[14])
        warned = [out for _, out in results if out is not None]
        assert len(warned) >= 1
        assert "Scope" in warned[0]["hookSpecificOutput"]["additionalContext"]


class TestCriticalAtCriticalThreshold:
    def test_critical_at_critical_threshold(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _edit_n_files(26, state_dir)
        warned = [out for _, out in results if out is not None]
        # Should have a critical warning mentioning 25
        critical = [w for w in warned if "25" in w["hookSpecificOutput"]["additionalContext"]]
        assert len(critical) >= 1


class TestResetsAfterCommit:
    def test_resets_after_commit(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        # Edit 14 files (below threshold)
        _edit_n_files(14, state_dir, session_id="reset-test")
        # Simulate a git commit via Bash tool
        env = os.environ.copy()
        env["FETTLE_SCOPE_STATE_DIR"] = state_dir
        input_data = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'feat: checkpoint'"},
            "cwd": "/tmp/proj",
            "session_id": "reset-test",
        }
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "scope_creep.py")],
            input=json.dumps(input_data),
            capture_output=True, text=True, timeout=10, env=env,
        )
        # Edit 14 more — should NOT trigger (count reset)
        results = _edit_n_files(14, state_dir, session_id="reset-test")
        assert all(out is None for _, out in results)


class TestCustomThresholds:
    def test_custom_thresholds_from_config(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text("[gates.scope_creep]\nenabled = true\nwarning_threshold = 3\ncritical_threshold = 5\n")
        state_dir = str(tmp_path / "state")
        os.makedirs(state_dir, exist_ok=True)

        results = []
        for i in range(4):
            rc, out, _ = _run_hook(
                f"/tmp/proj/file_{i}.py",
                session_id="custom",
                cwd=str(proj),
                env_overrides={"FETTLE_SCOPE_STATE_DIR": state_dir},
            )
            results.append((rc, out))
        warned = [out for _, out in results if out is not None]
        assert len(warned) >= 1


class TestDisabled:
    def test_disabled_config_skips_check(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text("[gates.scope_creep]\nenabled = false\n")
        state_dir = str(tmp_path / "state")
        os.makedirs(state_dir, exist_ok=True)

        results = []
        for i in range(20):
            rc, out, _ = _run_hook(
                f"/tmp/proj/file_{i}.py",
                session_id="disabled",
                cwd=str(proj),
                env_overrides={"FETTLE_SCOPE_STATE_DIR": state_dir},
            )
            results.append((rc, out))
        assert all(out is None for _, out in results)


class TestAdvisoryOnly:
    def test_advisory_only_never_blocks(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _edit_n_files(30, state_dir, session_id="no-block")
        assert all(rc == 0 for rc, _ in results)


class TestWarnsOnlyOnce:
    def test_warns_only_once_per_threshold_crossing(self, tmp_path) -> None:
        state_dir = str(tmp_path)
        results = _edit_n_files(20, state_dir, session_id="once-only")
        warned = [out for _, out in results if out is not None]
        # Should warn exactly once for crossing 15
        assert len(warned) == 1
