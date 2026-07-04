"""Tests for Fettle plan gate — PreToolUse hook that blocks implementation edits without an active plan."""

import json
import os
import subprocess
import sys
import tempfile

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "plan_gate.py")

ENV_BASE = {
    **os.environ,
    "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""),
    "CLAUDE_PLUGIN_ROOT": PLUGIN_DIR,
}


def run_gate(stdin_data: dict, extra_env: dict | None = None):
    env = {**ENV_BASE, **(extra_env or {})}
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    return proc.stdout, proc.stderr, proc.returncode


# ─── Implementation files are blocked without a plan ────────────────────────

def test_py_file_blocked_without_plan():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/fettle/telegram-bridge.py"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert parsed.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def test_rs_file_blocked_without_plan():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "/data/logact/crates/logact-bus/src/sqlite.rs"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 2


def test_sh_file_blocked_without_plan():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/fettle/hooks/watchdog.sh"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 2


# ─── Allowed with an active plan ────────────────────────────────────────────

def test_py_file_allowed_with_plan():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    with open(marker, "w") as f:
        json.dump({"plan": "docs/plans/test.md", "approved": True, "ts": 1234567890}, f)
    stdout, stderr, rc = run_gate(
        {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/fettle/telegram-bridge.py"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


def test_plan_marker_not_approved_blocks():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    with open(marker, "w") as f:
        json.dump({"plan": "docs/plans/test.md", "approved": False, "ts": 1234567890}, f)
    stdout, stderr, rc = run_gate(
        {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/fettle/telegram-bridge.py"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 2


# ─── Non-implementation files always allowed ────────────────────────────────

def test_md_file_always_allowed():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "docs/plans/test.md"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


def test_json_file_always_allowed():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Edit", "tool_input": {"file_path": "/home/ubuntu/.claude/settings.json"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


def test_toml_file_always_allowed():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Edit", "tool_input": {"file_path": "/data/logact/Cargo.toml"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


def test_yml_file_always_allowed():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "/tmp/fettle/config.yml"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


def test_tmp_file_always_allowed():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "/tmp/test_script.py"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


def test_test_file_always_allowed():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "/tmp/fettle/tests/test_bridge.py"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


def test_test_prefix_file_always_allowed():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "/tmp/fettle/test_something.py"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


def test_memory_file_always_allowed():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "/home/ubuntu/.claude/projects/-home-ubuntu/memory/user_profile.md"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


# ─── Edge cases ─────────────────────────────────────────────────────────────

def test_malformed_stdin():
    env = {**ENV_BASE, "FETTLE_PLAN_MARKER": "/tmp/nonexistent.json"}
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input="NOT JSON",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert proc.returncode == 0


def test_missing_file_path():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Edit", "tool_input": {}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 0


def test_deny_output_has_reason():
    tmpdir = tempfile.mkdtemp()
    marker = os.path.join(tmpdir, "fettle-active-plan.json")
    stdout, stderr, rc = run_gate(
        {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/fettle/telegram-bridge.py"}},
        extra_env={"FETTLE_PLAN_MARKER": marker},
    )
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert "plan" in parsed.get("hookSpecificOutput", {}).get("permissionDecisionReason", "").lower()
