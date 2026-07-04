"""Tests for Fettle post_edit.py hook."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "post_edit.py")
FIXTURES = os.path.join(PLUGIN_DIR, "tests", "fixtures")

ENV_BASE = {
    **os.environ,
    "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""),
    "CLAUDE_PLUGIN_ROOT": PLUGIN_DIR,
}


def run_hook(stdin_data: dict, extra_env: dict | None = None, cwd: str | None = None):
    """Run post_edit.py with the given stdin JSON and return (stdout, stderr, returncode)."""
    env = {**ENV_BASE, **(extra_env or {})}
    if cwd and "FETTLE_TRACE_DIR" not in env:
        env["FETTLE_TRACE_DIR"] = os.path.join(cwd, ".fettle")
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=cwd,
    )
    return proc.stdout, proc.stderr, proc.returncode


# ─── 1. test_non_python_skipped ──────────────────────────────────────────────
def test_non_python_skipped():
    stdout, stderr, rc = run_hook({"tool_input": {"file_path": "/tmp/test.txt"}})
    assert rc == 0
    assert stdout == ""


# ─── 2. test_deleted_file_skipped ────────────────────────────────────────────
def test_deleted_file_skipped():
    stdout, stderr, rc = run_hook({"tool_input": {"file_path": "/tmp/nonexistent_xyz_12345.py"}})
    assert rc == 0
    assert stdout == ""


# ─── 3. test_advisory_mode_exit_0 ───────────────────────────────────────────
def test_advisory_mode_exit_0():
    fixture = os.path.join(FIXTURES, "violations", "bare_except.py")
    tmpdir = tempfile.mkdtemp()
    try:
        stdout, stderr, rc = run_hook(
            {"tool_input": {"file_path": fixture}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "advisory"},
            cwd=tmpdir,
        )
        assert rc == 0
        parsed = json.loads(stdout.strip())
        assert "additionalContext" in parsed.get("hookSpecificOutput", {})
        assert "BLE001" in parsed["hookSpecificOutput"]["additionalContext"]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 4. test_soft_mode_errors_exit_2 ────────────────────────────────────────
def test_soft_mode_errors_exit_2():
    fixture = os.path.join(FIXTURES, "violations", "bare_except.py")
    tmpdir = tempfile.mkdtemp()
    try:
        stdout, stderr, rc = run_hook(
            {"tool_input": {"file_path": fixture}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "soft"},
            cwd=tmpdir,
        )
        assert rc == 2
        parsed = json.loads(stdout.strip())
        assert parsed["decision"] == "block"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 5. test_output_json_valid ──────────────────────────────────────────────
def test_output_json_valid():
    fixture = os.path.join(FIXTURES, "violations", "bare_except.py")
    tmpdir = tempfile.mkdtemp()
    try:
        stdout, stderr, rc = run_hook(
            {"tool_input": {"file_path": fixture}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "soft"},
            cwd=tmpdir,
        )
        parsed = json.loads(stdout.strip())
        assert "decision" in parsed
        assert "reason" in parsed
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 6. test_malformed_stdin_handled ─────────────────────────────────────────
def test_malformed_stdin_handled():
    env = {**ENV_BASE}
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input="NOT VALID JSON {{{",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert proc.returncode == 0


# ─── 7. test_critical_directive_in_error_output ─────────────────────────────
def test_critical_directive_in_error_output():
    fixture = os.path.join(FIXTURES, "violations", "bare_except.py")
    tmpdir = tempfile.mkdtemp()
    try:
        stdout, stderr, rc = run_hook(
            {"tool_input": {"file_path": fixture}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "soft"},
            cwd=tmpdir,
        )
        assert rc == 2
        parsed = json.loads(stdout.strip())
        assert "CRITICAL SYSTEM DIRECTIVE" in parsed["reason"]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 8. test_jsonl_dedup_prevents_repeat ─────────────────────────────────────
def test_jsonl_dedup_prevents_repeat():
    fixture = os.path.join(FIXTURES, "violations", "bare_except.py")
    tmpdir = tempfile.mkdtemp()
    try:
        # First run — creates trace entries
        run_hook(
            {"tool_input": {"file_path": fixture}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "advisory"},
            cwd=tmpdir,
        )
        # Second run — should hit dedup
        run_hook(
            {"tool_input": {"file_path": fixture}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "advisory"},
            cwd=tmpdir,
        )

        trace_path = os.path.join(tmpdir, ".fettle", "trace.jsonl")
        assert os.path.isfile(trace_path)
        metrics = []
        with open(trace_path) as fh:
            for line in fh:
                entry = json.loads(line)
                if entry.get("type") == "metric":
                    metrics.append(entry)
        # The second metric should show dedup_suppressed > 0
        assert len(metrics) >= 2
        assert metrics[-1]["dedup_suppressed"] > 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 9. test_semgrep_skipped_for_non_scoped_path ────────────────────────────
def test_semgrep_skipped_for_non_scoped_path():
    fixture = os.path.join(FIXTURES, "violations", "bare_except.py")
    tmpdir = tempfile.mkdtemp()
    try:
        run_hook(
            {"tool_input": {"file_path": fixture}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "advisory"},
            cwd=tmpdir,
        )
        trace_path = os.path.join(tmpdir, ".fettle", "trace.jsonl")
        with open(trace_path) as fh:
            for line in fh:
                entry = json.loads(line)
                if entry.get("type") == "metric":
                    assert entry["semgrep_skipped"] is True
                    return
        pytest.fail("No metric entry found in trace.jsonl")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 10. test_semgrep_runs_for_scoped_path ───────────────────────────────────
def test_semgrep_runs_for_scoped_path(tmp_path):
    # Semgrep runs on all non-excluded .py files; /tmp paths are excluded,
    # so use a project dir outside the exclusion filter.
    proj = tmp_path / "workdir"
    proj.mkdir()
    test_file = str(proj / "health_semgrep_scope_test.py")
    try:
        with open(test_file, "w") as fh:
            fh.write("x = 1\n")

        trace_dir = str(tmp_path / "trace")
        os.makedirs(trace_dir, exist_ok=True)
        trace_path = os.path.join(trace_dir, "trace.jsonl")

        run_hook(
            {"tool_input": {"file_path": test_file}, "cwd": str(proj)},
            extra_env={"FETTLE_GATE_MODE": "advisory", "FETTLE_TRACE_DIR": trace_dir},
        )
        with open(trace_path) as fh:
            lines = fh.readlines()
        for line in reversed(lines):
            entry = json.loads(line)
            if entry.get("type") == "metric" and entry.get("file") == test_file:
                assert entry["semgrep_skipped"] is False, (
                    f"Semgrep should run on non-excluded .py file, got: {entry}"
                )
                return
        pytest.fail("No metric entry found for test file in trace.jsonl")
    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


# ─── 11. test_jsonl_rotation_at_10k_lines ───────────────────────────────────
def test_jsonl_rotation_at_10k_lines():
    tmpdir = tempfile.mkdtemp()
    try:
        trace_dir = os.path.join(tmpdir, ".fettle")
        os.makedirs(trace_dir)
        trace_path = os.path.join(trace_dir, "trace.jsonl")

        # Write 11000 dummy lines
        with open(trace_path, "w") as fh:
            for i in range(11000):
                fh.write(json.dumps({"type": "padding", "i": i}) + "\n")

        # Create a valid .py file to trigger the hook
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, "w") as fh:
            fh.write("x = 1\n")

        run_hook(
            {"tool_input": {"file_path": test_file}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "advisory"},
            cwd=tmpdir,
        )

        with open(trace_path) as fh:
            lines = fh.readlines()
        # Should be ~5000 (kept) + metric entry (+ possibly findings)
        assert len(lines) < 6000
        assert len(lines) >= 5000
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 12. test_escalation_ladder_after_3_repeats ─────────────────────────────
def test_escalation_ladder_after_3_repeats():
    fixture = os.path.join(FIXTURES, "violations", "bare_except.py")
    tmpdir = tempfile.mkdtemp()
    try:
        trace_dir = os.path.join(tmpdir, ".fettle")
        os.makedirs(trace_dir)
        trace_path = os.path.join(trace_dir, "trace.jsonl")

        # Pre-populate 3 consecutive finding entries for BLE001 with old timestamps
        # so they don't get dedup-suppressed (ts > 300s ago)
        old_ts = time.time() - 600
        for i in range(3):
            entry = {
                "type": "finding",
                "ts": old_ts + i,
                "session_id": "test",
                "file": fixture,
                "line": 3,
                "rule": "BLE001",
                "severity": "error",
                "message": "Do not catch blind exception: `Exception`",
            }
            with open(trace_path, "a") as fh:
                fh.write(json.dumps(entry) + "\n")

        stdout, stderr, rc = run_hook(
            {"tool_input": {"file_path": fixture}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "soft"},
            cwd=tmpdir,
        )
        assert rc == 2
        parsed = json.loads(stdout.strip())
        assert "MANDATORY IMMEDIATE FIX" in parsed["reason"]
        assert "ATTEMPT" in parsed["reason"]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 13. test_metric_entry_logged_to_jsonl ───────────────────────────────────
def test_metric_entry_logged_to_jsonl():
    fixture = os.path.join(FIXTURES, "clean.py")
    tmpdir = tempfile.mkdtemp()
    try:
        run_hook(
            {"tool_input": {"file_path": fixture}, "cwd": tmpdir},
            extra_env={"FETTLE_GATE_MODE": "advisory"},
            cwd=tmpdir,
        )
        trace_path = os.path.join(tmpdir, ".fettle", "trace.jsonl")
        assert os.path.isfile(trace_path)
        with open(trace_path) as fh:
            lines = fh.readlines()
        assert len(lines) >= 1
        last = json.loads(lines[-1])
        assert last["type"] == "metric"
        assert "hook_duration_ms" in last
        assert "ruff_duration_ms" in last
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 14. test_edit_tracking_appended ────────────────────────────────────────
def test_edit_tracking_appended():
    """PostToolUse hook appends edited file path to session tracking file."""
    fixture = os.path.join(FIXTURES, 'clean.py')
    tmpdir = tempfile.mkdtemp()
    tracking_path = os.path.join(tmpdir, 'fettle-edits.jsonl')
    try:
        run_hook(
            {'tool_input': {'file_path': fixture}, 'cwd': tmpdir},
            extra_env={'QUALITY_GATE_MODE': 'advisory', 'FETTLE_EDIT_TRACKING': tracking_path},
            cwd=tmpdir,
        )
        assert os.path.isfile(tracking_path), 'Tracking file was not created'
        with open(tracking_path) as fh:
            lines = fh.readlines()
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry['file'] == fixture
        assert entry['tested'] is False
        assert 'ts' in entry
        assert entry['tool'] in ('Write', 'Edit')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 15. test_edit_tracking_non_python_skipped ──────────────────────────────
def test_edit_tracking_non_python_skipped():
    """Non-Python files should not be appended by the Python hook."""
    tmpdir = tempfile.mkdtemp()
    tracking_path = os.path.join(tmpdir, 'fettle-edits.jsonl')
    try:
        run_hook(
            {'tool_input': {'file_path': '/tmp/test.txt'}},
            extra_env={'FETTLE_EDIT_TRACKING': tracking_path},
        )
        assert not os.path.isfile(tracking_path), 'Tracking file should not be created for non-Python files'
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 16. test_edit_tracking_multiple_appends ────────────────────────────────
def test_edit_tracking_multiple_appends():
    """Multiple edits append multiple entries to the same tracking file."""
    fixture = os.path.join(FIXTURES, 'clean.py')
    tmpdir = tempfile.mkdtemp()
    tracking_path = os.path.join(tmpdir, 'fettle-edits.jsonl')
    try:
        for _ in range(3):
            run_hook(
                {'tool_input': {'file_path': fixture}, 'cwd': tmpdir},
                extra_env={'QUALITY_GATE_MODE': 'advisory', 'FETTLE_EDIT_TRACKING': tracking_path},
                cwd=tmpdir,
            )
        with open(tracking_path) as fh:
            lines = fh.readlines()
        assert len(lines) == 3
        for line in lines:
            entry = json.loads(line)
            assert entry['file'] == fixture
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
