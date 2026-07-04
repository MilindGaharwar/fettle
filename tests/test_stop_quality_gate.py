"""Tests for Fettle Stop hook quality gate — cross-file analysis before response delivery."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "stop_quality_gate.py")
CARGO_BIN = os.path.expanduser(
    "~/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/cargo"
)

ENV_BASE = {
    **os.environ,
    "PATH": os.path.expanduser("~/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin")
    + ":"
    + os.path.expanduser("~/.local/bin")
    + ":"
    + os.environ.get("PATH", ""),
    "CLAUDE_PLUGIN_ROOT": PLUGIN_DIR,
}


def make_tracking_file(tmpdir, entries):
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
        timeout=120,
        env=env,
    )
    return proc.stdout, proc.stderr, proc.returncode


# --- Test 1: reads tracking file, extracts edited files ----------------------

def test_extracts_edited_files_from_tracking():
    """Stop hook reads tracking file and identifies 3 edited files."""
    tmpdir = tempfile.mkdtemp()
    try:
        for name in ("a.py", "b.py", "c.py"):
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("x = 1\n")
        tracking = make_tracking_file(tmpdir, [
            {"file": os.path.join(tmpdir, "a.py"), "ts": time.time(), "tool": "Edit", "tested": False},
            {"file": os.path.join(tmpdir, "b.py"), "ts": time.time(), "tool": "Write", "tested": False},
            {"file": os.path.join(tmpdir, "c.py"), "ts": time.time(), "tool": "Edit", "tested": False},
        ])
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": False},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        # No broken imports (all files are self-contained), so should pass
        assert rc == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --- Test 2: no files edited -> exit 0 immediately ---------------------------

def test_no_edits_exit_0():
    """If tracking file is empty or missing, exit 0."""
    tmpdir = tempfile.mkdtemp()
    try:
        tracking = os.path.join(tmpdir, "nonexistent.jsonl")
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": False},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        assert rc == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_empty_tracking_exit_0():
    tmpdir = tempfile.mkdtemp()
    try:
        tracking = make_tracking_file(tmpdir, [])
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": False},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        assert rc == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --- Test 3: edited .py with broken import -> exit 2 -------------------------

def test_broken_import_blocks():
    """a.py imports b, but b.py doesn't exist -> exit 2 with reason."""
    tmpdir = tempfile.mkdtemp()
    try:
        a_path = os.path.join(tmpdir, "a.py")
        with open(a_path, "w") as f:
            f.write("import b\nx = b.value\n")
        tracking = make_tracking_file(tmpdir, [
            {"file": a_path, "ts": time.time(), "tool": "Edit", "tested": False},
        ])
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": False},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        assert rc == 2
        parsed = json.loads(stdout.strip())
        assert parsed.get("decision") == "block"
        assert "b" in parsed.get("reason", "").lower()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_missing_symbol_blocks():
    """a.py does 'from b import foo', b.py has no foo -> exit 2."""
    tmpdir = tempfile.mkdtemp()
    try:
        a_path = os.path.join(tmpdir, "a.py")
        with open(a_path, "w") as f:
            f.write("from b import foo\n")
        with open(os.path.join(tmpdir, "b.py"), "w") as f:
            f.write("def bar():\n    return 1\n")
        tracking = make_tracking_file(tmpdir, [
            {"file": a_path, "ts": time.time(), "tool": "Edit", "tested": False},
        ])
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": False},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        assert rc == 2
        parsed = json.loads(stdout.strip())
        assert parsed.get("decision") == "block"
        assert "foo" in parsed.get("reason", "")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --- Test 4: edited .rs file with cargo check error -> exit 2 ----------------

@pytest.fixture
def skip_if_no_cargo():
    if not os.path.isfile(CARGO_BIN):
        pytest.skip("cargo not available")


def test_rs_cargo_check_error_blocks(skip_if_no_cargo):
    """Rust file with type error -> exit 2."""
    tmpdir = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmpdir, "src"))
        with open(os.path.join(tmpdir, "Cargo.toml"), "w") as f:
            f.write('[package]\nname = "test-crate"\nversion = "0.1.0"\nedition = "2021"\n')
        rs_path = os.path.join(tmpdir, "src", "lib.rs")
        with open(rs_path, "w") as f:
            f.write("pub fn add(a: i32, b: i32) -> String { a + b }\n")
        tracking = make_tracking_file(tmpdir, [
            {"file": rs_path, "ts": time.time(), "tool": "Edit", "tested": False},
        ])
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": False},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        assert rc == 2
        parsed = json.loads(stdout.strip())
        assert parsed.get("decision") == "block"
        assert "error" in parsed.get("reason", "").lower()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --- Test 5: convergence — stop_hook_active=true -> exit 0 -------------------

def test_convergence_allows_through():
    """When stop_hook_active=true, always exit 0 regardless of findings."""
    tmpdir = tempfile.mkdtemp()
    try:
        a_path = os.path.join(tmpdir, "a.py")
        with open(a_path, "w") as f:
            f.write("import nonexistent_module\n")
        tracking = make_tracking_file(tmpdir, [
            {"file": a_path, "ts": time.time(), "tool": "Edit", "tested": False},
        ])
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": True},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        assert rc == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --- Test 6: structured block report -----------------------------------------

def test_block_report_structure():
    """Block output has decision=block and detailed reason."""
    tmpdir = tempfile.mkdtemp()
    try:
        a_path = os.path.join(tmpdir, "a.py")
        with open(a_path, "w") as f:
            f.write("from missing_mod import something\n")
        tracking = make_tracking_file(tmpdir, [
            {"file": a_path, "ts": time.time(), "tool": "Edit", "tested": False},
        ])
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": False},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        assert rc == 2
        parsed = json.loads(stdout.strip())
        assert parsed["decision"] == "block"
        assert "reason" in parsed
        assert len(parsed["reason"]) > 20
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --- Clean edits pass through -------------------------------------------------

def test_clean_python_edits_pass():
    """Python files with valid imports pass through."""
    tmpdir = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmpdir, "b.py"), "w") as f:
            f.write("value = 42\n")
        a_path = os.path.join(tmpdir, "a.py")
        with open(a_path, "w") as f:
            f.write("import os\nfrom b import value\n")
        tracking = make_tracking_file(tmpdir, [
            {"file": a_path, "ts": time.time(), "tool": "Edit", "tested": False},
        ])
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": False},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        assert rc == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_non_python_non_rust_pass():
    """Non-Python, non-Rust files are not analyzed."""
    tmpdir = tempfile.mkdtemp()
    try:
        sh_path = os.path.join(tmpdir, "script.sh")
        with open(sh_path, "w") as f:
            f.write("#!/bin/bash\necho hello\n")
        tracking = make_tracking_file(tmpdir, [
            {"file": sh_path, "ts": time.time(), "tool": "Edit", "tested": False},
        ])
        stdout, stderr, rc = run_gate(
            {"stop_hook_active": False},
            extra_env={"FETTLE_EDIT_TRACKING": tracking, "FETTLE_PROJECT_ROOT": tmpdir},
        )
        assert rc == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
