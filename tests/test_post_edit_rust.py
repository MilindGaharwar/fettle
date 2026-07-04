"""Tests for Fettle Rust PostToolUse hook — runs cargo check on edited .rs files."""

import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "post_edit_rust.sh")
CARGO_BIN = shutil.which("cargo") or os.path.expanduser("~/.cargo/bin/cargo")

ENV_BASE = {
    **os.environ,
    "PATH": os.path.expanduser("~/.cargo/bin")
            + ":" + os.path.expanduser("~/.local/bin")
            + ":" + os.environ.get("PATH", ""),
    "CLAUDE_PLUGIN_ROOT": PLUGIN_DIR,
}


def make_cargo_project(tmpdir, rust_code):
    """Create a minimal Cargo project with the given lib.rs content."""
    os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
    with open(os.path.join(tmpdir, "Cargo.toml"), "w") as f:
        f.write('[package]\nname = "test-crate"\nversion = "0.1.0"\nedition = "2021"\n')
    rs_path = os.path.join(tmpdir, "src", "lib.rs")
    with open(rs_path, "w") as f:
        f.write(rust_code)
    return rs_path


def run_hook(stdin_data: dict, extra_env: dict | None = None):
    env = {**ENV_BASE, **(extra_env or {})}
    proc = subprocess.run(
        ["bash", SCRIPT],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return proc.stdout, proc.stderr, proc.returncode


@pytest.fixture(autouse=True)
def skip_if_no_cargo():
    if not os.path.isfile(CARGO_BIN):
        pytest.skip("cargo not available")


# ─── Non-.rs file is skipped ────────────────────────────────────────────────

def test_non_rs_file_skipped():
    stdout, stderr, rc = run_hook(
        {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/test.py"}, "cwd": "/tmp"},
    )
    assert rc == 0
    assert stdout.strip() == ""


# ─── .rs file not in Cargo workspace is skipped ────────────────────────────

def test_rs_file_no_cargo_toml_skipped():
    tmpdir = tempfile.mkdtemp()
    rs_path = os.path.join(tmpdir, "orphan.rs")
    with open(rs_path, "w") as f:
        f.write("fn main() {}\n")
    stdout, stderr, rc = run_hook(
        {"tool_name": "Edit", "tool_input": {"file_path": rs_path}, "cwd": tmpdir},
    )
    assert rc == 0
    shutil.rmtree(tmpdir, ignore_errors=True)


# ─── Clean .rs file returns exit 0 ─────────────────────────────────────────

def test_clean_rs_file_exit_0():
    tmpdir = tempfile.mkdtemp()
    try:
        rs_path = make_cargo_project(tmpdir, "pub fn add(a: i32, b: i32) -> i32 { a + b }\n")
        stdout, stderr, rc = run_hook(
            {"tool_name": "Write", "tool_input": {"file_path": rs_path}, "cwd": tmpdir},
        )
        assert rc == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── Bad .rs file returns exit 2 with structured JSON ──────────────────────

def test_bad_rs_file_exit_2():
    tmpdir = tempfile.mkdtemp()
    try:
        rs_path = make_cargo_project(tmpdir, "pub fn add(a: i32, b: i32) -> String { a + b }\n")
        stdout, stderr, rc = run_hook(
            {"tool_name": "Edit", "tool_input": {"file_path": rs_path}, "cwd": tmpdir},
        )
        assert rc == 2
        parsed = json.loads(stdout.strip())
        assert "additionalContext" in parsed.get("hookSpecificOutput", {})
        assert "error" in parsed["hookSpecificOutput"]["additionalContext"].lower()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)



# ─── Edit tracking ─────────────────────────────────────────────────────────

def test_rust_hook_appends_tracking():
    """Rust PostToolUse hook appends .rs file to edit tracking."""
    tmpdir = tempfile.mkdtemp()
    try:
        rs_path = make_cargo_project(tmpdir, 'pub fn add(a: i32, b: i32) -> i32 { a + b }' + chr(10))
        tracking_path = os.path.join(tmpdir, 'fettle-edits.jsonl')
        stdout, stderr, rc = run_hook(
            {'tool_name': 'Write', 'tool_input': {'file_path': rs_path}, 'cwd': tmpdir},
            extra_env={'FETTLE_EDIT_TRACKING': tracking_path},
        )
        assert os.path.isfile(tracking_path), 'Tracking file was not created by Rust hook'
        with open(tracking_path) as fh:
            lines = fh.readlines()
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry['file'] == rs_path
        assert entry['tested'] is False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
