"""Tests for the .fettle.toml config system and session-scoped state (WP-2)."""

import os
import subprocess
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)

from fettle.config import DEFAULTS, load_config, state_dir, trace_path  # noqa: E402


# --- load_config layering ---

def test_defaults_when_no_file(tmp_path):
    cfg = load_config(str(tmp_path))
    assert cfg["gates"]["lint"]["enabled"] is True
    assert cfg["gates"]["lint"]["mode"] == "advisory"
    # Opinionated gates default OFF
    for gate in ("plan", "ux_spec", "ui_colors", "tests", "mcp_trust"):
        assert cfg["gates"][gate]["enabled"] is False, gate
    assert cfg["severity"]["error_rules"] == ["BLE001", "S110", "S608", "S701"]


def test_file_overrides_merge_deep(tmp_path):
    (tmp_path / ".fettle.toml").write_text(
        '[gates.plan]\nenabled = true\nthreshold = 5\n\n'
        '[severity]\nerror_rules = ["BLE001"]\n'
    )
    cfg = load_config(str(tmp_path))
    assert cfg["gates"]["plan"]["enabled"] is True
    assert cfg["gates"]["plan"]["threshold"] == 5
    # untouched keys inside merged sections survive
    assert cfg["gates"]["plan"]["plan_dir"] == "docs"
    assert cfg["gates"]["lint"]["enabled"] is True
    assert cfg["severity"]["error_rules"] == ["BLE001"]


def test_env_mode_override(tmp_path, monkeypatch):
    (tmp_path / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    monkeypatch.setenv("FETTLE_GATE_MODE", "advisory")
    cfg = load_config(str(tmp_path))
    assert cfg["gates"]["lint"]["mode"] == "advisory"


def test_explicit_config_path(tmp_path, monkeypatch):
    config_path = tmp_path / "custom.toml"
    config_path.write_text('[gates.lint]\nmode = "enforce"\n')
    monkeypatch.setenv("FETTLE_CONFIG", str(config_path))

    cfg = load_config(str(tmp_path / "project"))

    assert cfg["gates"]["lint"]["mode"] == "enforce"


def test_env_mode_off_disables_lint(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_GATE_MODE", "off")
    cfg = load_config(str(tmp_path))
    assert cfg["gates"]["lint"]["enabled"] is False


def test_malformed_toml_falls_back_loudly(tmp_path, capsys):
    (tmp_path / ".fettle.toml").write_text("this is [not toml")
    cfg = load_config(str(tmp_path))
    assert cfg["gates"]["lint"]["enabled"] is True  # defaults survive
    assert "could not parse" in capsys.readouterr().err


def test_defaults_not_mutated_by_load(tmp_path):
    (tmp_path / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    load_config(str(tmp_path))
    assert DEFAULTS["gates"]["lint"]["mode"] == "advisory"


# --- session state isolation ---

def test_state_dir_isolates_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    a = state_dir("session-a")
    b = state_dir("session-b")
    assert a != b
    assert a.is_dir() and b.is_dir()
    (a / "edits.jsonl").write_text("x")
    assert not (b / "edits.jsonl").exists()


def test_state_dir_sanitizes_session_id(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    d = state_dir("../../evil")
    assert (tmp_path / "state") in d.parents
    assert ".." not in d.name


def test_trace_path_under_project(tmp_path):
    cfg = load_config(str(tmp_path))
    tp = trace_path(cfg, str(tmp_path))
    assert tp.parent == tmp_path / ".fettle"
    assert tp.name == "trace.jsonl"


# --- end-to-end: gates honor config through the hook entrypoint ---

def _run_gate(payload_cwd, session, tool="Write", file_path="src/a.py", event="PreToolUse"):
    import json

    payload = {
        "tool_name": tool,
        "tool_input": {"file_path": os.path.join(str(payload_cwd), file_path), "content": "x = 1\n"},
        "cwd": str(payload_cwd),
        "hook_event": event,
        "session_id": session,
    }
    return subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "quality_gate.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture()
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    return tmp_path


def test_plan_gate_off_by_default(isolated_state):
    proj = isolated_state / "proj"
    proj.mkdir()
    for i in range(4):
        rc = _run_gate(proj, "s1", file_path=f"src/mod{i}.py")
        assert rc.returncode == 0, rc.stdout + rc.stderr


def test_plan_gate_blocks_when_enabled(isolated_state):
    proj = isolated_state / "proj"
    proj.mkdir()
    (proj / ".fettle.toml").write_text("[gates.plan]\nenabled = true\nthreshold = 3\n")
    results = [_run_gate(proj, "s2", file_path=f"src/mod{i}.py") for i in range(3)]
    assert results[-1].returncode == 2
    assert "PLANNING" in results[-1].stdout
    assert "gates.plan" in results[-1].stdout  # block names its disable key
