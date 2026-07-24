"""Tests for Fettle Shell PostToolUse hook — runs shellcheck on edited .sh files."""

import json
import os
import shutil
import subprocess
import tempfile

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "post_edit_shell.sh")

ENV_BASE = {
    **os.environ,
    "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""),
    "CLAUDE_PLUGIN_ROOT": PLUGIN_DIR,
}


def run_hook(stdin_data: dict, extra_env: dict | None = None):
    env = {**ENV_BASE, **(extra_env or {})}
    proc = subprocess.run(
        ["bash", SCRIPT],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return proc.stdout, proc.stderr, proc.returncode


@pytest.fixture(autouse=True)
def skip_if_no_shellcheck():
    if not shutil.which("shellcheck"):
        pytest.skip("shellcheck not available")


# ─── Non-.sh file is skipped ────────────────────────────────────────────────

def test_non_sh_file_skipped():
    stdout, stderr, rc = run_hook(
        {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/test.py"}, "cwd": "/tmp"},
    )
    assert rc == 0
    assert stdout.strip() == ""


# ─── Clean .sh file returns exit 0 ─────────────────────────────────────────

def test_clean_sh_file_exit_0():
    tmpdir = tempfile.mkdtemp()
    try:
        sh_path = os.path.join(tmpdir, "clean.sh")
        with open(sh_path, "w") as f:
            f.write('#!/bin/bash\nset -euo pipefail\necho "ok"\n')
        stdout, stderr, rc = run_hook(
            {"tool_name": "Write", "tool_input": {"file_path": sh_path}, "cwd": tmpdir},
        )
        assert rc == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── .sh file with violations returns findings ─────────────────────────────

def test_bad_sh_file_has_findings():
    tmpdir = tempfile.mkdtemp()
    try:
        sh_path = os.path.join(tmpdir, "bad.sh")
        with open(sh_path, "w") as f:
            f.write('#!/bin/bash\necho $UNQUOTED_VAR\ncd $DIR\n')
        stdout, stderr, rc = run_hook(
            {"tool_name": "Edit", "tool_input": {"file_path": sh_path}, "cwd": tmpdir},
        )
        assert rc == 0  # advisory mode, exit 0
        parsed = json.loads(stdout.strip())
        ctx = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "SC2086" in ctx or "SC" in ctx
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)



# ─── Edit tracking ─────────────────────────────────────────────────────────

def test_shell_hook_appends_tracking():
    """Shell PostToolUse hook appends .sh file to edit tracking."""
    tmpdir = tempfile.mkdtemp()
    try:
        sh_path = os.path.join(tmpdir, 'clean.sh')
        with open(sh_path, 'w') as f:
            f.write('#!/bin/bash' + chr(10) + 'set -euo pipefail' + chr(10) + 'echo "ok"' + chr(10))
        tracking_path = os.path.join(tmpdir, 'fettle-edits.jsonl')
        stdout, stderr, rc = run_hook(
            {'tool_name': 'Write', 'tool_input': {'file_path': sh_path}, 'cwd': tmpdir},
            extra_env={'FETTLE_EDIT_TRACKING': tracking_path},
        )
        assert os.path.isfile(tracking_path), 'Tracking file was not created by shell hook'
        with open(tracking_path) as fh:
            lines = fh.readlines()
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry['file'] == sh_path
        assert entry['tested'] is False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
