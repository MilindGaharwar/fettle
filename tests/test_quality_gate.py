"""Specs for the consolidated quality_gate.py (plan / tests / stamping gates).

Replaces the pre-consolidation test_plan_gate.py and test_live_test_gate.py,
which subprocess-invoked scripts whose logic now lives inside quality_gate.py.
All gates here are opt-in via .fettle.toml; state is per-session.
"""

import json
import os
import subprocess
import sys
import time

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "quality_gate.py")


def run_gate(payload: dict, state_dir: str):
    env = {**os.environ, "FETTLE_STATE_DIR": state_dir}
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    parsed = None
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            parsed = None
    return proc.returncode, parsed, proc.stderr


def edit_payload(proj, file_path, session="s1", event="PreToolUse", tool="Edit"):
    return {
        "tool_name": tool,
        "tool_input": {"file_path": file_path, "content": "x = 1\n"},
        "cwd": str(proj),
        "hook_event": event,
        "session_id": session,
    }


@pytest.fixture()
def proj(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    return p


@pytest.fixture()
def state(tmp_path):
    return str(tmp_path / "state")


def enable(proj, *gates, extra=""):
    body = "".join(f"[gates.{g}]\nenabled = true\n" for g in gates)
    (proj / ".fettle.toml").write_text(body + extra)


def seed_edits(state, session, entries):
    sdir = os.path.join(state, session)
    os.makedirs(sdir, exist_ok=True)
    with open(os.path.join(sdir, "edits.jsonl"), "w") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
    return sdir


# ─── Contract basics ─────────────────────────────────────────────────────────

def test_malformed_stdin_exits_zero(state):
    proc = subprocess.run(
        [sys.executable, SCRIPT], input="not json", capture_output=True,
        text=True, timeout=15, env={**os.environ, "FETTLE_STATE_DIR": state},
    )
    assert proc.returncode == 0


def test_block_output_shape(proj, state):
    enable(proj, "plan", extra="[gates.plan.x]\n")  # plan gate, default threshold 3
    for i in range(2):
        run_gate(edit_payload(proj, f"src/m{i}.py", session="shape"), state)
    rc, parsed, _ = run_gate(edit_payload(proj, "src/m2.py", session="shape"), state)
    assert rc == 2
    assert parsed["decision"] == "block"
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert parsed["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


# ─── Plan gate (from plan_gate.py, consolidated) ─────────────────────────────

def test_plan_gate_disabled_by_default(proj, state):
    for i in range(5):
        rc, _, _ = run_gate(edit_payload(proj, f"src/m{i}.py", session="off"), state)
        assert rc == 0


def test_plan_gate_blocks_at_threshold(proj, state):
    enable(proj, "plan")
    rcs = [run_gate(edit_payload(proj, f"src/m{i}.py", session="thr"), state)[0] for i in range(3)]
    assert rcs[:2] == [0, 0]
    assert rcs[2] == 2


def test_plan_gate_custom_threshold(proj, state):
    (proj / ".fettle.toml").write_text("[gates.plan]\nenabled = true\nthreshold = 2\n")
    rcs = [run_gate(edit_payload(proj, f"src/m{i}.py", session="thr2"), state)[0] for i in range(2)]
    assert rcs == [0, 2]


def test_recent_plan_allows_multi_file_edits(proj, state):
    enable(proj, "plan")
    docs = proj / "docs"
    docs.mkdir()
    (docs / "feature-plan.md").write_text("# plan\n")  # fresh mtime
    for i in range(5):
        rc, _, _ = run_gate(edit_payload(proj, f"src/m{i}.py", session="planned"), state)
        assert rc == 0


def test_stale_plan_does_not_count(proj, state):
    enable(proj, "plan")
    docs = proj / "docs"
    docs.mkdir()
    plan = docs / "old-plan.md"
    plan.write_text("# plan\n")
    stale = time.time() - 7200  # 2h old vs 1h max_age
    os.utime(plan, (stale, stale))
    rcs = [run_gate(edit_payload(proj, f"src/m{i}.py", session="stale"), state)[0] for i in range(3)]
    assert rcs[2] == 2


@pytest.mark.parametrize("path", [
    "README.md", "config.toml", "data.json", "notes.txt",         # exempt extensions
    "tests/test_mod.py", "src/mod.test.ts", "conftest.py",        # test files
    "alembic/versions/abc_migration.py",                          # exempt path segment
])
def test_plan_gate_exemptions(proj, state, path):
    enable(proj, "plan")
    session = f"ex-{abs(hash(path)) % 10_000}"
    # exempt files never increment the counter, so even many edits stay clean
    for _ in range(4):
        rc, _, _ = run_gate(edit_payload(proj, path, session=session), state)
        assert rc == 0, path


def test_plan_gate_warns_not_blocks_on_post(proj, state):
    enable(proj, "plan")
    for i in range(2):
        run_gate(edit_payload(proj, f"src/m{i}.py", session="post"), state)
    rc, _, stderr = run_gate(
        edit_payload(proj, "src/m2.py", session="post", event="PostToolUse"), state
    )
    assert rc == 0
    assert "PLANNING" in stderr


def test_plan_gate_sessions_isolated(proj, state):
    enable(proj, "plan")
    for i in range(2):
        run_gate(edit_payload(proj, f"src/m{i}.py", session="a"), state)
    # a different session starts from zero
    rc, _, _ = run_gate(edit_payload(proj, "src/m9.py", session="b"), state)
    assert rc == 0


# ─── Stop gate: untested implementation files (from live_test_gate.py) ──────

def stop_payload(proj, session):
    return {
        "tool_name": "", "tool_input": {}, "cwd": str(proj),
        "hook_event": "Stop", "session_id": session,
    }


def test_stop_gate_disabled_by_default(proj, state):
    seed_edits(state, "sd", [{"file": str(proj / "src/mod.py"), "ts": 1, "tested": False}])
    rc, _, _ = run_gate(stop_payload(proj, "sd"), state)
    assert rc == 0


def test_stop_blocks_untested_implementation(proj, state):
    enable(proj, "tests")
    seed_edits(state, "su", [{"file": str(proj / "src/mod.py"), "ts": 1, "tested": False}])
    rc, parsed, _ = run_gate(stop_payload(proj, "su"), state)
    assert rc == 2
    assert "mod.py" in parsed["reason"]


def test_stop_passes_when_tested(proj, state):
    enable(proj, "tests")
    seed_edits(state, "st", [{"file": str(proj / "src/mod.py"), "ts": 1, "tested": True}])
    rc, _, _ = run_gate(stop_payload(proj, "st"), state)
    assert rc == 0


def test_stop_ignores_non_implementation_files(proj, state):
    enable(proj, "tests")
    seed_edits(state, "sn", [
        {"file": str(proj / "README.md"), "ts": 1, "tested": False},
        {"file": str(proj / "tests/test_x.py"), "ts": 1, "tested": False},
    ])
    rc, _, _ = run_gate(stop_payload(proj, "sn"), state)
    assert rc == 0


def test_stop_flags_frontend_without_browser_test(proj, state):
    enable(proj, "tests")
    seed_edits(state, "sf", [{"file": str(proj / "frontend/src/pages/App.tsx"), "ts": 1, "tested": True}])
    rc, parsed, _ = run_gate(stop_payload(proj, "sf"), state)
    assert rc == 2
    assert "BROWSER" in parsed["reason"]


def test_stop_passes_frontend_with_fresh_browser_marker(proj, state):
    enable(proj, "tests")
    sdir = seed_edits(state, "sb", [{"file": str(proj / "frontend/src/pages/App.tsx"), "ts": 1, "tested": True}])
    open(os.path.join(sdir, "browser-tested.timestamp"), "w").close()
    rc, _, _ = run_gate(stop_payload(proj, "sb"), state)
    assert rc == 0


# ─── Bash: test stamping (from post_bash_test_detect.py) ─────────────────────

def bash_payload(proj, command, session):
    return {
        "tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(proj),
        "hook_event": "PostToolUse", "session_id": session,
    }


def _entries(state, session):
    path = os.path.join(state, session, "edits.jsonl")
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_pytest_command_stamps_entries_tested(proj, state):
    seed_edits(state, "tp", [{"file": str(proj / "src/mod.py"), "ts": 1, "tested": False}])
    rc, _, _ = run_gate(bash_payload(proj, "uv run pytest tests/ -q", "tp"), state)
    assert rc == 0
    entry = _entries(state, "tp")[0]
    assert entry["tested"] is True
    assert "tested_ts" in entry


def test_non_test_command_does_not_stamp(proj, state):
    seed_edits(state, "tn", [{"file": str(proj / "src/mod.py"), "ts": 1, "tested": False}])
    run_gate(bash_payload(proj, "ls -la", "tn"), state)
    assert _entries(state, "tn")[0]["tested"] is False


def test_playwright_command_touches_browser_marker(proj, state):
    seed_edits(state, "tb", [{"file": str(proj / "src/mod.py"), "ts": 1, "tested": False}])
    run_gate(bash_payload(proj, "npx playwright test", "tb"), state)
    assert os.path.isfile(os.path.join(state, "tb", "browser-tested.timestamp"))


def test_commit_warning_when_untested(proj, state):
    enable(proj, "tests")
    seed_edits(state, "tc", [{"file": str(proj / "src/mod.py"), "ts": 1, "tested": False}])
    rc, _, stderr = run_gate(bash_payload(proj, "git commit -m x", "tc"), state)
    assert rc == 0  # warning, never a block
    assert "TESTS" in stderr
