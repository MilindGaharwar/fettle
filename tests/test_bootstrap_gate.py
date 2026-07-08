"""Bootstrap gate: CI must be set up before development (CI enforcement WP-3)."""

import json
import os
import subprocess
import sys
import tempfile

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PLUGIN_DIR, "scripts"))

from quality_gate import scan_bootstrap  # noqa: E402

WORKFLOW = os.path.join(".github", "workflows", "fettle.yml")


def _repo(with_workflow: bool) -> str:
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    if with_workflow:
        os.makedirs(os.path.join(d, ".github", "workflows"))
        with open(os.path.join(d, WORKFLOW), "w") as f:
            f.write("name: Fettle CI\n")
    return d


def test_impl_edit_without_workflow_fires():
    d = _repo(with_workflow=False)
    findings = scan_bootstrap(os.path.join(d, "app.py"), d)
    assert findings
    assert "fettle ci init" in findings[0]


def test_impl_edit_with_workflow_is_clean():
    d = _repo(with_workflow=True)
    assert scan_bootstrap(os.path.join(d, "app.py"), d) == []


def test_non_impl_files_exempt():
    d = _repo(with_workflow=False)
    assert scan_bootstrap(os.path.join(d, "README.md"), d) == []
    assert scan_bootstrap(os.path.join(d, "test_app.py"), d) == []
    assert scan_bootstrap(os.path.join(d, "config.toml"), d) == []


def test_regression_scratch_file_outside_cwd_exempt():
    """Regression — the gate must not nag scratch/experiment files or block
    unrelated work: a file outside the project root is never gated."""
    d = _repo(with_workflow=False)
    assert scan_bootstrap("/tmp/experiment.py", d) == []


def _run_gate(payload: dict, cwd: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, os.path.join(PLUGIN_DIR, "scripts", "quality_gate.py")],
        input=json.dumps(payload), capture_output=True, text=True, cwd=cwd,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _write_config(root: str, mode: str) -> None:
    with open(os.path.join(root, ".fettle.toml"), "w") as f:
        f.write(f'[gates.ci_bootstrap]\nenabled = true\nmode = "{mode}"\n')


def test_integration_strict_blocks_without_workflow():
    d = _repo(with_workflow=False)
    _write_config(d, "strict")
    payload = {
        "tool_name": "Write", "hook_event": "PreToolUse", "cwd": d,
        "session_id": "t1",
        "tool_input": {"file_path": os.path.join(d, "app.py"), "content": "x = 1\n"},
    }
    rc, out = _run_gate(payload, d)
    assert rc == 2
    assert "fettle ci init" in out


def test_integration_regression_advisory_never_blocks():
    """Regression — advisory mode informs, never blocks (exit != 2)."""
    d = _repo(with_workflow=False)
    _write_config(d, "advisory")
    payload = {
        "tool_name": "Write", "hook_event": "PreToolUse", "cwd": d,
        "session_id": "t2",
        "tool_input": {"file_path": os.path.join(d, "app.py"), "content": "x = 1\n"},
    }
    rc, out = _run_gate(payload, d)
    assert rc == 0


def test_integration_workflow_present_allows():
    d = _repo(with_workflow=True)
    _write_config(d, "strict")
    payload = {
        "tool_name": "Write", "hook_event": "PreToolUse", "cwd": d,
        "session_id": "t3",
        "tool_input": {"file_path": os.path.join(d, "app.py"), "content": "x = 1\n"},
    }
    rc, out = _run_gate(payload, d)
    assert rc == 0
