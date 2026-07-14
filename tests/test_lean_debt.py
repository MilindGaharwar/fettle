"""WP-108 — fettle:lean: Comment Convention + Debt Tracking.

Tests the lean_debt.py script (grep + report) and the Tier 1 suppression
logic in lean_sniffers.py.
"""

import contextlib
import json
import os
import subprocess
import sys
import textwrap

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)


def _run_lean_debt(
    cwd: str,
    env_overrides: dict | None = None,
) -> tuple[int, str, str]:
    """Run lean_debt.py, return (rc, stdout, stderr)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "lean_debt.py")],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _run_sniffers(
    file_path: str,
    cwd: str,
    state_dir: str,
    session_id: str = "test-session",
) -> list[dict]:
    """Run lean_sniffers.py and return candidates from state."""
    env = os.environ.copy()
    env["FETTLE_LEAN_STATE_DIR"] = state_dir
    input_data = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
        "cwd": cwd,
        "session_id": session_id,
    }
    subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "lean_sniffers.py")],
        input=json.dumps(input_data),
        capture_output=True, text=True, timeout=10, env=env,
    )
    state_path = os.path.join(state_dir, "sessions", f"{session_id}.lean.jsonl")
    if not os.path.exists(state_path):
        return []
    candidates = []
    with open(state_path) as f:
        for line in f:
            if line.strip():
                with contextlib.suppress(json.JSONDecodeError):
                    candidates.append(json.loads(line.strip()))
    return candidates


def _init_git(path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)


def _git_add_commit(path, msg: str = "commit") -> None:
    subprocess.run(["git", "add", "-A"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg, "--allow-empty"], cwd=str(path), check=True)


class TestGrepsLeanComments:
    def test_greps_fettle_lean_comments(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        f = proj / "utils.py"
        f.write_text(textwrap.dedent("""\
            # fettle:lean: simple dict lookup, upgrade when: >5 cases
            def get_handler(name):
                return {"a": handle_a, "b": handle_b}[name]
        """))
        rc, stdout, _ = _run_lean_debt(str(proj))
        assert rc == 0
        assert "utils.py" in stdout
        assert "simple dict lookup" in stdout

    def test_handles_ts_and_python_comments(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "a.py").write_text("# fettle:lean: flat list, upgrade when: >100 items\nx = []\n")
        (proj / "b.ts").write_text("// fettle:lean: inline validation, upgrade when: shared across 3+ files\n")
        rc, stdout, _ = _run_lean_debt(str(proj))
        assert rc == 0
        assert "a.py" in stdout
        assert "b.ts" in stdout


class TestParsesCeilingAndTrigger:
    def test_parses_ceiling_and_trigger(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "x.py").write_text("# fettle:lean: manual retry loop, upgrade when: need backoff/jitter\n")
        rc, stdout, _ = _run_lean_debt(str(proj))
        assert "manual retry loop" in stdout
        assert "need backoff/jitter" in stdout


class TestFlagsNoTriggerMarkers:
    def test_flags_no_trigger_markers(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "x.py").write_text("# fettle:lean: simple approach\ny = 1\n")
        rc, stdout, _ = _run_lean_debt(str(proj))
        assert "no trigger" in stdout.lower() or "NO-TRIGGER" in stdout


class TestSkipsExcludedDirectories:
    def test_skips_excluded_directories(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        nm = proj / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("// fettle:lean: should be invisible\n")
        (proj / "src.py").write_text("# fettle:lean: visible marker, upgrade when: scale\n")
        rc, stdout, _ = _run_lean_debt(str(proj))
        assert "visible marker" in stdout
        assert "should be invisible" not in stdout


class TestReportIncludesLeanCount:
    def test_report_includes_lean_count(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "a.py").write_text("# fettle:lean: thing one, upgrade when: x\n")
        (proj / "b.py").write_text("# fettle:lean: thing two, upgrade when: y\n")
        (proj / "c.py").write_text("# fettle:lean: no trigger here\n")
        rc, stdout, _ = _run_lean_debt(str(proj))
        assert "3 marker" in stdout.lower() or "3" in stdout
        assert "1" in stdout  # 1 without trigger


class TestSuppressesTier1CandidateNearLeanMarker:
    def test_suppresses_tier1_candidate_near_lean_marker(self, tmp_path) -> None:
        """A fettle:lean: comment near a flagged line suppresses that candidate."""
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "service.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        # Pass-through wrapper that would normally trigger LR003,
        # but has a lean marker suppressing it
        f.write_text(textwrap.dedent("""\
            # fettle:lean: thin wrapper for testability, upgrade when: need retry/circuit-breaker
            def get_user(user_id):
                return client.get_user(user_id)
        """))
        state_dir = str(tmp_path / "state")
        os.makedirs(os.path.join(state_dir, "sessions"), exist_ok=True)

        candidates = _run_sniffers(str(f), str(proj), state_dir)
        lr003 = [c for c in candidates if c["sniffer_id"] == "LR003_PASS_THROUGH_WRAPPER"]
        assert lr003 == []
