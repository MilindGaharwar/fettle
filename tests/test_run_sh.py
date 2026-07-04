"""Tests for scripts/run.sh — the interpreter launcher every hook depends on.

Pins the contract: resolve a Python >= 3.11 (FETTLE_PYTHON override first),
forward arguments, and when no interpreter exists fail loud on stderr but
exit 0 — a hook must never hard-fail the session over environment issues.
"""

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUN_SH = os.path.join(PLUGIN_DIR, "scripts", "run.sh")

MODERN_PYTHON = sys.executable if sys.version_info >= (3, 11) else None


def run_launcher(target: str, *args: str, env: dict):
    # Absolute bash path: the no-interpreter test strips PATH bare.
    proc = subprocess.run(
        ["/bin/bash", RUN_SH, target, *args],
        capture_output=True, text=True, timeout=60, env=env,
    )
    return proc.stdout, proc.stderr, proc.returncode


@pytest.mark.skipif(MODERN_PYTHON is None, reason="test env python < 3.11")
def test_fettle_python_override_runs_target_with_args():
    stdout, stderr, rc = run_launcher(
        "quality_scan.py", "--help",
        env={**os.environ, "FETTLE_PYTHON": MODERN_PYTHON},
    )
    assert rc == 0
    assert "--baseline" in stdout  # argparse usage: args reached the target


@pytest.mark.skipif(MODERN_PYTHON is None, reason="test env python < 3.11")
def test_invalid_fettle_python_falls_back():
    """A broken override must not kill the launcher; discovery continues."""
    shim_dir = tempfile.mkdtemp()
    try:
        os.symlink(MODERN_PYTHON, os.path.join(shim_dir, "python3"))
        stdout, stderr, rc = run_launcher(
            "quality_scan.py", "--help",
            env={
                **os.environ,
                "FETTLE_PYTHON": "/nonexistent/python",
                "PATH": shim_dir + ":" + os.environ.get("PATH", ""),
            },
        )
        assert rc == 0
        assert "--baseline" in stdout
    finally:
        shutil.rmtree(shim_dir, ignore_errors=True)


def test_no_interpreter_is_loud_but_exits_0():
    """No usable Python anywhere: readable stderr, exit 0, target never runs."""
    shim_dir = tempfile.mkdtemp()
    fake_home = tempfile.mkdtemp()
    try:
        # Minimal PATH: the utilities run.sh itself needs, plus a python3
        # whose version check always fails.
        for tool in ("dirname", "ls", "sort", "tail"):
            real = shutil.which(tool)
            assert real, f"{tool} missing from test environment"
            os.symlink(real, os.path.join(shim_dir, tool))
        fake_python = os.path.join(shim_dir, "python3")
        with open(fake_python, "w") as fh:
            fh.write("#!/bin/sh\nexit 1\n")
        os.chmod(fake_python, 0o755)

        stdout, stderr, rc = run_launcher(
            "quality_scan.py", "--help",
            env={"PATH": shim_dir, "HOME": fake_home},
        )
        assert rc == 0
        assert "no Python >= 3.11" in stderr
        assert "FETTLE_PYTHON" in stderr  # tells the user how to fix it
        assert "--baseline" not in stdout  # target must not have run
    finally:
        shutil.rmtree(shim_dir, ignore_errors=True)
        shutil.rmtree(fake_home, ignore_errors=True)
