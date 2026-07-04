"""Tests for Fettle live test gate — Stop hook that blocks response if no tests were run after implementation edits."""

import json
import os
import subprocess
import sys
import tempfile
import time

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "live_test_gate.py")

ENV_BASE = {
    **os.environ,
    "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""),
    "CLAUDE_PLUGIN_ROOT": PLUGIN_DIR,
}


def make_tracking_file(tmpdir, entries):
    """Create a fettle edit tracking file."""
    path = os.path.join(tmpdir, "fettle-edits.jsonl")
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return path


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


# ─── No edits → always allow ────────────────────────────────────────────────

def test_no_edits_allows_through():
    """If no implementation files were edited, allow response."""
    tmpdir = tempfile.mkdtemp()
    tracking = os.path.join(tmpdir, "fettle-edits.jsonl")
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-1"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 0


def test_empty_tracking_file_allows():
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-2"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 0


# ─── Edits without tests → block ────────────────────────────────────────────

def test_impl_edit_without_test_blocks():
    """Implementation file edited but no test run → block."""
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [
        {"file": "/tmp/fettle/telegram-bridge.py", "ts": time.time(), "tool": "Edit", "tested": False},
    ])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-3"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert "test" in parsed.get("reason", "").lower()


def test_rs_edit_without_test_blocks():
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [
        {"file": "/data/logact/crates/logact-bus/src/sqlite.rs", "ts": time.time(), "tool": "Write", "tested": False},
    ])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-4"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 2


# ─── Edits with tests → allow ───────────────────────────────────────────────

def test_impl_edit_with_test_allows():
    """Implementation file edited and tested → allow."""
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [
        {"file": "/tmp/fettle/telegram-bridge.py", "ts": time.time(), "tool": "Edit", "tested": True},
    ])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-5"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 0


# ─── Non-implementation edits → always allow ────────────────────────────────

def test_md_edit_without_test_allows():
    """Markdown file edits don't require tests."""
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [
        {"file": "docs/plans/test.md", "ts": time.time(), "tool": "Write", "tested": False},
    ])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-6"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 0


def test_tmp_edit_without_test_allows():
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [
        {"file": "/tmp/throwaway.py", "ts": time.time(), "tool": "Write", "tested": False},
    ])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-7"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 0


# ─── Convergence ────────────────────────────────────────────────────────────

def test_stop_hook_active_allows_through():
    """When stop_hook_active=true, always allow (convergence limit)."""
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [
        {"file": "/tmp/fettle/telegram-bridge.py", "ts": time.time(), "tool": "Edit", "tested": False},
    ])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": True, "session_id": "test-8"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 0


# ─── Mixed edits ────────────────────────────────────────────────────────────

def test_mixed_impl_and_doc_only_impl_needs_test():
    """If both impl and doc files edited, only impl files need tests."""
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [
        {"file": "docs/plans/test.md", "ts": time.time(), "tool": "Write", "tested": False},
        {"file": "/tmp/fettle/telegram-bridge.py", "ts": time.time(), "tool": "Edit", "tested": False},
    ])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-9"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 2


def test_all_impl_tested_allows():
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [
        {"file": "docs/plans/test.md", "ts": time.time(), "tool": "Write", "tested": False},
        {"file": "/tmp/fettle/telegram-bridge.py", "ts": time.time(), "tool": "Edit", "tested": True},
    ])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-10"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 0


# ─── Edge cases ─────────────────────────────────────────────────────────────

def test_malformed_stdin():
    env = {**ENV_BASE, "FETTLE_EDIT_TRACKING": "/tmp/nonexistent.jsonl"}
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input="GARBAGE",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert proc.returncode == 0


def test_block_output_lists_untested_files():
    """Block message lists which files need testing."""
    tmpdir = tempfile.mkdtemp()
    tracking = make_tracking_file(tmpdir, [
        {"file": "/tmp/fettle/telegram-bridge.py", "ts": time.time(), "tool": "Edit", "tested": False},
        {"file": "/data/logact/crates/logact-bus/src/sqlite.rs", "ts": time.time(), "tool": "Write", "tested": False},
    ])
    stdout, stderr, rc = run_gate(
        {"stop_hook_active": False, "session_id": "test-11"},
        extra_env={"FETTLE_EDIT_TRACKING": tracking},
    )
    assert rc == 2
    parsed = json.loads(stdout.strip())
    reason = parsed.get("reason", "")
    assert "telegram-bridge.py" in reason
    assert "sqlite.rs" in reason
